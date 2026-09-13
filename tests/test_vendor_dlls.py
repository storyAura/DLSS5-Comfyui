# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vendor_dlls import (  # noqa: E402
    ASSET_SHA256,
    GPU_GEN_LABELS,
    VendorError,
    gen_from_capability,
    gen_from_gpu_name,
    resolve_gpu_gen,
    verify_archive,
)


def test_name_parsing() -> None:
    cases = {
        "NVIDIA GeForce RTX 3060": "rtx30",
        "GeForce RTX 3080 Ti": "rtx30",
        "NVIDIA GeForce RTX 4090": "rtx40",
        "RTX 4070 Laptop GPU": "rtx40",
        "NVIDIA GeForce RTX 5090": "rtx50",
        "GeForce RTX 5070 Ti": "rtx50",
        "Intel Arc": None,
        "AMD Radeon": None,
    }
    for name, expected in cases.items():
        got = gen_from_gpu_name(name)
        assert got == expected, f"{name}: {got} != {expected}"


def test_capability() -> None:
    assert gen_from_capability((8, 6)) == "rtx30"
    assert gen_from_capability((8, 9)) == "rtx40"
    assert gen_from_capability((10, 0)) == "rtx50"
    assert gen_from_capability((12, 0)) == "rtx50"
    assert gen_from_capability((7, 5)) is None


def test_archive_hash_mismatch(tmp_path: Path | None = None) -> None:
    folder = tmp_path if tmp_path is not None else Path(__file__).resolve().parent
    junk = folder / "_hash_junk.bin"
    junk.write_bytes(b"not-an-official-archive")
    try:
        verify_archive(junk, "0" * 64)
        raise AssertionError("expected VendorError")
    except VendorError:
        assert not junk.exists()
    assert len(ASSET_SHA256) == 3
    assert all(len(value) == 64 for value in ASSET_SHA256.values())


def test_manual_resolve() -> None:
    gen, reason = resolve_gpu_gen("RTX 50")
    assert gen == "rtx50"
    assert "manual" in reason
    assert "Auto" in GPU_GEN_LABELS


if __name__ == "__main__":
    test_name_parsing()
    test_capability()
    test_manual_resolve()
    test_archive_hash_mismatch()
    print("ok")
