"""Base class for pipeline stages."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.modules.base import BaseModule, ModuleResult
from app.pipeline.context import PipelineContext


@dataclass
class StageResult:
    name: str
    success: bool
    message: str = ""
    module_results: list[ModuleResult] = field(default_factory=list)


class BaseStage(ABC):
    name: str = "base"
    modules: list[type[BaseModule]] = []

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @abstractmethod
    def get_modules(self) -> list[BaseModule]:
        pass

    def execute(self, context: PipelineContext) -> StageResult:
        results = []
        modules = self.get_modules()

        for i, module in enumerate(modules):
            pct_base = (i / len(modules)) * 100
            context.report(self.name, pct_base, f"Running {module.name}...")

            if not module.is_enabled(context):
                from app.modules.base import ModuleStatus
                results.append(ModuleResult(ModuleStatus.SKIPPED, f"{module.name} skipped"))
                continue

            try:
                result = module.run(context)
                results.append(result)
                if result.status.value == "failed":
                    return StageResult(
                        name=self.name,
                        success=False,
                        message=result.message,
                        module_results=results,
                    )
            except Exception as e:
                from app.modules.base import ModuleStatus
                results.append(ModuleResult(ModuleStatus.FAILED, str(e)))
                return StageResult(
                    name=self.name,
                    success=False,
                    message=f"{module.name} failed: {e}",
                    module_results=results,
                )

        return StageResult(
            name=self.name,
            success=True,
            message=f"{self.name} complete",
            module_results=results,
        )
