"""Scene cut and duplicate frame detection."""

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext


class SceneDetectionModule(BaseModule):
    name = "scene_detection"
    description = "Detect scene cuts and duplicate segments"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("ai_analysis", default={})
        video = str(context.current_video or context.input_path)
        scene_cuts: list[float] = []
        duplicates: list[tuple[float, float]] = []

        if cfg.get("scene_detection", True):
            context.report(self.name, 20, "Detecting scenes...")
            scene_cuts = self._detect_scenes(
                video,
                threshold=cfg.get("scene_threshold", 27.0),
                min_scene_len=cfg.get("min_scene_len", 15),
            )

        if cfg.get("duplicate_frame_check", True):
            context.report(self.name, 60, "Checking duplicate frames...")
            duplicates = self._find_duplicates(video, cfg.get("duplicate_threshold", 0.95))

        context.scene_cuts = scene_cuts
        context.duplicate_segments = duplicates

        return ModuleResult(
            ModuleStatus.SUCCESS,
            f"Found {len(scene_cuts)} cuts, {len(duplicates)} duplicate segments",
            {"scene_cuts": scene_cuts, "duplicates": duplicates},
        )

    def _detect_scenes(self, video: str, threshold: float, min_scene_len: int) -> list[float]:
        try:
            from scenedetect import detect, ContentDetector, AdaptiveDetector

            scene_list = detect(
                video,
                ContentDetector(threshold=threshold, min_scene_len=min_scene_len),
                show_progress=False,
            )
            cuts = []
            for scene in scene_list:
                cuts.append(scene[0].get_seconds())
            return cuts[1:] if len(cuts) > 1 else cuts
        except ImportError:
            return self._opencv_scene_detect(video, threshold)

    def _opencv_scene_detect(self, video: str, threshold: float) -> list[float]:
        import cv2

        cap = cv2.VideoCapture(video)
        cuts = []
        prev_hist = None
        frame_idx = 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 30

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist = cv2.normalize(hist, hist).flatten()

            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
                if diff > threshold / 100.0:
                    cuts.append(frame_idx / fps)

            prev_hist = hist
            frame_idx += 1

        cap.release()
        return cuts

    def _find_duplicates(self, video: str, threshold: float) -> list[tuple[float, float]]:
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(video)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        duplicates = []
        prev_frame = None
        dup_start = None
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            small = cv2.resize(frame, (64, 64))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).flatten().astype(np.float32)
            gray /= np.linalg.norm(gray) + 1e-8

            if prev_frame is not None:
                sim = float(np.dot(prev_frame, gray))
                t = frame_idx / fps
                if sim >= threshold:
                    if dup_start is None:
                        dup_start = t - 1 / fps
                elif dup_start is not None:
                    duplicates.append((dup_start, t))
                    dup_start = None

            prev_frame = gray
            frame_idx += 1

        cap.release()
        if dup_start is not None:
            duplicates.append((dup_start, frame_idx / fps))
        return duplicates
