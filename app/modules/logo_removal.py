"""Remove detected logos/watermarks via inpainting."""

import cv2
import numpy as np

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext
from app.utils.compat_encode import run_ffmpeg, video_encode_args, audio_encode_args, container_args


class LogoRemovalModule(BaseModule):
    name = "logo_removal"
    description = "Remove logos, signatures, watermarks"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("editing", default={})
        if not cfg.get("logo_removal_enabled", True):
            return ModuleResult(ModuleStatus.SKIPPED, "Logo removal disabled")

        regions = getattr(context, "logo_regions", []) or []
        manual = cfg.get("manual_logo_regions", []) or []
        all_regions = list(regions) + [tuple(r) for r in manual]

        if not all_regions:
            return ModuleResult(ModuleStatus.SKIPPED, "No logo regions to remove")

        video = str(context.current_video or context.input_path)
        output = context.get_working_path("logo_removed.mp4")

        context.report(self.name, 30, f"Removing {len(all_regions)} overlay region(s)...")

        cap = cv2.VideoCapture(video)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        temp_video = str(context.get_working_path("logo_removed_raw.mp4"))
        writer = cv2.VideoWriter(temp_video, fourcc, fps, (w, h))

        mask = np.zeros((h, w), dtype=np.uint8)
        for x, y, rw, rh in all_regions:
            x2, y2 = min(w, x + rw), min(h, y + rh)
            cv2.rectangle(mask, (x, y), (x2, y2), 255, -1)

        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            cleaned = cv2.inpaint(frame, mask, 5, cv2.INPAINT_TELEA)
            writer.write(cleaned)
            frame_count += 1
            if frame_count % 100 == 0:
                context.report(self.name, 30 + min(50, frame_count / 300), "Inpainting frames...")

        cap.release()
        writer.release()

        # Re-encode to compatible H.264 (mp4v temp is not Windows-friendly)
        args = [
            "-i", temp_video,
            "-i", video,
            "-map", "0:v:0", "-map", "1:a:0?",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            *video_encode_args(23, "fast"),
            *audio_encode_args("192k"),
            *container_args(),
            str(output),
        ]
        run_ffmpeg(args, "Logo removal encode")

        context.current_video = output
        return ModuleResult(ModuleStatus.SUCCESS, f"Removed {len(all_regions)} overlay(s)")
