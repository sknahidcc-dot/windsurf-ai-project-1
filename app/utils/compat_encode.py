"""Windows Media Player compatible H.264/AAC encoding settings."""

import json
import subprocess
from pathlib import Path


def even_dimensions_filter() -> str:
    """H.264 yuv420p requires even width/height."""
    return "scale=trunc(iw/2)*2:trunc(ih/2)*2"


def video_encode_args(crf: int = 23, preset: str = "medium") -> list[str]:
    return [
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-profile:v", "main",
        "-level", "4.0",
        "-preset", preset,
        "-crf", str(crf),
    ]


def audio_encode_args(bitrate: str = "256k") -> list[str]:
    """AAC encoding — compatible with all standard FFmpeg Windows builds."""
    return [
        "-c:a", "aac",
        "-ar", "48000",
        "-ac", "2",
        "-b:a", bitrate,
    ]


def audio_resample_filter() -> str:
    """Resample audio (no soxr — not available on all Windows FFmpeg builds)."""
    return "aresample=48000"


def container_args() -> list[str]:
    return ["-movflags", "+faststart", "-f", "mp4"]


def metadata_args(title: str, artist: str, creation_time: str) -> list[str]:
    return [
        "-map_metadata", "-1",
        "-metadata", f"title={title}",
        "-metadata", f"artist={artist}",
        "-metadata", f"creation_time={creation_time}",
        "-metadata", "encoder=Video Automation Studio",
    ]


def run_ffmpeg(args: list[str], label: str = "FFmpeg") -> None:
    cmd = ["ffmpeg", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-2500:]
        raise RuntimeError(f"{label} failed: {err}")


def probe_streams(path: Path | str) -> dict:
    """Return video/audio codec info for stream-copy decisions."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
    return {
        "video_codec": video.get("codec_name", ""),
        "pix_fmt": video.get("pix_fmt", ""),
        "audio_codec": audio.get("codec_name", ""),
        "has_audio": audio.get("codec_name") is not None,
    }


def has_audio_stream(path: Path | str) -> bool:
    try:
        return probe_streams(path).get("has_audio", False)
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return False


def can_remux_copy(path: Path | str) -> bool:
    """True if file can be remuxed without re-encode (H.264 + AAC)."""
    try:
        info = probe_streams(path)
        return (
            info.get("video_codec") == "h264"
            and info.get("pix_fmt") == "yuv420p"
            and info.get("audio_codec") in ("aac", "mp4a")
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return False


def append_maps_and_codecs(
    args: list[str],
    *,
    has_audio: bool,
    video_bitrate_mode: bool = True,
    crf: int = 23,
    preset: str = "medium",
    audio_bitrate: str = "256k",
) -> None:
    """Append -map and codec args; use -an when input has no audio."""
    args.extend(["-map", "0:v:0"])
    args.extend(video_encode_args(crf, preset))
    if has_audio:
        args.extend(["-map", "0:a:0"])
        args.extend(audio_encode_args(audio_bitrate))
    else:
        args.append("-an")
