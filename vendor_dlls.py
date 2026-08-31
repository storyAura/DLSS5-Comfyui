# -*- coding: utf-8 -*-
"""Download and select per-GPU nvngx_dlssnr.dll from the upstream DLSS5 release."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

try:
    import torch
except ImportError:
    torch = None

PACKAGE_DIR = Path(__file__).resolve().parent
VENDOR_DIR = PACKAGE_DIR / "vendor"
CACHE_DIR = VENDOR_DIR / ".cache"
HOST_DLL_NAME = "dlssnr_host.dll"
NR_DLL_NAME = "nvngx_dlssnr.dll"

RELEASE_BASE = "https://github.com/purkatyy/DLSS5-/releases/download/dlss"
ZIP_URL = f"{RELEASE_BASE}/DLSS5Tool.zip"
RAR_30_URL = f"{RELEASE_BASE}/RTX30xx.rar"
RAR_50_URL = f"{RELEASE_BASE}/RTX50xx.rar"

# GitHub release asset digests for tag `dlss` (sha256:<hex> from the API).
ASSET_SHA256 = {
    "DLSS5Tool.zip": "733c334f3b30d10d7fbd4d75f7242ff01b6e08380ac3396b39920e47eb6f65d0",
    "RTX30xx.rar": "62427325f40aef0fc703904f53055883740ff8d2721203cfe376f33892b304b1",
    "RTX50xx.rar": "97d5d4292937d5f7839c2a0755c63961dc5db8b755fd994e37607496e14e31dd",
}

GEN_RTX30 = "rtx30"
GEN_RTX40 = "rtx40"
GEN_RTX50 = "rtx50"
VALID_GENS = (GEN_RTX30, GEN_RTX40, GEN_RTX50)

GPU_GEN_LABELS = {
    "Auto": None,
    "RTX 30": GEN_RTX30,
    "RTX 40": GEN_RTX40,
    "RTX 50": GEN_RTX50,
}

_RTX_NAME_RE = re.compile(r"rtx\s*([3-5])\d{2}", re.IGNORECASE)


class VendorError(RuntimeError):
    """Raised when a vendor DLL cannot be downloaded, extracted, or selected."""


def host_dll_path() -> Path:
    return VENDOR_DIR / HOST_DLL_NAME


def nr_dll_path(gen: str) -> Path:
    if gen not in VALID_GENS:
        raise VendorError(f"Unknown GPU generation: {gen}")
    return VENDOR_DIR / gen / NR_DLL_NAME


def find_7z() -> str | None:
    env = os.environ.get("SEVEN_ZIP")
    if env and Path(env).is_file():
        return env
    for candidate in (
        Path(r"C:\Program Files\7-Zip\7z.exe"),
        Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
    ):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("7z") or shutil.which("7z.exe") or shutil.which("7za")


def _gpu_name_from_smi() -> str | None:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    line = completed.stdout.strip().splitlines()
    return line[0].strip() if line else None


def _gpu_name_and_capability() -> tuple[str | None, tuple[int, int] | None]:
    if torch is not None:
        try:
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                capability = torch.cuda.get_device_capability(0)
                return name, capability
        except Exception:
            pass
    return _gpu_name_from_smi(), None


def gen_from_gpu_name(name: str) -> str | None:
    match = _RTX_NAME_RE.search(name)
    if match is None:
        return None
    return f"rtx{match.group(1)}0"


def gen_from_capability(capability: tuple[int, int]) -> str | None:
    major, minor = capability
    if major >= 10:
        return GEN_RTX50
    if major == 8 and minor == 9:
        return GEN_RTX40
    if major == 8 and minor >= 6:
        return GEN_RTX30
    if major == 8:
        return GEN_RTX30
    return None


def detect_gpu_gen() -> tuple[str, str]:
    """Return (gen, reason). Unknown consumer cards fall back to rtx40."""
    name, capability = _gpu_name_and_capability()
    if name:
        from_name = gen_from_gpu_name(name)
        if from_name:
            return from_name, f"gpu name '{name}'"
    if capability:
        from_cap = gen_from_capability(capability)
        if from_cap:
            label = name or f"sm_{capability[0]}{capability[1]}"
            return from_cap, f"compute capability {capability} ({label})"
    if name:
        return GEN_RTX40, f"unrecognized GPU '{name}', falling back to RTX 40"
    return GEN_RTX40, "GPU not detected, falling back to RTX 40"


def resolve_gpu_gen(gpu_gen_label: str) -> tuple[str, str]:
    if gpu_gen_label not in GPU_GEN_LABELS:
        raise VendorError(
            f"Unknown gpu_gen '{gpu_gen_label}'. Use Auto / RTX 30 / RTX 40 / RTX 50."
        )
    mapped = GPU_GEN_LABELS[gpu_gen_label]
    if mapped is not None:
        return mapped, f"manual {gpu_gen_label}"
    return detect_gpu_gen()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(path: Path, expected_sha256: str) -> None:
    got = sha256_file(path)
    if got != expected_sha256:
        path.unlink(missing_ok=True)
        raise VendorError(
            f"{path.name} SHA-256 mismatch (got {got}, expected {expected_sha256}). "
            "Cached file was deleted. Re-download from the official release."
        )


def _ensure_archive(filename: str, url: str) -> Path:
    dest = CACHE_DIR / filename
    expected = ASSET_SHA256[filename]
    if dest.is_file():
        try:
            verify_archive(dest, expected)
            return dest
        except VendorError:
            print(f"[DLSS5] cached {filename} failed hash check, re-downloading")
    _download(url, dest, expected)
    return dest


def _download(url: str, dest: Path, expected_sha256: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "DLSS5-ComfyUI"})
    print(f"[DLSS5] downloading {url}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response, tmp.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except urllib.error.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        raise VendorError(f"Download failed ({exc.code}) for {url}") from exc
    except urllib.error.URLError as exc:
        tmp.unlink(missing_ok=True)
        raise VendorError(f"Download failed for {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        tmp.unlink(missing_ok=True)
        raise VendorError(f"Download timed out for {url}") from exc
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise VendorError(f"Download I/O failed for {url}: {exc}") from exc
    tmp.replace(dest)
    try:
        verify_archive(dest, expected_sha256)
    except VendorError:
        dest.unlink(missing_ok=True)
        raise
    print(f"[DLSS5] saved {dest} ({dest.stat().st_size} bytes)")


def _extract_zip_member(archive: Path, member_suffix: str, dest: Path) -> bool:
    suffix = member_suffix.replace("\\", "/").lower()
    with zipfile.ZipFile(archive) as zipped:
        for name in zipped.namelist():
            normalized = name.replace("\\", "/").lower()
            if normalized.endswith(suffix) and not name.endswith("/"):
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(name) as src, dest.open("wb") as out:
                    shutil.copyfileobj(src, out)
                return True
    return False


def _extract_rar_dll(archive: Path, dest: Path) -> None:
    seven = find_7z()
    if seven is None:
        raise VendorError(
            "Need 7-Zip to extract RTX 30/50 DLLs from .rar. "
            "Install 7-Zip or set SEVEN_ZIP to 7z.exe, then retry."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    work = dest.parent / "_extract_tmp"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    try:
        try:
            completed = subprocess.run(
                [seven, "e", str(archive), f"-o{work}", NR_DLL_NAME, "-r", "-y"],
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired as exc:
            raise VendorError(f"7-Zip timed out extracting {archive.name}") from exc
        if completed.returncode != 0:
            raise VendorError(
                f"7-Zip failed to extract {archive.name}: {completed.stderr[-400:]}"
            )
        found = list(work.rglob(NR_DLL_NAME))
        if not found:
            raise VendorError(f"{NR_DLL_NAME} not found inside {archive.name}")
        shutil.copy2(found[0], dest)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _ensure_zip_assets(need_40: bool) -> None:
    need_host = not host_dll_path().is_file()
    need_40_dll = need_40 and not nr_dll_path(GEN_RTX40).is_file()
    if not need_host and not need_40_dll:
        return
    archive = _ensure_archive("DLSS5Tool.zip", ZIP_URL)
    if need_host and not _extract_zip_member(archive, HOST_DLL_NAME, host_dll_path()):
        raise VendorError(f"{HOST_DLL_NAME} missing from DLSS5Tool.zip")
    if need_40_dll and not _extract_zip_member(archive, NR_DLL_NAME, nr_dll_path(GEN_RTX40)):
        raise VendorError(f"{NR_DLL_NAME} missing from DLSS5Tool.zip")


def _ensure_rar_gen(gen: str, url: str, filename: str) -> None:
    dest = nr_dll_path(gen)
    if dest.is_file():
        return
    archive = _ensure_archive(filename, url)
    _extract_rar_dll(archive, dest)


def ensure_vendor_dlls(gen: str | None = None) -> None:
    """Download host + the requested runtime. gen=None prefetches all three."""
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_zip_assets(need_40=(gen is None or gen == GEN_RTX40))
    rar_jobs = (
        (GEN_RTX30, RAR_30_URL, "RTX30xx.rar"),
        (GEN_RTX50, RAR_50_URL, "RTX50xx.rar"),
    )
    for item, url, filename in rar_jobs:
        if gen is not None and item != gen:
            continue
        _ensure_rar_gen(item, url, filename)
    if not host_dll_path().is_file():
        raise VendorError(
            f"Missing {host_dll_path()}. Re-run from a machine that can download {ZIP_URL}"
        )
    needed = VALID_GENS if gen is None else (gen,)
    for item in needed:
        path = nr_dll_path(item)
        if not path.is_file():
            raise VendorError(
                f"Missing {path}. Download the matching asset from {RELEASE_BASE} "
                f"and place {NR_DLL_NAME} there."
            )


def add_dll_directories(gen: str) -> None:
    if sys.platform != "win32":
        return
    adder = getattr(os, "add_dll_directory", None)
    if adder is None:
        os.environ["PATH"] = os.pathsep.join(
            [str(VENDOR_DIR), str(nr_dll_path(gen).parent), os.environ.get("PATH", "")]
        )
        return
    adder(str(VENDOR_DIR))
    adder(str(nr_dll_path(gen).parent))


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target in GPU_GEN_LABELS:
        target, reason = resolve_gpu_gen(target)
        print(f"[DLSS5] resolved {target} ({reason})")
    ensure_vendor_dlls(target)
    print(f"[DLSS5] host={host_dll_path()}")
    for item in VALID_GENS:
        print(f"[DLSS5] {item}={nr_dll_path(item)} exists={nr_dll_path(item).is_file()}")
