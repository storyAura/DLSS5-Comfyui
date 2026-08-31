#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ctypes wrapper for the upstream DLSS5 Feature 18 host DLL (zero-guidance).

Adapted from purkatyy/DLSS5- (MIT, Copyright 2026 ylso0). Feature 18 ignores
depth/flow in this config, so the engine always feeds zero guidance.
"""
from __future__ import annotations

import ctypes
import os
import threading
from typing import Any

import numpy as np

HOST_DLL = ""
DLSSNR_DLL = ""
LOG_PATH = ""

_lib = None
_load_lock = threading.Lock()


def configure(host_dll: str, dlssnr_dll: str, log_path: str) -> None:
    """Set DLL and log paths before the first Live session is created."""
    global HOST_DLL, DLSSNR_DLL, LOG_PATH
    HOST_DLL = host_dll
    DLSSNR_DLL = dlssnr_dll
    LOG_PATH = log_path


def _load():
    global _lib
    with _load_lock:
        if _lib is None:
            if not HOST_DLL or not os.path.exists(HOST_DLL):
                raise FileNotFoundError("missing host DLL: %s" % HOST_DLL)
            _lib = ctypes.CDLL(HOST_DLL)
            _lib.dlssnr_init.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p, ctypes.c_wchar_p]
            _lib.dlssnr_init.restype = ctypes.c_int
            _lib.dlssnr_create_feature.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
            _lib.dlssnr_create_feature.restype = ctypes.c_int
            _lib.dlssnr_process.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
            _lib.dlssnr_process.restype = ctypes.c_int
            _lib.dlssnr_set_options.argtypes = [
                ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_float,
                ctypes.c_float, ctypes.c_float, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_float, ctypes.c_float,
            ]
            _lib.dlssnr_set_options.restype = None
            _lib.dlssnr_shutdown.argtypes = []
            _lib.dlssnr_shutdown.restype = None
            _lib.dlssnr_resize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
            _lib.dlssnr_resize.restype = ctypes.c_int
        return _lib


def _set_options(lib, s: dict[str, Any]) -> None:
    lib.dlssnr_set_options(
        int(s.get("preset", 1)),
        int(s.get("style", 0)),
        float(s.get("intensity", 1.0)),
        float(s.get("local_tone", 1.0)),
        float(s.get("local_struct", 1.0)),
        float(s.get("skin_struct", 1.0)),
        int(s.get("use_auto_mask", 0)),
        int(s.get("ui_correction", 0)),
        0,
        int(s.get("depth_convention", 2)),
        float(s.get("motion_scale_x", 1.0)),
        float(s.get("motion_scale_y", 1.0)),
    )


def _read_log_tail(limit: int = 800) -> str:
    if not LOG_PATH or not os.path.exists(LOG_PATH):
        return ""
    with open(LOG_PATH, encoding="utf-8", errors="replace") as handle:
        return handle.read()[-limit:]


def apply_output_view(
    processed: list[np.ndarray],
    color: list[np.ndarray],
    view: int,
    mix: float,
    w: int,
    h: int,
) -> list[np.ndarray]:
    """Post-process DLSS RGBA8 output (0=Processed, 1=DiffX10, 2=L/R Compare)."""
    out = []
    for pr, co in zip(processed, color):
        cof = co[..., :3].astype(np.float32) / 255.0
        prf = pr[..., :3].astype(np.float32) / 255.0
        if view == 1:
            result = np.clip(0.5 + (prf - cof) * 10.0, 0, 1)
        elif view == 2:
            result = prf.copy()
            result[:, : w // 2] = cof[:, : w // 2]
            if w % 2 == 1:
                result[:, w // 2] = 1.0
        else:
            result = cof + (prf - cof) * mix
        stacked = np.dstack([result, np.ones((h, w), np.float32)])
        out.append((stacked * 255.0).clip(0, 255).astype(np.uint8))
    return out


class Live:
    """Persistent single-frame DLSS session. NGX core init is one-time per process."""

    def __init__(self, w: int, h: int, settings: dict[str, Any] | None = None):
        self._w, self._h = w, h
        self.settings = dict(settings or {})
        self._initialized = False
        self._lib = _load()
        self._open()

    def _open(self) -> None:
        if self._initialized:
            raise RuntimeError(
                "NGX core init is one-time per process. Restart ComfyUI instead of re-init."
            )
        s = self.settings
        _set_options(self._lib, s)
        if not DLSSNR_DLL or not os.path.exists(DLSSNR_DLL):
            raise FileNotFoundError("missing nvngx_dlssnr.dll: %s" % DLSSNR_DLL)
        if not self._lib.dlssnr_init(self._w, self._h, int(s.get("preset", 1)), DLSSNR_DLL, LOG_PATH):
            raise RuntimeError("dlssnr_init failed (D3D12/gate). See " + LOG_PATH)
        self._initialized = True
        if not self._lib.dlssnr_create_feature(self._w, self._h, int(s.get("preset", 1))):
            raise RuntimeError("Feature 18 create failed.\n" + _read_log_tail())

    def update(self, settings: dict[str, Any]) -> None:
        old_preset = self.settings.get("preset")
        self.settings.update(settings)
        if self.settings.get("preset") != old_preset:
            self.resize(self._w, self._h, int(self.settings.get("preset", 1)))

    def resize(self, w: int, h: int, preset: int | None = None) -> None:
        if preset is None:
            preset = int(self.settings.get("preset", 1))
        self.settings["preset"] = preset
        _set_options(self._lib, self.settings)
        if not self._lib.dlssnr_resize(w, h, preset):
            raise RuntimeError("Feature 18 resize failed.\n" + _read_log_tail())
        self._w, self._h = w, h

    def process(self, rgba: np.ndarray, reset: bool = False) -> np.ndarray | None:
        _set_options(self._lib, self.settings)
        rgba = np.ascontiguousarray(rgba)
        h, w = rgba.shape[:2]
        mv = np.zeros((h, w, 2), np.float32)
        dp = np.zeros((h, w), np.float32)
        out = np.zeros_like(rgba)
        ok = self._lib.dlssnr_process(
            rgba.ctypes.data_as(ctypes.c_void_p),
            mv.ctypes.data_as(ctypes.c_void_p),
            dp.ctypes.data_as(ctypes.c_void_p),
            out.ctypes.data_as(ctypes.c_void_p),
            1 if reset else 0,
        )
        return out if ok else None

    @property
    def width(self) -> int:
        return self._w

    @property
    def height(self) -> int:
        return self._h

    def close(self) -> None:
        if not self._initialized:
            return
        try:
            self._lib.dlssnr_shutdown()
        except Exception:
            pass
        self._initialized = False
