"""Input validation and probe."""

import shutil
from pathlib import Path

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext
from app.utils.ffmpeg import FFmpegHelper, check_ffmpeg


class PreprocessingModule(BaseModule):
    name = "preprocessing"
    description = "Validate input and extract video metadata"

    def run(self, context: PipelineContext) -> ModuleResult:
        if not check_ffmpeg():
            return ModuleResult(
                ModuleStatus.FAILED,
                "FFmpeg not found. Install FFmpeg and add to PATH.",
            )

        input_path = context.input_path
        if not input_path.exists():
            return ModuleResult(ModuleStatus.FAILED, f"Input file not found: {input_path}")

        valid_ext = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v"}
        if input_path.suffix.lower() not in valid_ext:
            return ModuleResult(ModuleStatus.FAILED, f"Unsupported format: {input_path.suffix}")

        context.report(self.name, 20, "Probing video...")
        probe = FFmpegHelper.probe(input_path)
        info = FFmpegHelper.get_video_info(input_path)

        context.probe_data = {**info, "format": probe.get("format", {})}
        context.current_video = input_path

        # Copy to working dir for safe processing
        working_copy = context.get_working_path("input_copy" + input_path.suffix)
        if not working_copy.exists():
            context.report(self.name, 60, "Creating working copy...")
            shutil.copy2(input_path, working_copy)
        context.current_video = working_copy

        context.metadata_log["input"] = {
            "path": str(input_path),
            "size_mb": input_path.stat().st_size / (1024 * 1024),
            **info,
        }

        context.report(self.name, 100, "Preprocessing complete")
        return ModuleResult(ModuleStatus.SUCCESS, "Input validated", {"probe": info})
