"""FFmpeg wrapper for video/audio operations."""

import json
import shutil
import subprocess
from pathlib import Path


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class FFmpegHelper:
    @staticmethod
    def probe(input_path: str | Path) -> dict:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(input_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    @staticmethod
    def run(args: list[str], on_progress=None) -> subprocess.CompletedProcess:
        cmd = ["ffmpeg", "-y", *args]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {proc.stderr[-2000:]}")
        return proc

    @staticmethod
    def get_duration(input_path: str | Path) -> float:
        data = FFmpegHelper.probe(input_path)
        return float(data.get("format", {}).get("duration", 0))

    @staticmethod
    def get_video_info(input_path: str | Path) -> dict:
        data = FFmpegHelper.probe(input_path)
        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
            {},
        )
        return {
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "fps": _parse_fps(video_stream.get("r_frame_rate", "30/1")),
            "codec": video_stream.get("codec_name", "unknown"),
            "duration": float(data.get("format", {}).get("duration", 0)),
            "bitrate": int(data.get("format", {}).get("bit_rate", 0)),
        }


def _parse_fps(rate: str) -> float:
    if "/" in rate:
        num, den = rate.split("/")
        return float(num) / float(den) if float(den) else 30.0
    return float(rate)
