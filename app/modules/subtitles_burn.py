"""Burn Whisper SRT subtitles into video."""

from pathlib import Path

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext
from app.utils.compat_encode import run_ffmpeg, video_encode_args, audio_encode_args, container_args


class SubtitlesBurnModule(BaseModule):
    name = "subtitles_burn"
    description = "Burn generated subtitles into video"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("editing", default={})
        if not cfg.get("burn_subtitles", True):
            return ModuleResult(ModuleStatus.SKIPPED, "Subtitle burn disabled")

        srt = getattr(context, "subtitle_path", None)
        if not srt or not Path(srt).exists():
            return ModuleResult(ModuleStatus.SKIPPED, "No subtitles to burn")

        video = context.current_video or context.input_path
        output = context.get_working_path("with_subtitles.mp4")

        srt_escaped = str(srt).replace("\\", "/").replace(":", "\\:")
        font_size = cfg.get("subtitle_font_size", 22)
        margin = cfg.get("subtitle_margin", 28)

        vf = (
            f"subtitles='{srt_escaped}':force_style="
            f"'FontSize={font_size},MarginV={margin},PrimaryColour=&HFFFFFF&,"
            f"OutlineColour=&H000000&,Outline=2,Bold=1'"
        )

        context.report(self.name, 50, "Burning subtitles...")

        args = [
            "-i", str(video),
            "-vf", f"{vf},scale=trunc(iw/2)*2:trunc(ih/2)*2",
            *video_encode_args(23, "medium"),
            *audio_encode_args("192k"),
            *container_args(),
            str(output),
        ]
        run_ffmpeg(args, "Subtitles")

        context.current_video = output
        return ModuleResult(ModuleStatus.SUCCESS, "Subtitles burned in")
