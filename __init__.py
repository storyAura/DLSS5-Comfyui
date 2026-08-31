# -*- coding: utf-8 -*-
"""ComfyUI-DLSS5 custom node package."""
from __future__ import annotations

try:
    from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
except ImportError:
    from nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

try:
    from .nodes import comfy_entrypoint
except ImportError:
    try:
        from nodes import comfy_entrypoint
    except ImportError:
        comfy_entrypoint = None

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]
if comfy_entrypoint is not None:
    __all__.append("comfy_entrypoint")
