"""Metadata rewriting and tracking."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext


class MetadataModule(BaseModule):
    name = "metadata"
    description = "Rewrite video metadata for uniqueness"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("postprocessing", default={})
        if not cfg.get("metadata_rewrite", True):
            return ModuleResult(ModuleStatus.SKIPPED, "Metadata rewrite disabled")

        video = context.current_video or context.input_path
        output = context.get_working_path("metadata_video.mp4")

        title = cfg.get("custom_title", "Processed Video")
        artist = cfg.get("custom_artist", "Video Automation Studio")
        creation_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        args = ["-i", str(video), "-c", "copy", "-map", "0"]
        if cfg.get("strip_original_metadata", True):
            args = ["-i", str(video), "-map", "0", "-c", "copy", "-map_metadata", "-1"]

        args.extend([
            "-metadata", f"title={title}",
            "-metadata", f"artist={artist}",
            "-metadata", f"creation_time={creation_time}",
            "-metadata", "encoder=Video Automation Studio v1.0",
            "-metadata", f"comment=Processed {creation_time}",
            str(output),
        ])

        context.report(self.name, 50, "Rewriting metadata...")
        subprocess.run(["ffmpeg", "-y", *args], capture_output=True, check=True)

        context.current_video = output
        context.metadata_log["rewrite"] = {
            "title": title,
            "artist": artist,
            "creation_time": creation_time,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        log_path = context.get_working_path("metadata_log.json")
        log_path.write_text(json.dumps(context.metadata_log, indent=2), encoding="utf-8")

        return ModuleResult(
            ModuleStatus.SUCCESS,
            "Metadata rewritten",
            {"output": str(output), "metadata": context.metadata_log["rewrite"]},
        )
