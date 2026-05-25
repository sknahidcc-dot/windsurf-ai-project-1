"""Windows Media Player compatible H.264/AAC encoding settings."""

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


def audio_encode_args(bitrate: str = "192k") -> list[str]:
    return [
        "-c:a", "aac",
        "-ar", "48000",
        "-ac", "2",
        "-b:a", bitrate,
    ]


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


def encode_video(
    input_path: Path | str,
    output_path: Path | str,
    *,
    vf_filters: list[str] | None = None,
    af_filters: list[str] | None = None,
    crf: int = 23,
    preset: str = "medium",
    audio_bitrate: str = "192k",
    metadata: dict | None = None,
    extra_inputs: list[str] | None = None,
    filter_complex: str | None = None,
    map_video: str = "0:v:0",
    map_audio: str = "0:a:0?",
) -> None:
    """Re-encode to a Windows-compatible MP4."""
    inputs = ["-i", str(input_path)]
    if extra_inputs:
        for ex in extra_inputs:
            inputs.extend(["-i", str(ex)])

    args = inputs

    if filter_complex:
        args.extend(["-filter_complex", filter_complex])
    else:
        vf = list(vf_filters or [])
        if vf:
            vf.append(even_dimensions_filter())
            args.extend(["-vf", ",".join(vf)])
        elif not vf_filters:
            args.extend(["-vf", even_dimensions_filter()])
        if af_filters:
            args.extend(["-af", ",".join(af_filters)])

    args.extend(["-map", map_video, "-map", map_audio])
    args.extend(video_encode_args(crf, preset))
    args.extend(audio_encode_args(audio_bitrate))

    if metadata:
        args.extend(metadata_args(
            metadata.get("title", "Processed Video"),
            metadata.get("artist", "Video Automation Studio"),
            metadata.get("creation_time", ""),
        ))

    args.extend(container_args())
    args.append(str(output_path))
    run_ffmpeg(args)
