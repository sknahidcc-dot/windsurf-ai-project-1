"""Video transforms: speed, crop, mirror, color, auto-cut, watermark."""

import subprocess
from pathlib import Path

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext
from app.utils.compat_encode import (
    append_maps_and_codecs,
    audio_resample_filter,
    container_args,
    even_dimensions_filter,
    has_audio_stream,
    run_ffmpeg,
    video_encode_args,
)

# FFmpeg cannot cut segments shorter than this (seconds)
MIN_SEGMENT_DURATION = 0.5


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

        has_audio = has_audio_stream(video)
        vf_filters = self._build_video_filters(context, cfg)
        af_filters = []

        speed = cfg.get("speed_change", 1.0)
        if has_audio and speed and speed != 1.0:
            # atempo valid range 0.5–2.0
            tempo = max(0.5, min(2.0, float(speed)))
            af_filters.append(f"atempo={tempo},{audio_resample_filter()}")

        if vf_filters:
            vf_filters.append(even_dimensions_filter())
        else:
            vf_filters = [even_dimensions_filter()]

        post_cfg = context.get_setting("postprocessing", default={})
        abr = post_cfg.get("output_audio_bitrate", "256k") if isinstance(post_cfg, dict) else "256k"

        args = ["-i", str(video), "-vf", ",".join(vf_filters)]
        if has_audio and af_filters:
            args.extend(["-af", ",".join(af_filters)])

        append_maps_and_codecs(args, has_audio=has_audio, crf=23, preset="medium", audio_bitrate=abr)
        args.extend(container_args())
        args.append(str(output))

        context.report(self.name, 70, "Rendering video edits...")
        run_ffmpeg(args, "Video editing")

        context.current_video = output
        return ModuleResult(ModuleStatus.SUCCESS, "Video editing complete", {"output": str(output)})

    def _apply_auto_cut(self, context: PipelineContext, video: Path, cfg: dict) -> Path:
        """Remove duplicate segments and trim at scene boundaries."""
        context.report(self.name, 30, "Auto-cutting duplicates...")
        duration = context.probe_data.get("duration", 0)
        if not duration:
            from app.utils.ffmpeg import FFmpegHelper
            duration = FFmpegHelper.get_duration(video)

        remove_ranges = self._merge_ranges(list(context.duplicate_segments))
        if not remove_ranges:
            return video

        keep_segments = self._invert_ranges(remove_ranges, duration)
        keep_segments = [
            (round(s, 3), round(e, 3))
            for s, e in keep_segments
            if (e - s) >= MIN_SEGMENT_DURATION
        ]

        if not keep_segments:
            return video

        # Single segment spanning full video — no cut needed
        if len(keep_segments) == 1 and keep_segments[0][0] <= 0.01:
            if keep_segments[0][1] >= duration - 0.5:
                return video

        concat_file = context.get_working_path("concat_list.txt")
        segment_paths = []

        for i, (start, end) in enumerate(keep_segments):
            seg_duration = end - start
            if seg_duration < MIN_SEGMENT_DURATION:
                continue

            seg_path = context.get_working_path(f"segment_{i}.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-i", str(video),
                "-ss", str(start), "-t", str(seg_duration),
                "-c", "copy", "-avoid_negative_ts", "make_zero",
                str(seg_path),
            ], capture_output=True, check=True)
            segment_paths.append(seg_path)

        if not segment_paths:
            return video

        if len(segment_paths) == 1:
            return segment_paths[0]

        with open(concat_file, "w", encoding="utf-8") as f:
            for p in segment_paths:
                f.write(f"file '{p.resolve()}'\n")

        cut_output = context.get_working_path("autocut_video.mp4")
        has_audio = has_audio_stream(video)
        args = ["-f", "concat", "-safe", "0", "-i", str(concat_file), "-vf", even_dimensions_filter()]
        post_cfg = context.get_setting("postprocessing", default={})
        abr = post_cfg.get("output_audio_bitrate", "256k") if isinstance(post_cfg, dict) else "256k"
        append_maps_and_codecs(args, has_audio=has_audio, crf=23, preset="fast", audio_bitrate=abr)
        args.extend(container_args())
        args.append(str(cut_output))
        run_ffmpeg(args, "Auto-cut concat")
        return cut_output

    def _merge_ranges(self, ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Merge overlapping/adjacent remove ranges; drop tiny ranges."""
        if not ranges:
            return []
        sorted_ranges = sorted(ranges, key=lambda r: r[0])
        merged = [sorted_ranges[0]]
        for start, end in sorted_ranges[1:]:
            if end - start < MIN_SEGMENT_DURATION:
                continue
            prev_start, prev_end = merged[-1]
            if start <= prev_end + 0.1:
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))
        return [(s, e) for s, e in merged if (e - s) >= MIN_SEGMENT_DURATION]

    def _invert_ranges(self, remove: list[tuple[float, float]], duration: float) -> list[tuple[float, float]]:
        keep = []
        pos = 0.0
        for start, end in sorted(remove):
            if start > pos and (start - pos) >= MIN_SEGMENT_DURATION:
                keep.append((pos, start))
            pos = max(pos, end)
        if pos < duration and (duration - pos) >= MIN_SEGMENT_DURATION:
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
