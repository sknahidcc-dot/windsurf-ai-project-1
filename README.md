# Video Automation Studio

Local desktop app for automated video processing. Upload a raw video, run the pipeline, export the result — all on your machine.

## Features

| Category | Capabilities |
|----------|-------------|
| **Video** | Speed change, crop, mirror, color LUT, auto-cut duplicates, scene detection |
| **Content break** | Logo/watermark removal, metadata rewrite, audio fingerprint shift |
| **AI (optional)** | Whisper subtitles, YOLO face detection |
| **Branding** | Intro/outro injection, custom watermark overlay |
| **Audio** | Noise reduction, EQ, BGM mix |
| **Export** | Windows-compatible H.264/AAC MP4 (plays in Media Player) |

## Requirements

- **Python 3.10+**
- **FFmpeg** on system PATH — [Download FFmpeg](https://ffmpeg.org/download.html)
  - Windows: `winget install ffmpeg` or download from gyan.dev builds

## Quick Start

### Windows (easiest)

Double-click **`run.bat`** — it creates a venv, installs dependencies, and launches the app.

### Manual

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
pip install -r requirements-ai.txt   # optional: Whisper + YOLO
python main.py
```

## How to Use

1. Launch the app (`python main.py` or `run.bat`)
2. **Drag & drop** a video onto the drop zone, or click to browse
3. Adjust options (speed, crop, mirror, color filter, audio, metadata)
4. Click **Process Video**
5. When done, click **Open Output Folder** — file is saved as `output/yourvideo_processed.mp4`

## Project Structure

```
video-automation/
├── main.py                 # App entry point
├── run.bat                 # Windows launcher
├── requirements.txt
├── config/settings.yaml    # Default pipeline settings
├── app/
│   ├── ui/main_window.py   # Desktop UI (CustomTkinter)
│   ├── pipeline/
│   │   ├── controller.py   # Pipeline orchestrator
│   │   ├── context.py      # Shared state between stages
│   │   └── stages/         # preprocessing → ai → editing → post
│   ├── modules/            # Individual processors
│   └── utils/              # FFmpeg, config helpers
└── output/                 # Processed videos
```

## Pipeline Flow

```
Input Video
    │
    ▼
┌─────────────────┐
│ Pre-processing  │  Validate, probe metadata, working copy
└────────┬────────┘
         ▼
┌─────────────────┐
│ AI Analysis     │  Scene cuts, duplicate frame detection
└────────┬────────┘
         ▼
┌─────────────────┐
│ Editing         │  Auto-cut, speed, crop, mirror, color LUT
└────────┬────────┘
         ▼
┌─────────────────┐
│ Post-processing │  Audio (noise/EQ/fingerprint/BGM), metadata, export
└────────┬────────┘
         ▼
   output/video_processed.mp4
```

## Configuration

Edit `config/settings.yaml` for defaults:

```yaml
editing:
  speed_change: 1.05      # 5% faster
  crop_percent: 3
  mirror: false
  color_lut: cinematic
  auto_cut: true

postprocessing:
  noise_reduction: true
  audio_eq: true
  audio_fingerprint_shift: true
  metadata_rewrite: true
```

## Optional AI Features

Uncomment in `requirements.txt` for:

- **Whisper** — auto subtitles
- **Ultralytics** — YOLO face/object detection

Then set `ai_analysis.whisper_subtitles: true` in settings.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| FFmpeg not found | Install FFmpeg, restart terminal/app |
| Drag-drop not working | Click browse instead; or `pip install tkinterdnd2` |
| Slow processing | Normal for long videos; use shorter clips to test |
| Import errors | Run `pip install -r requirements.txt` inside venv |
| Video won't play in Media Player | Fixed: export uses H.264 yuv420p + AAC. Re-process with latest version. |
| Whisper/YOLO skipped | Run `pip install -r requirements-ai.txt` and enable in UI |

## License

MIT — use freely for personal projects.
