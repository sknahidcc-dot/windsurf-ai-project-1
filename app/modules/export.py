"""Final export with Windows-compatible encoding."""

from datetime import datetime, timezone
from pathlib import Path

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext
from app.utils.compat_encode import audio_encode_args, container_args, metadata_args, run_ffmpeg, video_encode_args


class ExportModule(BaseModule):
    name = "export"
    description = "Export final video with compatible H.264/AAC encoding"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("postprocessing", default={})
        export_cfg = context.get_setting("export", default={})

        video = context.current_video or context.input_path
        output_dir = Path(export_cfg.get("output_dir", "output"))
        output_dir.mkdir(parents=True, exist_ok=True)

        suffix = export_cfg.get("filename_suffix", "_processed")
        stem = context.input_path.stem
        final_path = output_dir / f"{stem}{suffix}.mp4"

        if context.output_path:
            final_path = Path(context.output_path)

        context.report(self.name, 50, "Exporting Windows-compatible MP4...")

        crf = str(cfg.get("output_crf", 23))
        preset = cfg.get("output_preset", "medium")
        abr = cfg.get("output_audio_bitrate", "192k")

        args = ["-i", str(video), "-map", "0:v:0", "-map", "0:a:0?"]
        args.extend(["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"])
        args.extend(video_encode_args(int(crf), preset))
        args.extend(audio_encode_args(abr))

        if cfg.get("metadata_rewrite", True):
            title = cfg.get("custom_title", "Processed Video")
            artist = cfg.get("custom_artist", "Video Automation Studio")
            creation_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            args.extend(metadata_args(title, artist, creation_time))
            context.metadata_log["export"] = {
                "title": title, "artist": artist, "creation_time": creation_time,
            }

        args.extend(container_args())
        args.append(str(final_path))

        run_ffmpeg(args, "Export")

        context.output_path = final_path
        context.current_video = final_path

        return ModuleResult(
            ModuleStatus.SUCCESS,
            f"Exported to {final_path}",
            {"output_path": str(final_path), "size_mb": final_path.stat().st_size / (1024 * 1024)},
        )
