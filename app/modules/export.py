"""Final export with compression."""

import subprocess
from pathlib import Path

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext


class ExportModule(BaseModule):
    name = "export"
    description = "Compress and export final video"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("postprocessing", default={})
        export_cfg = context.get_setting("export", default={})

        video = context.current_video or context.input_path
        output_dir = Path(export_cfg.get("output_dir", "output"))
        output_dir.mkdir(parents=True, exist_ok=True)

        suffix = export_cfg.get("filename_suffix", "_processed")
        stem = context.input_path.stem
        ext = context.input_path.suffix or ".mp4"
        final_path = output_dir / f"{stem}{suffix}{ext}"

        if context.output_path:
            final_path = Path(context.output_path)

        context.report(self.name, 50, "Exporting final video...")

        if cfg.get("compress_output", True):
            crf = str(cfg.get("output_crf", 23))
            preset = cfg.get("output_preset", "medium")
            codec = cfg.get("output_codec", "libx264")
            abr = cfg.get("output_audio_bitrate", "192k")

            subprocess.run([
                "ffmpeg", "-y", "-i", str(video),
                "-c:v", codec, "-preset", preset, "-crf", crf,
                "-c:a", "aac", "-b:a", abr,
                "-movflags", "+faststart",
                str(final_path),
            ], capture_output=True, check=True)
        else:
            import shutil
            shutil.copy2(video, final_path)

        context.output_path = final_path
        context.current_video = final_path

        return ModuleResult(
            ModuleStatus.SUCCESS,
            f"Exported to {final_path}",
            {"output_path": str(final_path), "size_mb": final_path.stat().st_size / (1024 * 1024)},
        )
