"""Apply custom branding watermark overlay."""

from pathlib import Path

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext
from app.utils.compat_encode import (
    audio_encode_args,
    container_args,
    has_audio_stream,
    run_ffmpeg,
    video_encode_args,
)


class WatermarkBrandingModule(BaseModule):
    name = "watermark_branding"
    description = "Overlay custom branding watermark"

    POSITIONS = {
        "top-left": "10:10",
        "top-right": "W-w-10:10",
        "bottom-left": "10:H-h-10",
        "bottom-right": "W-w-10:H-h-10",
        "center": "(W-w)/2:(H-h)/2",
    }

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("editing", default={})
        wm_path = cfg.get("watermark_path") or cfg.get("branding_path")

        if not wm_path or not Path(wm_path).exists():
            return ModuleResult(ModuleStatus.SKIPPED, "No branding watermark file set")

        video = context.current_video or context.input_path
        output = context.get_working_path("branded.mp4")
        pos = self.POSITIONS.get(cfg.get("watermark_position", "bottom-right"), "W-w-10:H-h-10")
        opacity = cfg.get("watermark_opacity", 0.7)
        scale = cfg.get("watermark_scale", 0.15)

        context.report(self.name, 40, "Applying branding watermark...")

        filter_complex = (
            f"[1:v]scale=iw*{scale}:-1,format=rgba,colorchannelmixer=aa={opacity}[wm];"
            f"[0:v][wm]overlay={pos},scale=trunc(iw/2)*2:trunc(ih/2)*2[v]"
        )

        has_audio = has_audio_stream(video)
        args = [
            "-i", str(video), "-i", str(wm_path),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            *video_encode_args(23, "medium"),
        ]
        if has_audio:
            args.extend(["-map", "0:a:0", *audio_encode_args("256k")])
        else:
            args.append("-an")
        args.extend(container_args())
        args.append(str(output))
        run_ffmpeg(args, "Watermark")

        context.current_video = output
        return ModuleResult(ModuleStatus.SUCCESS, "Branding watermark applied")
