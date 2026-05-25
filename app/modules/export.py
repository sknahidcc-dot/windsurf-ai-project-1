"""Final export — remux when possible to preserve audio quality."""

from datetime import datetime, timezone
from pathlib import Path

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext
from app.utils.compat_encode import (
    append_maps_and_codecs,
    can_remux_copy,
    container_args,
    even_dimensions_filter,
    has_audio_stream,
    metadata_args,
    run_ffmpeg,
)


class ExportModule(BaseModule):
    name = "export"
    description = "Export final video (stream copy when possible)"

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

        context.report(self.name, 50, "Exporting final video...")
        abr = cfg.get("output_audio_bitrate", "256k")
        meta = None

        if cfg.get("metadata_rewrite", True):
            meta = {
                "title": cfg.get("custom_title", "Processed Video"),
                "artist": cfg.get("custom_artist", "Video Automation Studio"),
                "creation_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            context.metadata_log["export"] = meta

        # Remux without re-encoding — keeps audio crystal clear
        if can_remux_copy(video):
            args = ["-i", str(video), "-map", "0", "-c", "copy"]
            if meta:
                args.extend(metadata_args(meta["title"], meta["artist"], meta["creation_time"]))
            args.extend(container_args())
            args.append(str(final_path))
            run_ffmpeg(args, "Export remux")
        else:
            has_audio = has_audio_stream(video)
            args = ["-i", str(video), "-vf", even_dimensions_filter()]
            append_maps_and_codecs(
                args,
                has_audio=has_audio,
                crf=int(cfg.get("output_crf", 23)),
                preset=cfg.get("output_preset", "medium"),
                audio_bitrate=abr,
            )
            if meta:
                args.extend(metadata_args(meta["title"], meta["artist"], meta["creation_time"]))
            args.extend(container_args())
            args.append(str(final_path))
            run_ffmpeg(args, "Export encode")

        context.output_path = final_path
        context.current_video = final_path

        return ModuleResult(
            ModuleStatus.SUCCESS,
            f"Exported to {final_path}",
            {"output_path": str(final_path), "size_mb": final_path.stat().st_size / (1024 * 1024)},
        )
