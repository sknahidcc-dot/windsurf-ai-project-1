"""Shared state passed through the processing pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class PipelineContext:
    input_path: Path
    output_path: Path | None = None
    working_dir: Path | None = None
    config: dict = field(default_factory=dict)

    # Intermediate files (stage outputs)
    current_video: Path | None = None
    current_audio: Path | None = None

    # Analysis results
    probe_data: dict = field(default_factory=dict)
    scene_cuts: list[float] = field(default_factory=list)
    duplicate_segments: list[tuple[float, float]] = field(default_factory=list)
    subtitles: list[dict] = field(default_factory=list)
    subtitle_path: Path | None = None
    logo_regions: list[tuple[int, int, int, int]] = field(default_factory=list)
    face_regions: list[dict] = field(default_factory=list)
    metadata_log: dict = field(default_factory=dict)

    # Progress callback: (stage_name, percent, message)
    on_progress: Callable[[str, float, str], None] | None = None

    def report(self, stage: str, percent: float, message: str) -> None:
        if self.on_progress:
            self.on_progress(stage, percent, message)

    def get_working_path(self, filename: str) -> Path:
        if self.working_dir is None:
            self.working_dir = self.input_path.parent / ".video_automation_temp"
        self.working_dir.mkdir(parents=True, exist_ok=True)
        return self.working_dir / filename

    def get_setting(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.config
        for i, key in enumerate(keys):
            if not isinstance(node, dict):
                return default
            if i == len(keys) - 1:
                return node.get(key, default)
            node = node.get(key)
            if node is None:
                return default
        return node
