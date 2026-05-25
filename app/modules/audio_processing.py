"""Audio: noise reduction, EQ, BGM, fingerprint shift."""

import subprocess
import tempfile
from pathlib import Path

import numpy as np

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext


class AudioProcessingModule(BaseModule):
    name = "audio_processing"
    description = "Audio cleanup, EQ, BGM, fingerprint modification"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("postprocessing", default={})
        video = context.current_video or context.input_path
        output = context.get_working_path("audio_processed.mp4")

        context.report(self.name, 10, "Extracting audio...")
        audio_path = context.get_working_path("extracted_audio.wav")
        subprocess.run([
            "ffmpeg", "-y", "-i", str(video),
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            str(audio_path),
        ], capture_output=True, check=True)

        processed_audio = audio_path

        if cfg.get("noise_reduction", True):
            context.report(self.name, 25, "Reducing noise...")
            processed_audio = self._reduce_noise(processed_audio, context)

        if cfg.get("audio_eq", True):
            context.report(self.name, 45, "Applying EQ...")
            processed_audio = self._apply_eq(processed_audio, context)

        if cfg.get("audio_fingerprint_shift", True):
            context.report(self.name, 60, "Shifting audio fingerprint...")
            processed_audio = self._fingerprint_shift(processed_audio, context, cfg)

        if cfg.get("bgm_enabled") and cfg.get("bgm_path"):
            context.report(self.name, 75, "Mixing background music...")
            processed_audio = self._mix_bgm(processed_audio, context, cfg)

        context.report(self.name, 85, "Merging audio back to video...")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(video),
            "-i", str(processed_audio),
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(output),
        ], capture_output=True, check=True)

        context.current_video = output
        context.current_audio = processed_audio
        return ModuleResult(ModuleStatus.SUCCESS, "Audio processing complete")

    def _reduce_noise(self, audio_path: Path, context: PipelineContext) -> Path:
        try:
            import librosa
            import soundfile as sf

            y, sr = librosa.load(str(audio_path), sr=None)
            # Simple spectral gating noise reduction
            S = np.abs(librosa.stft(y))
            noise_floor = np.percentile(S, 15, axis=1, keepdims=True)
            mask = S > noise_floor * 2.5
            S_clean = S * mask
            y_clean = librosa.istft(S_clean * np.exp(1j * np.angle(librosa.stft(y))))
            out = context.get_working_path("denoised.wav")
            sf.write(str(out), y_clean, sr)
            return out
        except Exception:
            out = context.get_working_path("denoised.wav")
            subprocess.run([
                "ffmpeg", "-y", "-i", str(audio_path),
                "-af", "afftdn=nr=12:nf=-25",
                str(out),
            ], capture_output=True, check=True)
            return out

    def _apply_eq(self, audio_path: Path, context: PipelineContext) -> Path:
        out = context.get_working_path("eq_audio.wav")
        # Multi-band EQ via FFmpeg
        eq_filter = (
            "equalizer=f=100:width_type=o:width=2:g=-2,"
            "equalizer=f=500:width_type=o:width=2:g=1,"
            "equalizer=f=3000:width_type=o:width=2:g=2,"
            "equalizer=f=8000:width_type=o:width=2:g=1,"
            "loudnorm=I=-16:TP=-1.5:LRA=11"
        )
        subprocess.run([
            "ffmpeg", "-y", "-i", str(audio_path),
            "-af", eq_filter,
            str(out),
        ], capture_output=True, check=True)
        return out

    def _fingerprint_shift(self, audio_path: Path, context: PipelineContext, cfg: dict) -> Path:
        """Shift pitch/tempo slightly to alter audio fingerprint."""
        out = context.get_working_path("fingerprint_shifted.wav")
        semitones = cfg.get("pitch_shift_semitones", 0.3)
        # asetrate changes pitch; atempo restores duration
        pitch_factor = 2 ** (semitones / 12)
        new_rate = int(44100 * pitch_factor)
        subprocess.run([
            "ffmpeg", "-y", "-i", str(audio_path),
            "-af", f"asetrate={new_rate},aresample=44100,atempo={1/pitch_factor}",
            str(out),
        ], capture_output=True, check=True)
        return out

    def _mix_bgm(self, audio_path: Path, context: PipelineContext, cfg: dict) -> Path:
        out = context.get_working_path("with_bgm.wav")
        bgm_vol = cfg.get("bgm_volume", 0.15)
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-i", str(cfg["bgm_path"]),
            "-filter_complex",
            f"[1:a]volume={bgm_vol}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2",
            str(out),
        ], capture_output=True, check=True)
        return out
