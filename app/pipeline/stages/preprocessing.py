from app.modules.preprocessing import PreprocessingModule
from app.pipeline.stages.base_stage import BaseStage


class PreprocessingStage(BaseStage):
    name = "preprocessing"

    def get_modules(self):
        return [PreprocessingModule(self.config.get("preprocessing", {}))]
