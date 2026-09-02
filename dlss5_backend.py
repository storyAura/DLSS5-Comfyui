# -*- coding: utf-8 -*-
"""ComfyUI IMAGE tensor adapter around the upstream DLSS5 Live session."""
from __future__ import annotations

import sys
import threading
from typing import Any

import numpy as np
import torch

try:
    from . import dlss_engine
    from .vendor_dlls import (
        VendorError,
        add_dll_directories,
        ensure_vendor_dlls,
        host_dll_path,
        nr_dll_path,
        resolve_gpu_gen,
    )
except ImportError:
    import dlss_engine
    from vendor_dlls import (
        VendorError,
        add_dll_directories,
        ensure_vendor_dlls,
        host_dll_path,
        nr_dll_path,
        resolve_gpu_gen,
    )

try:
    from comfy.utils import ProgressBar
except ImportError:
    ProgressBar = None

STYLE_CHOICES = {"默认": 0, "自然": 1, "电影": 2, "风格3": 3}
OUTVIEW_CHOICES = {"处理": 0, "差异×10": 1, "左右对比": 2}

_lock = threading.Lock()
_session: dlss_engine.Live | None = None
_session_gen: str | None = None
_session_dll: str | None = None
_vendor_ready: set[str] = set()


def _require_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError("DLSS5 Neural Render only runs on Windows with an NVIDIA RTX GPU.")


def _to_rgba_uint8(frame: np.ndarray) -> np.ndarray:
    clipped = np.clip(frame, 0.0, 1.0)
    height, width, channels = clipped.shape
    if channels == 1:
        clipped = np.repeat(clipped, 3, axis=2)
    rgb = (clipped[..., :3] * 255.0).round().astype(np.uint8)
    if channels >= 4:
        alpha = (clipped[..., 3] * 255.0).round().astype(np.uint8)
    else:
        alpha = np.full((height, width), 255, np.uint8)
    return np.ascontiguousarray(np.dstack([rgb, alpha]))


def _ensure_session(width: int, height: int, gen: str, settings: dict[str, Any]) -> dlss_engine.Live:
    """Reuse the process-global Live session. Caller must hold `_lock`."""
    global _session, _session_gen, _session_dll
    dll = str(nr_dll_path(gen))
    if _session is not None and _session_gen != gen:
        raise RuntimeError(
            f"NGX is already initialized with {_session_gen} ({_session_dll}). "
            f"Restart ComfyUI to switch to {gen}."
        )
    if _session is None:
        add_dll_directories(gen)
        dlss_engine.configure(
            host_dll=str(host_dll_path()),
            dlssnr_dll=dll,
            log_path=str(host_dll_path().with_name("dlss_run.log")),
        )
        _session = dlss_engine.Live(width, height, settings)
        _session_gen = gen
        _session_dll = dll
        return _session
    if (_session.width, _session.height) != (width, height):
        _session.resize(width, height, int(settings.get("preset", 1)))
    _session.update(settings)
    return _session


def process_images(
    images: torch.Tensor,
    style: str,
    intensity: float,
    local_tone: float,
    local_struct: float,
    output_view: str,
    output_mix: float,
    gpu_gen: str,
    preset: int = 1,
    skin_struct: float = 1.0,
    use_auto_mask: bool = False,
    ui_correction: bool = False,
) -> torch.Tensor:
    _require_windows()
    if style not in STYLE_CHOICES:
        raise ValueError(f"Unknown style '{style}'")
    if output_view not in OUTVIEW_CHOICES:
        raise ValueError(f"Unknown output_view '{output_view}'")
    preset_i = int(preset)
    if preset_i not in (0, 1, 2, 3):
        raise ValueError(f"Unknown preset '{preset}'")

    gen, reason = resolve_gpu_gen(gpu_gen)
    print(f"[DLSS5] using {gen} ({reason})")
    if gen not in _vendor_ready:
        try:
            ensure_vendor_dlls(gen)
        except VendorError as exc:
            raise RuntimeError(str(exc)) from exc
        _vendor_ready.add(gen)

    settings = {
        "preset": preset_i,
        "style": STYLE_CHOICES[style],
        "intensity": float(intensity),
        "local_tone": float(local_tone),
        "local_struct": float(local_struct),
        "skin_struct": float(skin_struct),
        "use_auto_mask": 1 if use_auto_mask else 0,
        "ui_correction": 1 if ui_correction else 0,
        "output_view": OUTVIEW_CHOICES[output_view],
        "output_mix": float(output_mix),
    }

    if images.ndim != 4:
        raise ValueError(f"Expected IMAGE tensor [B,H,W,C], got shape {tuple(images.shape)}")
    if images.shape[0] == 0:
        return images

    device = images.device
    dtype = images.dtype
    batch = images.detach().float().cpu().numpy()
    _, height, width, channels = batch.shape
    view = settings["output_view"]
    mix = settings["output_mix"]

    progress = ProgressBar(batch.shape[0]) if ProgressBar is not None else None
    out_frames: list[np.ndarray] = []
    with _lock:
        session = _ensure_session(width, height, gen, settings)
        for index, frame in enumerate(batch):
            rgba = _to_rgba_uint8(frame)
            processed = session.process(rgba, reset=(index == 0))
            if processed is None:
                raise RuntimeError(
                    "dlssnr_process failed. See vendor/dlss_run.log for the host log."
                )
            if view != 0 or mix < 1.0:
                processed = dlss_engine.apply_output_view(
                    [processed], [rgba], view, mix, width, height
                )[0]
            rgb = processed[..., :3].astype(np.float32) / 255.0
            if channels >= 4:
                rgb = np.concatenate([rgb, frame[..., 3:4].astype(np.float32)], axis=2)
            out_frames.append(np.clip(rgb, 0.0, 1.0).astype(np.float32))
            if progress is not None:
                progress.update(1)

    stacked = np.stack(out_frames, axis=0)
    return torch.from_numpy(stacked).to(device=device, dtype=dtype)
