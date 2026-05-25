"""Base class for all pipeline modules."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModuleStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class ModuleResult:
    status: ModuleStatus
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class BaseModule(ABC):
    name: str = "base"
    description: str = ""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @abstractmethod
    def run(self, context: "PipelineContext") -> ModuleResult:  # noqa: F821
        pass

    def is_enabled(self, context: "PipelineContext") -> bool:  # noqa: F821
        return True
