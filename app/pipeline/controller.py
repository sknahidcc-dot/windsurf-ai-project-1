"""
Pipeline Controller - Orchestrates the full video processing workflow.

Execution order:
  Pre-processing -> AI Analysis -> Editing -> Post-processing
"""

import shutil
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from app.pipeline.context import PipelineContext
from app.pipeline.stages import (
    AIAnalysisStage,
    EditingStage,
    PostprocessingStage,
    PreprocessingStage,
)
from app.pipeline.stages.base_stage import StageResult
from app.utils.config_loader import load_config


class PipelineState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineReport:
    state: PipelineState
    input_path: str
    output_path: str | None = None
    stages: list[StageResult] = field(default_factory=list)
    total_duration_sec: float = 0.0
    error: str | None = None


class PipelineController:
    """
    Central controller that manages pipeline execution flow.

    Usage:
        controller = PipelineController()
        report = controller.run("input.mp4", on_progress=callback)
    """

    STAGE_MAP = {
        "preprocessing": PreprocessingStage,
        "ai_analysis": AIAnalysisStage,
        "editing": EditingStage,
        "postprocessing": PostprocessingStage,
    }

    STAGE_ORDER = ["preprocessing", "ai_analysis", "editing", "postprocessing"]

    def __init__(self, config: dict | None = None, config_path: str | Path | None = None):
        self.config = config or load_config(config_path)
        self._cancelled = False
        self.state = PipelineState.IDLE
        self._last_report: PipelineReport | None = None

    def cancel(self) -> None:
        self._cancelled = True

    def run(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        on_progress: Callable[[str, float, str], None] | None = None,
        overrides: dict | None = None,
    ) -> PipelineReport:
        """
        Execute the full pipeline on a single video file.

        Args:
            input_path: Path to raw input video
            output_path: Optional explicit output path
            on_progress: Callback(stage_name, percent_0_100, message)
            overrides: Dict to merge into config for this run

        Returns:
            PipelineReport with results and output path
        """
        start = time.time()
        self._cancelled = False
        self.state = PipelineState.RUNNING

        config = {**self.config, **(overrides or {})}
        input_path = Path(input_path)

        context = PipelineContext(
            input_path=input_path,
            output_path=Path(output_path) if output_path else None,
            config=config,
            on_progress=on_progress,
        )

        enabled = config.get("pipeline", {}).get("enabled_stages", self.STAGE_ORDER)
        stages_results: list[StageResult] = []

        def stage_progress(stage_name: str, pct: float, msg: str) -> None:
            if on_progress:
                stage_idx = self.STAGE_ORDER.index(stage_name) if stage_name in self.STAGE_ORDER else 0
                overall = ((stage_idx + pct / 100) / len(self.STAGE_ORDER)) * 100
                on_progress(stage_name, overall, msg)

        try:
            for stage_name in self.STAGE_ORDER:
                if self._cancelled:
                    self.state = PipelineState.CANCELLED
                    return PipelineReport(
                        state=PipelineState.CANCELLED,
                        input_path=str(input_path),
                        stages=stages_results,
                        error="Pipeline cancelled",
                    )

                if stage_name not in enabled:
                    continue

                stage_cls = self.STAGE_MAP[stage_name]
                stage = stage_cls(config)
                context.report(stage_name, 0, f"Starting {stage_name}...")

                result = stage.execute(context)
                stages_results.append(result)

                if not result.success:
                    self.state = PipelineState.FAILED
                    report = PipelineReport(
                        state=PipelineState.FAILED,
                        input_path=str(input_path),
                        output_path=str(context.output_path) if context.output_path else None,
                        stages=stages_results,
                        total_duration_sec=time.time() - start,
                        error=result.message,
                    )
                    self._last_report = report
                    return report

            self._cleanup_temp(context)
            self.state = PipelineState.COMPLETED

            report = PipelineReport(
                state=PipelineState.COMPLETED,
                input_path=str(input_path),
                output_path=str(context.output_path) if context.output_path else None,
                stages=stages_results,
                total_duration_sec=time.time() - start,
            )
            self._last_report = report
            return report

        except Exception as e:
            self.state = PipelineState.FAILED
            report = PipelineReport(
                state=PipelineState.FAILED,
                input_path=str(input_path),
                stages=stages_results,
                total_duration_sec=time.time() - start,
                error=str(e),
            )
            self._last_report = report
            return report

    def _cleanup_temp(self, context: PipelineContext) -> None:
        if context.working_dir and context.working_dir.exists():
            try:
                shutil.rmtree(context.working_dir, ignore_errors=True)
            except OSError:
                pass

    @property
    def last_report(self) -> PipelineReport | None:
        return self._last_report
