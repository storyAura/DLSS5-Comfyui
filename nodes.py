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
PRESET_LIST = ["0", "1", "2", "3"]


def _run(
    images: Any,
    style: str,
    intensity: float,
    local_tone: float,
    local_struct: float,
    output_view: str,
    output_mix: float,
    gpu_gen: str,
    preset: int | str = 1,
    skin_struct: float = 1.0,
    use_auto_mask: bool = False,
    ui_correction: bool = False,
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
        preset=int(preset),
        skin_struct=skin_struct,
        use_auto_mask=use_auto_mask,
        ui_correction=ui_correction,
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


class DLSS5NeuralRenderAdvanced:
    """Classic ComfyUI node with extra Feature 18 options."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "style": (STYLE_LIST, {"default": "默认"}),
                "intensity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "local_tone": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 2.0, "step": 0.05}),
                "local_struct": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 2.0, "step": 0.05}),
                "output_view": (OUTVIEW_LIST, {"default": "处理"}),
                "output_mix": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "gpu_gen": (GPU_GEN_LIST, {"default": "Auto"}),
                "preset": (PRESET_LIST, {"default": "1"}),
                "skin_struct": ("FLOAT", {"default": 1.0, "min": -1.0, "max": 2.0, "step": 0.05}),
                "use_auto_mask": ("BOOLEAN", {"default": False}),
                "ui_correction": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "process"
    CATEGORY = "image/dlss5"
    DESCRIPTION = (
        "DLSS5 Feature 18 neural render with extra options. "
        "local_tone / local_struct default 0.5 and go up to 2."
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
        preset,
        skin_struct,
        use_auto_mask,
        ui_correction,
    ):
        return (_run(
            images, style, intensity, local_tone, local_struct,
            output_view, output_mix, gpu_gen,
            preset=preset,
            skin_struct=skin_struct,
            use_auto_mask=use_auto_mask,
            ui_correction=ui_correction,
        ),)


NODE_CLASS_MAPPINGS = {
    "DLSS5NeuralRender": DLSS5NeuralRender,
    "DLSS5NeuralRenderAdvanced": DLSS5NeuralRenderAdvanced,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DLSS5NeuralRender": "DLSS5 Neural Render",
    "DLSS5NeuralRenderAdvanced": "DLSS5 Neural Render (Advanced)",
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

    class DLSS5NeuralRenderAdvancedV3(io.ComfyNode):
        @classmethod
        def define_schema(cls):
            return io.Schema(
                node_id="DLSS5NeuralRenderAdvanced",
                display_name="DLSS5 Neural Render (Advanced)",
                category="image/dlss5",
                search_aliases=["dlss", "dlss5", "nvidia", "neural render", "advanced"],
                inputs=[
                    io.Image.Input("images"),
                    io.Combo.Input("style", options=STYLE_LIST, default="默认"),
                    io.Float.Input("intensity", default=1.0, min=0.0, max=2.0, step=0.05),
                    io.Float.Input("local_tone", default=0.5, min=0.0, max=2.0, step=0.05),
                    io.Float.Input("local_struct", default=0.5, min=0.0, max=2.0, step=0.05),
                    io.Combo.Input("output_view", options=OUTVIEW_LIST, default="处理"),
                    io.Float.Input("output_mix", default=1.0, min=0.0, max=1.0, step=0.05),
                    io.Combo.Input("gpu_gen", options=GPU_GEN_LIST, default="Auto"),
                    io.Combo.Input("preset", options=PRESET_LIST, default="1"),
                    io.Float.Input("skin_struct", default=1.0, min=-1.0, max=2.0, step=0.05),
                    io.Boolean.Input("use_auto_mask", default=False),
                    io.Boolean.Input("ui_correction", default=False),
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
            preset,
            skin_struct,
            use_auto_mask,
            ui_correction,
        ):
            return io.NodeOutput(_run(
                images, style, intensity, local_tone, local_struct,
                output_view, output_mix, gpu_gen,
                preset=preset,
                skin_struct=skin_struct,
                use_auto_mask=use_auto_mask,
                ui_correction=ui_correction,
            ))

    class DLSS5Extension(ComfyExtension):
        async def get_node_list(self):
            return [DLSS5NeuralRenderV3, DLSS5NeuralRenderAdvancedV3]

    async def comfy_entrypoint():
        return DLSS5Extension()
