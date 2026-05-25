"""YOLO face/object detection for content analysis."""

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext


class YOLODetectionModule(BaseModule):
    name = "yolo_detection"
    description = "Detect faces/objects with YOLOv8"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("ai_analysis", default={})
        if not cfg.get("yolo_enabled", True):
            return ModuleResult(ModuleStatus.SKIPPED, "YOLO detection disabled")

        try:
            from ultralytics import YOLO
        except ImportError:
            return ModuleResult(
                ModuleStatus.SKIPPED,
                "YOLO not installed. Run: pip install ultralytics",
            )

        import cv2

        video = str(context.current_video or context.input_path)
        model_name = cfg.get("yolo_model", "yolov8n.pt")
        sample_every = cfg.get("yolo_sample_every", 45)
        blur_faces = cfg.get("yolo_blur_faces", False)

        context.report(self.name, 15, f"Loading YOLO model {model_name}...")
        model = YOLO(model_name)

        cap = cv2.VideoCapture(video)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        face_regions = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % sample_every == 0:
                results = model(frame, verbose=False)
                for r in results:
                    for box in r.boxes:
                        cls_id = int(box.cls[0])
                        name = model.names.get(cls_id, "")
                        if name in ("person", "face"):
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            face_regions.append({
                                "frame": frame_idx,
                                "time": frame_idx / fps,
                                "bbox": [x1, y1, x2 - x1, y2 - y1],
                                "confidence": float(box.conf[0]),
                            })
            frame_idx += 1

        cap.release()
        context.face_regions = face_regions

        if blur_faces and face_regions:
            context.report(self.name, 70, "Applying face blur...")
            output = self._blur_faces(video, face_regions, context, fps, sample_every)
            context.current_video = output

        return ModuleResult(
            ModuleStatus.SUCCESS,
            f"Detected {len(face_regions)} face/person regions",
            {"count": len(face_regions), "blur_applied": blur_faces},
        )

    def _blur_faces(self, video, regions, context, fps, sample_every):
        import cv2
        from app.utils.compat_encode import run_ffmpeg, video_encode_args, audio_encode_args, container_args

        cap = cv2.VideoCapture(video)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        temp = str(context.get_working_path("yolo_blur_raw.mp4"))
        out = context.get_working_path("yolo_blur.mp4")
        writer = cv2.VideoWriter(temp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

        region_by_frame = {}
        for r in regions:
            region_by_frame.setdefault(r["frame"], []).append(r["bbox"])

        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            for bbox in region_by_frame.get(idx, []):
                x, y, bw, bh = bbox
                roi = frame[y:y + bh, x:x + bw]
                if roi.size > 0:
                    blurred = cv2.GaussianBlur(roi, (51, 51), 30)
                    frame[y:y + bh, x:x + bw] = blurred
            writer.write(frame)
            idx += 1

        cap.release()
        writer.release()

        args = [
            "-i", temp, "-i", video,
            "-map", "0:v:0", "-map", "1:a:0?",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            *video_encode_args(23, "fast"),
            *audio_encode_args("192k"),
            *container_args(),
            str(out),
        ]
        run_ffmpeg(args)
        return out
