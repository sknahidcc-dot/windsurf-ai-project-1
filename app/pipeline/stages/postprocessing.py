from app.modules.audio_processing import AudioProcessingModule
from app.modules.metadata import MetadataModule
from app.modules.export import ExportModule
from app.pipeline.stages.base_stage import BaseStage


class PostprocessingStage(BaseStage):
    name = "postprocessing"

    def get_modules(self):
        cfg = self.config.get("postprocessing", {})
        return [
            AudioProcessingModule(cfg),
            MetadataModule(cfg),
            ExportModule({**self.config.get("postprocessing", {}), **self.config.get("export", {})}),
        ]
