from app.modules.video_editing import VideoEditingModule
from app.pipeline.stages.base_stage import BaseStage


class EditingStage(BaseStage):
    name = "editing"

    def get_modules(self):
        return [VideoEditingModule(self.config.get("editing", {}))]
