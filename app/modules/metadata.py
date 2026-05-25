"""Metadata tracking (applied during final export)."""

import json
from datetime import datetime, timezone

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext


class MetadataModule(BaseModule):
    name = "metadata"
    description = "Prepare metadata for final export (no re-encode)"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("postprocessing", default={})
        if not cfg.get("metadata_rewrite", True):
            return ModuleResult(ModuleStatus.SKIPPED, "Metadata rewrite disabled")

        title = cfg.get("custom_title", "Processed Video")
        artist = cfg.get("custom_artist", "Video Automation Studio")
        creation_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        context.metadata_log["rewrite"] = {
            "title": title,
            "artist": artist,
            "creation_time": creation_time,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        log_path = context.get_working_path("metadata_log.json")
        log_path.write_text(json.dumps(context.metadata_log, indent=2), encoding="utf-8")

        return ModuleResult(ModuleStatus.SUCCESS, "Metadata prepared for export")
