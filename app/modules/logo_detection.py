"""Detect static logos/watermarks in corner regions."""

import cv2
import numpy as np

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext


class LogoDetectionModule(BaseModule):
    name = "logo_detection"
    description = "Detect static watermark/logo regions"

    CORNER_RATIO = 0.18
    SAMPLE_EVERY = 30
    MIN_STATIC_FRAMES = 0.6

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("ai_analysis", default={})
        if not cfg.get("logo_removal_enabled", True):
            return ModuleResult(ModuleStatus.SKIPPED, "Logo detection disabled")

        video = str(context.current_video or context.input_path)
        context.report(self.name, 20, "Scanning for logos/watermarks...")

        regions = self._detect_static_overlays(video)
        context.logo_regions = regions

        return ModuleResult(
            ModuleStatus.SUCCESS,
            f"Found {len(regions)} logo/watermark region(s)",
            {"regions": regions},
        )

    def _detect_static_overlays(self, video: str) -> list[tuple[int, int, int, int]]:
        cap = cv2.VideoCapture(video)
        if not cap.isOpened():
            return []

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

        corner_defs = self._corner_boxes(w, h)
        corner_scores = {i: [] for i in range(len(corner_defs))}

        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % self.SAMPLE_EVERY != 0:
                idx += 1
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            for i, (x, y, cw, ch) in enumerate(corner_defs):
                patch = gray[y:y + ch, x:x + cw]
                if patch.size == 0:
                    continue
                edge = cv2.Canny(patch, 80, 200)
                score = float(np.mean(edge > 0))
                corner_scores[i].append(score)

            idx += 1

        cap.release()

        regions = []
        for i, (x, y, cw, ch) in enumerate(corner_defs):
            scores = corner_scores[i]
            if len(scores) < 3:
                continue
            mean_score = np.mean(scores)
            std_score = np.std(scores)
            # Static overlay: consistent edge activity across frames
            if mean_score > 0.02 and std_score < 0.015:
                pad = 8
                regions.append((
                    max(0, x - pad),
                    max(0, y - pad),
                    min(w - x, cw + 2 * pad),
                    min(h - y, ch + 2 * pad),
                ))

        return self._merge_regions(regions)

    def _corner_boxes(self, w: int, h: int) -> list[tuple[int, int, int, int]]:
        cw = int(w * self.CORNER_RATIO)
        ch = int(h * self.CORNER_RATIO)
        return [
            (0, 0, cw, ch),
            (w - cw, 0, cw, ch),
            (0, h - ch, cw, ch),
            (w - cw, h - ch, cw, ch),
            (w // 2 - cw // 2, 0, cw, ch // 2),
            (w // 2 - cw // 2, h - ch // 2, cw, ch // 2),
        ]

    def _merge_regions(self, regions: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
        if not regions:
            return []
        merged = [regions[0]]
        for x, y, rw, rh in regions[1:]:
            overlap = False
            for mx, my, mw, mh in merged:
                if abs(x - mx) < 50 and abs(y - my) < 50:
                    overlap = True
                    break
            if not overlap:
                merged.append((x, y, rw, rh))
        return merged[:4]
