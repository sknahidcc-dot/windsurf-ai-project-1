"""Audio processing — clarity-first, minimal quality loss."""

import subprocess
from pathlib import Path

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext
from app.utils.compat_encode import (
    audio_encode_args,
    audio_resample_filter,
    can_remux_copy,
    container_args,
    run_ffmpeg,
)


class AudioProcessingModule(BaseModule):
    name = "audio_processing"
    description = "Enhance audio clarity with minimal destructive processing"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("postprocessing", default={})
        video = context.current_video or context.input_path
        output = context.get_working_path("audio_processed.mp4")
        abr = cfg.get("output_audio_bitrate", "256k")

        # Skip all processing — remux only (best quality)
        if cfg.get("audio_preserve_original", False):
            context.report(self.name, 50, "Preserving original audio...")
            self._remux_preserve(video, output, abr)
            context.current_video = output
            return ModuleResult(ModuleStatus.SUCCESS, "Original audio preserved")

        context.report(self.name, 10, "Enhancing audio clarity...")
        af_chain = self._build_filter_chain(cfg)

        if cfg.get("bgm_enabled") and cfg.get("bgm_path"):
            context.report(self.name, 50, "Mixing background music...")
            self._mix_bgm(video, output, cfg, af_chain, abr)
        elif not af_chain:
            context.report(self.name, 40, "Copying audio without filters...")
            self._remux_preserve(video, output, abr)
        else:
            context.report(self.name, 40, "Applying clarity enhancement...")
            self._process_in_one_pass(video, output, af_chain, abr)

        context.current_video = output
        return ModuleResult(ModuleStatus.SUCCESS, "Audio enhanced")

    def _build_filter_chain(self, cfg: dict) -> str | None:
        """
        Build a single gentle FFmpeg audio filter chain.
        Avoids stacked WAV round-trips and destructive loudnorm/NR.
        """
        filters: list[str] = []
        mode = cfg.get("audio_mode", "clear")

        # Always start with high-quality resample
        filters.append(audio_resample_filter())

        if mode == "clear":
            if not (cfg.get("audio_enhance", True) or cfg.get("audio_eq", True)) and not cfg.get(
                "noise_reduction", False
            ) and not cfg.get("audio_fingerprint_shift", False):
                return None
            if cfg.get("audio_enhance", True) or cfg.get("audio_eq", True):
                filters.extend([
                    "highpass=f=60",
                    "equalizer=f=2500:width_type=o:width=1.5:g=1.5",
                    "equalizer=f=200:width_type=o:width=2:g=-1",
                    "acompressor=threshold=-18dB:ratio=2:attack=5:release=80:makeup=1",
                ])
            if cfg.get("noise_reduction", False):
                filters.append("afftdn=nr=4:nf=-50:nt=w")
        elif mode == "enhance":
            if cfg.get("noise_reduction", True):
                filters.append("afftdn=nr=6:nf=-45:nt=w")
            filters.extend([
                "highpass=f=80",
                "equalizer=f=3000:width_type=o:width=1.5:g=2",
                "acompressor=threshold=-20dB:ratio=2.5:attack=5:release=100:makeup=1",
            ])
        elif mode == "fingerprint":
            if cfg.get("noise_reduction", False):
                filters.append("afftdn=nr=4:nf=-50:nt=w")
            semitones = cfg.get("pitch_shift_semitones", 0.15)
            pitch_factor = 2 ** (semitones / 12)
            filters.append(
                f"asetrate=48000*{pitch_factor},aresample=48000:resampler=soxr,"
                f"atempo={1/pitch_factor:.6f}"
            )

        # Legacy toggles (gentle if enabled)
        if cfg.get("audio_fingerprint_shift", False) and mode != "fingerprint":
            semitones = min(cfg.get("pitch_shift_semitones", 0.15), 0.2)
            pitch_factor = 2 ** (semitones / 12)
            filters.append(
                f"asetrate=48000*{pitch_factor},aresample=48000:resampler=soxr,"
                f"atempo={1/pitch_factor:.6f}"
            )

        # Final limiter — prevents clipping, preserves dynamics (NOT loudnorm)
        filters.append("alimiter=limit=0.98:attack=5:release=50")

        # Deduplicate consecutive identical resamples
        chain = ",".join(filters)
        return chain if len(filters) > 1 else None

    def _process_in_one_pass(self, video: Path, output: Path, af_chain: str, abr: str) -> None:
        """One FFmpeg pass: copy video, process audio only."""
        args = [
            "-i", str(video),
            "-map", "0:v:0", "-map", "0:a:0?",
            "-c:v", "copy",
            "-af", af_chain,
            *audio_encode_args(abr),
            "-shortest",
            *container_args(),
            str(output),
        ]
        run_ffmpeg(args, "Audio enhance")

    def _remux_preserve(self, video: Path, output: Path, abr: str) -> None:
        """Copy streams when possible; only encode audio if missing/incompatible."""
        if can_remux_copy(video):
            args = [
                "-i", str(video),
                "-map", "0",
                "-c", "copy",
                *container_args(),
                str(output),
            ]
            run_ffmpeg(args, "Audio remux")
            return

        args = [
            "-i", str(video),
            "-map", "0:v:0", "-map", "0:a:0?",
            "-c:v", "copy",
            *audio_encode_args(abr),
            "-shortest",
            *container_args(),
            str(output),
        ]
        run_ffmpeg(args, "Audio encode")

    def _mix_bgm(self, video: Path, output: Path, cfg: dict, af_chain: str | None, abr: str) -> None:
        """Mix BGM under main audio; optional clarity chain on voice track."""
        bgm_vol = cfg.get("bgm_volume", 0.12)
        voice_chain = af_chain or audio_resample_filter()
        fc = (
            f"[0:a]{voice_chain}[voice];"
            f"[1:a]volume={bgm_vol},aresample=48000:resampler=soxr[bgm];"
            f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2,"
            f"alimiter=limit=0.98[audio]"
        )
        args = [
            "-i", str(video), "-i", str(cfg["bgm_path"]),
            "-filter_complex", fc,
            "-map", "0:v:0", "-map", "[audio]",
            "-c:v", "copy",
            *audio_encode_args(abr),
            "-shortest",
            *container_args(),
            str(output),
        ]
        run_ffmpeg(args, "BGM mix")
