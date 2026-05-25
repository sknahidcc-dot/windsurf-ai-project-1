"""Intro and outro video injection."""

from pathlib import Path

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext
from app.utils.compat_encode import run_ffmpeg, video_encode_args, audio_encode_args, container_args


class IntroOutroModule(BaseModule):
    name = "intro_outro"
    description = "Prepend intro and append outro clips"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("editing", default={})
        intro = cfg.get("intro_path")
        outro = cfg.get("outro_path")

        if not intro and not outro:
            return ModuleResult(ModuleStatus.SKIPPED, "No intro/outro configured")

        video = context.current_video or context.input_path
        parts = []

        if intro and Path(intro).exists():
            parts.append(self._normalize_clip(intro, context, "intro_norm.mp4"))
        parts.append(str(video))
        if outro and Path(outro).exists():
            parts.append(self._normalize_clip(outro, context, "outro_norm.mp4"))

        if len(parts) <= 1:
            return ModuleResult(ModuleStatus.SKIPPED, "Intro/outro files not found")

        concat_file = context.get_working_path("intro_outro_list.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for p in parts:
                f.write(f"file '{Path(p).resolve()}'\n")

        output = context.get_working_path("with_intro_outro.mp4")
        context.report(self.name, 60, "Merging intro/main/outro...")

        args = [
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            *video_encode_args(23, "medium"),
            *audio_encode_args("192k"),
            *container_args(),
            str(output),
        ]
        run_ffmpeg(args, "Intro/outro")

        context.current_video = output
        return ModuleResult(ModuleStatus.SUCCESS, "Intro/outro applied")

    def _normalize_clip(self, path: str, context: PipelineContext, name: str) -> str:
        """Normalize clip to compatible encode for concat."""
        out = str(context.get_working_path(name))
        args = [
            "-i", path,
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            *video_encode_args(23, "fast"),
            *audio_encode_args("192k"),
            *container_args(),
            out,
        ]
        run_ffmpeg(args, "Normalize clip")
        return out
