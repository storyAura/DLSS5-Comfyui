# -*- coding: utf-8 -*-
"""ComfyUI node registration for DLSS5 Neural Render."""
from __future__ import annotations

from typing import Any

try:
    from .dlss5_backend import OUTVIEW_CHOICES, STYLE_CHOICES, process_images
    from .vendor_dlls import GPU_GEN_LABELS
except ImportError:
    from dlss5_backend import OUTVIEW_CHOICES, STYLE_CHOICES, process_images
    from vendor_dlls import GPU_GEN_LABELS

try:
    from comfy_api.latest import ComfyExtension, io
except ImportError:
    ComfyExtension = None
    io = None

STYLE_LIST = list(STYLE_CHOICES.keys())
OUTVIEW_LIST = list(OUTVIEW_CHOICES.keys())
GPU_GEN_LIST = list(GPU_GEN_LABELS.keys())


def _run(
    images: Any,
    style: str,
    intensity: float,
    local_tone: float,
    local_struct: float,
    output_view: str,
    output_mix: float,
    gpu_gen: str,
) -> Any:
    return process_images(
        images=images,
        style=style,
        intensity=intensity,
        local_tone=local_tone,
        local_struct=local_struct,
        output_view=output_view,
        output_mix=output_mix,
        gpu_gen=gpu_gen,
    )


class DLSS5NeuralRender:
    """Classic ComfyUI node: IMAGE in, IMAGE out."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "style": (STYLE_LIST, {"default": "默认"}),
                "intensity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "local_tone": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "local_struct": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "output_view": (OUTVIEW_LIST, {"default": "处理"}),
                "output_mix": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "gpu_gen": (GPU_GEN_LIST, {"default": "Auto"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "process"
    CATEGORY = "image/dlss5"
    DESCRIPTION = (
        "DLSS5 Feature 18 neural render (same-resolution). "
        "Auto picks RTX 30/40/50 nvngx_dlssnr.dll from vendor/."
    )

    def process(
        self,
        images,
        style,
        intensity,
        local_tone,
        local_struct,
        output_view,
        output_mix,
        gpu_gen,
    ):
        return (_run(
            images, style, intensity, local_tone, local_struct,
            output_view, output_mix, gpu_gen,
        ),)


NODE_CLASS_MAPPINGS = {
    "DLSS5NeuralRender": DLSS5NeuralRender,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DLSS5NeuralRender": "DLSS5 Neural Render",
}


if io is not None:

    class DLSS5NeuralRenderV3(io.ComfyNode):
        @classmethod
        def define_schema(cls):
            return io.Schema(
                node_id="DLSS5NeuralRender",
                display_name="DLSS5 Neural Render",
                category="image/dlss5",
                search_aliases=["dlss", "dlss5", "nvidia", "neural render"],
                inputs=[
                    io.Image.Input("images"),
                    io.Combo.Input("style", options=STYLE_LIST, default="默认"),
                    io.Float.Input("intensity", default=1.0, min=0.0, max=1.0, step=0.05),
                    io.Float.Input("local_tone", default=1.0, min=0.0, max=1.0, step=0.05),
                    io.Float.Input("local_struct", default=1.0, min=0.0, max=1.0, step=0.05),
                    io.Combo.Input("output_view", options=OUTVIEW_LIST, default="处理"),
                    io.Float.Input("output_mix", default=1.0, min=0.0, max=1.0, step=0.05),
                    io.Combo.Input("gpu_gen", options=GPU_GEN_LIST, default="Auto"),
                ],
                outputs=[
                    io.Image.Output("images"),
                ],
            )

        @classmethod
        def execute(
            cls,
            images,
            style,
            intensity,
            local_tone,
            local_struct,
            output_view,
            output_mix,
            gpu_gen,
        ):
            return io.NodeOutput(_run(
                images, style, intensity, local_tone, local_struct,
                output_view, output_mix, gpu_gen,
            ))

    class DLSS5Extension(ComfyExtension):
        async def get_node_list(self):
            return [DLSS5NeuralRenderV3]

    async def comfy_entrypoint():
        return DLSS5Extension()
