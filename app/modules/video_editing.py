"""Video transforms: speed, crop, mirror, color, auto-cut, watermark."""

import subprocess
from pathlib import Path

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext


class VideoEditingModule(BaseModule):
    name = "video_editing"
    description = "Apply visual transforms and auto-cut"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("editing", default={})
        video = context.current_video or context.input_path
        output = context.get_working_path("edited_video.mp4")

        context.report(self.name, 10, "Building edit filter chain...")

        if cfg.get("auto_cut", True) and (context.scene_cuts or context.duplicate_segments):
            video = self._apply_auto_cut(context, video, cfg)

        vf_filters = self._build_video_filters(context, cfg)
        af_filters = []

        speed = cfg.get("speed_change", 1.0)
        if speed and speed != 1.0:
            af_filters.append(f"atempo={speed}")

        args = ["-i", str(video)]
        if vf_filters:
            args.extend(["-vf", ",".join(vf_filters)])
        if af_filters:
            args.extend(["-af", ",".join(af_filters)])

        args.extend([
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            str(output),
        ])

        context.report(self.name, 70, "Rendering video edits...")
        subprocess.run(["ffmpeg", "-y", *args], capture_output=True, check=True)

        context.current_video = output
        return ModuleResult(ModuleStatus.SUCCESS, "Video editing complete", {"output": str(output)})

    def _apply_auto_cut(self, context: PipelineContext, video: Path, cfg: dict) -> Path:
        """Remove duplicate segments and trim at scene boundaries."""
        context.report(self.name, 30, "Auto-cutting duplicates...")
        duration = context.probe_data.get("duration", 0)
        if not duration:
            from app.utils.ffmpeg import FFmpegHelper
            duration = FFmpegHelper.get_duration(video)

        remove_ranges = list(context.duplicate_segments)
        if not remove_ranges:
            return video

        keep_segments = self._invert_ranges(remove_ranges, duration)
        if len(keep_segments) <= 1 and keep_segments[0][0] == 0:
            return video

        concat_file = context.get_working_path("concat_list.txt")
        segment_paths = []

        for i, (start, end) in enumerate(keep_segments):
            seg_path = context.get_working_path(f"segment_{i}.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-i", str(video),
                "-ss", str(start), "-to", str(end),
                "-c", "copy", str(seg_path),
            ], capture_output=True, check=True)
            segment_paths.append(seg_path)

        with open(concat_file, "w", encoding="utf-8") as f:
            for p in segment_paths:
                f.write(f"file '{p.resolve()}'\n")

        cut_output = context.get_working_path("autocut_video.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_file), "-c", "copy", str(cut_output),
        ], capture_output=True, check=True)

        return cut_output

    def _invert_ranges(self, remove: list[tuple[float, float]], duration: float) -> list[tuple[float, float]]:
        keep = []
        pos = 0.0
        for start, end in sorted(remove):
            if start > pos:
                keep.append((pos, start))
            pos = max(pos, end)
        if pos < duration:
            keep.append((pos, duration))
        return keep if keep else [(0.0, duration)]

    def _build_video_filters(self, context: PipelineContext, cfg: dict) -> list[str]:
        filters = []

        crop_pct = cfg.get("crop_percent", 0)
        if crop_pct and crop_pct > 0:
            info = context.probe_data
            w = info.get("width", 1920)
            h = info.get("height", 1080)
            margin_w = int(w * crop_pct / 100)
            margin_h = int(h * crop_pct / 100)
            filters.append(f"crop={w - 2 * margin_w}:{h - 2 * margin_h}")

        if cfg.get("mirror", False):
            filters.append("hflip")

        speed = cfg.get("speed_change", 1.0)
        if speed and speed != 1.0:
            filters.append(f"setpts=PTS/{speed}")

        lut = cfg.get("color_lut", "none")
        color_filter = self._get_color_filter(lut)
        if color_filter:
            filters.append(color_filter)

        scale = cfg.get("resolution_scale")
        if scale:
            filters.append(f"scale={scale}")

        wm_path = cfg.get("watermark_path")
        if wm_path and Path(wm_path).exists():
            opacity = cfg.get("watermark_opacity", 0.7)
            pos = cfg.get("watermark_position", "bottom-right")
            overlay = self._watermark_position(pos)
            filters.append(f"movie={wm_path}[wm];[in][wm]overlay={overlay}:format=auto:alpha={opacity}[out]")

        return filters

    def _get_color_filter(self, lut_name: str) -> str | None:
        presets = {
            "warm": "colortemperature=6500,eq=contrast=1.05:saturation=1.1",
            "cool": "colortemperature=9000,eq=contrast=1.05:saturation=0.95",
            "cinematic": "eq=contrast=1.15:brightness=-0.02:saturation=0.9,curves=preset=lighter",
            "vivid": "eq=contrast=1.2:saturation=1.3:brightness=0.02",
            "fade": "eq=brightness=0.05:contrast=0.9:saturation=0.85",
        }
        return presets.get(lut_name)

    def _watermark_position(self, position: str) -> str:
        positions = {
            "top-left": "10:10",
            "top-right": "W-w-10:10",
            "bottom-left": "10:H-h-10",
            "bottom-right": "W-w-10:H-h-10",
            "center": "(W-w)/2:(H-h)/2",
        }
        return positions.get(position, positions["bottom-right"])
