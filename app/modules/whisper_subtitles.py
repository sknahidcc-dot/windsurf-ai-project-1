"""Whisper-based subtitle generation (optional dependency)."""

import subprocess
from pathlib import Path

from app.modules.base import BaseModule, ModuleResult, ModuleStatus
from app.pipeline.context import PipelineContext


class WhisperSubtitlesModule(BaseModule):
    name = "whisper_subtitles"
    description = "Generate subtitles with OpenAI Whisper (local)"

    def run(self, context: PipelineContext) -> ModuleResult:
        cfg = context.get_setting("ai_analysis", default={})
        if not cfg.get("whisper_subtitles", True):
            return ModuleResult(ModuleStatus.SKIPPED, "Whisper subtitles disabled")

        try:
            import whisper
        except ImportError:
            return ModuleResult(
                ModuleStatus.SKIPPED,
                "Whisper not installed. Run: pip install openai-whisper",
            )

        video = str(context.current_video or context.input_path)
        model_name = cfg.get("whisper_model", "base")
        language = cfg.get("whisper_language", None)

        context.report(self.name, 10, f"Loading Whisper model '{model_name}'...")

        audio_path = context.get_working_path("whisper_audio.wav")
        subprocess.run([
            "ffmpeg", "-y", "-i", video,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(audio_path),
        ], capture_output=True, check=True)

        model = whisper.load_model(model_name)
        context.report(self.name, 40, "Transcribing audio...")

        options = {"fp16": False}
        if language:
            options["language"] = language

        result = model.transcribe(str(audio_path), **options)
        srt_path = context.get_working_path("subtitles.srt")
        self._write_srt(result["segments"], srt_path)

        context.subtitle_path = srt_path
        context.subtitles = result.get("segments", [])

        return ModuleResult(
            ModuleStatus.SUCCESS,
            f"Generated {len(result.get('segments', []))} subtitle segments",
            {"srt_path": str(srt_path)},
        )

    def _write_srt(self, segments: list, path: Path) -> None:
        lines = []
        for i, seg in enumerate(segments, 1):
            start = self._format_time(seg["start"])
            end = self._format_time(seg["end"])
            text = seg.get("text", "").strip()
            lines.append(f"{i}\n{start} --> {end}\n{text}\n")
        path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _format_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
