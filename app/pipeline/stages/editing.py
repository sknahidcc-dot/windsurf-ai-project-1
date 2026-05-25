from app.modules.video_editing import VideoEditingModule
from app.modules.intro_outro import IntroOutroModule
from app.modules.watermark_branding import WatermarkBrandingModule
from app.modules.subtitles_burn import SubtitlesBurnModule
from app.pipeline.stages.base_stage import BaseStage


class EditingStage(BaseStage):
    name = "editing"

    def get_modules(self):
        cfg = self.config.get("editing", {})
        return [
            VideoEditingModule(cfg),
            IntroOutroModule(cfg),
            WatermarkBrandingModule(cfg),
            SubtitlesBurnModule(cfg),
        ]
