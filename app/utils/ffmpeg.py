"""FFmpeg wrapper for video/audio operations."""

import json
import os
import shutil
import subprocess
from pathlib import Path


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def safe_path(path: str | Path) -> str:
    """Windows-safe path for ffprobe/ffmpeg (Unicode + long paths)."""
    resolved = Path(path).resolve()
    path_str = str(resolved)
    if os.name == "nt" and not path_str.startswith("\\\\?\\"):
        path_str = "\\\\?\\" + path_str
    return path_str


def run_ffprobe_json(input_path: str | Path) -> dict:
    """Run ffprobe and parse JSON output with proper error handling."""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        safe_path(path),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "unknown error").strip()
        raise RuntimeError(
            f"ffprobe could not read this file.\n"
            f"Try moving the video to a shorter path (e.g. C:\\Videos\\input.mp4).\n"
            f"Details: {err[:400]}"
        )

    raw = result.stdout
    if raw is None or not str(raw).strip():
        raise RuntimeError(
            f"ffprobe returned no data for: {path.name}\n"
            "Try renaming the file to English characters and a shorter path."
        )

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"ffprobe returned invalid JSON: {e}") from e


class FFmpegHelper:
    @staticmethod
    def probe(input_path: str | Path) -> dict:
        return run_ffprobe_json(input_path)

    @staticmethod
    def run(args: list[str], on_progress=None) -> subprocess.CompletedProcess:
        cmd = ["ffmpeg", "-y", *args]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {(proc.stderr or '')[-2000:]}")
        return proc

    @staticmethod
    def get_duration(input_path: str | Path) -> float:
        data = FFmpegHelper.probe(input_path)
        return float(data.get("format", {}).get("duration", 0))

    @staticmethod
    def get_video_info(input_path: str | Path, probe_data: dict | None = None) -> dict:
        data = probe_data or FFmpegHelper.probe(input_path)
        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
            {},
        )
        if not video_stream:
            raise RuntimeError("No video stream found in file")

        bitrate = data.get("format", {}).get("bit_rate", 0)
        return {
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "fps": _parse_fps(video_stream.get("r_frame_rate", "30/1")),
            "codec": video_stream.get("codec_name", "unknown"),
            "duration": float(data.get("format", {}).get("duration", 0)),
            "bitrate": int(bitrate) if bitrate else 0,
            "has_audio": any(
                s.get("codec_type") == "audio" for s in data.get("streams", [])
            ),
        }


def _parse_fps(rate: str) -> float:
    if not rate or rate == "0/0":
        return 30.0
    if "/" in str(rate):
        num, den = str(rate).split("/", 1)
        return float(num) / float(den) if float(den) else 30.0
    return float(rate)
