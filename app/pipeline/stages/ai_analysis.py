from app.modules.scene_detection import SceneDetectionModule
from app.pipeline.stages.base_stage import BaseStage


class AIAnalysisStage(BaseStage):
    name = "ai_analysis"

    def get_modules(self):
        return [SceneDetectionModule(self.config.get("ai_analysis", {}))]
