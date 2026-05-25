from app.modules.scene_detection import SceneDetectionModule
from app.modules.logo_detection import LogoDetectionModule
from app.modules.whisper_subtitles import WhisperSubtitlesModule
from app.modules.yolo_detection import YOLODetectionModule
from app.pipeline.stages.base_stage import BaseStage


class AIAnalysisStage(BaseStage):
    name = "ai_analysis"

    def get_modules(self):
        cfg = self.config.get("ai_analysis", {})
        return [
            SceneDetectionModule(cfg),
            LogoDetectionModule(cfg),
            WhisperSubtitlesModule(cfg),
            YOLODetectionModule(cfg),
        ]
