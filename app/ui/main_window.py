"""Main desktop UI - CustomTkinter with drag & drop."""

import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.pipeline.controller import PipelineController, PipelineState
from app.utils.config_loader import load_config
from app.utils.ffmpeg import check_ffmpeg

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    HAS_DND = True
except ImportError:
    HAS_DND = False


class MainWindow(TkinterDnD.Tk if HAS_DND else ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Video Automation Studio")
        self.geometry("900x700")
        self.minsize(800, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.config_data = load_config()
        self.controller = PipelineController(self.config_data)
        self.input_path: Path | None = None
        self.output_path: Path | None = None
        self._processing = False

        self._build_ui()
        self._check_dependencies()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=24, pady=(24, 8), sticky="ew")
        ctk.CTkLabel(
            header,
            text="Video Automation Studio",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).pack(side="left")
        ctk.CTkLabel(
            header,
            text="Local automated video processing",
            font=ctk.CTkFont(size=13),
            text_color="gray60",
        ).pack(side="left", padx=(16, 0))

        # Drop zone
        self.drop_frame = ctk.CTkFrame(self, corner_radius=16, border_width=2, border_color="#3B8ED0")
        self.drop_frame.grid(row=1, column=0, padx=24, pady=12, sticky="ew")
        self.drop_frame.grid_columnconfigure(0, weight=1)

        self.drop_label = ctk.CTkLabel(
            self.drop_frame,
            text="Drag & Drop your video here\nor click to browse",
            font=ctk.CTkFont(size=16),
            height=120,
        )
        self.drop_label.grid(row=0, column=0, padx=40, pady=40)
        self.drop_label.bind("<Button-1>", lambda e: self._browse_file())

        if HAS_DND:
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)

        self.file_label = ctk.CTkLabel(self.drop_frame, text="", font=ctk.CTkFont(size=12), text_color="gray60")
        self.file_label.grid(row=1, column=0, pady=(0, 16))

        # Settings panel
        settings = ctk.CTkScrollableFrame(self, label_text="Processing Options")
        settings.grid(row=2, column=0, padx=24, pady=8, sticky="nsew")
        settings.grid_columnconfigure((0, 1), weight=1)

        edit_cfg = self.config_data.get("editing", {})
        post_cfg = self.config_data.get("postprocessing", {})
        ai_cfg = self.config_data.get("ai_analysis", {})

        self.var_speed = ctk.DoubleVar(value=edit_cfg.get("speed_change", 1.05))
        self.var_crop = ctk.IntVar(value=edit_cfg.get("crop_percent", 3))
        self.var_mirror = ctk.BooleanVar(value=edit_cfg.get("mirror", False))
        self.var_autocut = ctk.BooleanVar(value=edit_cfg.get("auto_cut", True))
        self.var_color = ctk.StringVar(value=edit_cfg.get("color_lut", "cinematic"))
        self.var_logo_remove = ctk.BooleanVar(value=edit_cfg.get("logo_removal_enabled", True))
        self.var_whisper = ctk.BooleanVar(value=ai_cfg.get("whisper_subtitles", False))
        self.var_yolo = ctk.BooleanVar(value=ai_cfg.get("yolo_enabled", False))
        self.var_burn_subs = ctk.BooleanVar(value=edit_cfg.get("burn_subtitles", True))
        self.var_noise = ctk.BooleanVar(value=post_cfg.get("noise_reduction", True))
        self.var_eq = ctk.BooleanVar(value=post_cfg.get("audio_eq", True))
        self.var_fingerprint = ctk.BooleanVar(value=post_cfg.get("audio_fingerprint_shift", True))
        self.var_metadata = ctk.BooleanVar(value=post_cfg.get("metadata_rewrite", True))
        self.var_bgm = ctk.BooleanVar(value=post_cfg.get("bgm_enabled", False))

        self.intro_path: str | None = edit_cfg.get("intro_path")
        self.outro_path: str | None = edit_cfg.get("outro_path")
        self.watermark_path: str | None = edit_cfg.get("watermark_path") or edit_cfg.get("branding_path")

        row = 0
        ctk.CTkLabel(settings, text="Video transforms", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(8, 4)
        )
        row += 1

        ctk.CTkLabel(settings, text="Speed change (1.05 = 5% faster)").grid(row=row, column=0, sticky="w", padx=8)
        ctk.CTkSlider(settings, from_=0.95, to=1.10, variable=self.var_speed, number_of_steps=15).grid(
            row=row, column=1, sticky="ew", padx=8
        )
        row += 1

        ctk.CTkLabel(settings, text="Crop % (each edge)").grid(row=row, column=0, sticky="w", padx=8)
        ctk.CTkSlider(settings, from_=0, to=10, variable=self.var_crop, number_of_steps=10).grid(
            row=row, column=1, sticky="ew", padx=8
        )
        row += 1

        ctk.CTkCheckBox(settings, text="Mirror (horizontal flip)", variable=self.var_mirror).grid(
            row=row, column=0, sticky="w", padx=8, pady=4
        )
        ctk.CTkCheckBox(settings, text="Auto-cut duplicates", variable=self.var_autocut).grid(
            row=row, column=1, sticky="w", padx=8, pady=4
        )
        row += 1

        ctk.CTkLabel(settings, text="Color filter").grid(row=row, column=0, sticky="w", padx=8)
        ctk.CTkOptionMenu(
            settings,
            variable=self.var_color,
            values=["none", "warm", "cool", "cinematic", "vivid", "fade"],
        ).grid(row=row, column=1, sticky="ew", padx=8)
        row += 1

        ctk.CTkLabel(settings, text="AI & content", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(16, 4)
        )
        row += 1

        ctk.CTkCheckBox(settings, text="Remove logos/watermarks", variable=self.var_logo_remove).grid(
            row=row, column=0, sticky="w", padx=8
        )
        ctk.CTkCheckBox(settings, text="Whisper subtitles", variable=self.var_whisper).grid(
            row=row, column=1, sticky="w", padx=8
        )
        row += 1

        ctk.CTkCheckBox(settings, text="YOLO face detection", variable=self.var_yolo).grid(
            row=row, column=0, sticky="w", padx=8
        )
        ctk.CTkCheckBox(settings, text="Burn subtitles", variable=self.var_burn_subs).grid(
            row=row, column=1, sticky="w", padx=8
        )
        row += 1

        ctk.CTkButton(settings, text="Intro video", width=100, command=self._select_intro).grid(
            row=row, column=0, sticky="w", padx=8, pady=4
        )
        ctk.CTkButton(settings, text="Outro video", width=100, command=self._select_outro).grid(
            row=row, column=1, sticky="w", padx=8, pady=4
        )
        row += 1

        self.wm_btn = ctk.CTkButton(settings, text="Branding watermark", width=140, command=self._select_watermark)
        self.wm_btn.grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=4)
        row += 1

        ctk.CTkLabel(settings, text="Audio & metadata", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(16, 4)
        )
        row += 1

        ctk.CTkCheckBox(settings, text="Noise reduction", variable=self.var_noise).grid(row=row, column=0, sticky="w", padx=8)
        ctk.CTkCheckBox(settings, text="Audio EQ", variable=self.var_eq).grid(row=row, column=1, sticky="w", padx=8)
        row += 1

        ctk.CTkCheckBox(settings, text="Audio fingerprint shift", variable=self.var_fingerprint).grid(
            row=row, column=0, sticky="w", padx=8
        )
        ctk.CTkCheckBox(settings, text="Rewrite metadata", variable=self.var_metadata).grid(
            row=row, column=1, sticky="w", padx=8
        )
        row += 1

        ctk.CTkCheckBox(settings, text="Background music", variable=self.var_bgm).grid(
            row=row, column=0, sticky="w", padx=8, pady=4
        )
        self.bgm_btn = ctk.CTkButton(settings, text="Select BGM file", width=120, command=self._select_bgm)
        self.bgm_btn.grid(row=row, column=1, sticky="w", padx=8)
        self.bgm_path: str | None = post_cfg.get("bgm_path")
        row += 1

        # Progress
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.grid(row=3, column=0, padx=24, pady=8, sticky="ew")
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(progress_frame, text="Ready", font=ctk.CTkFont(size=12), text_color="gray60")
        self.status_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=24, pady=(8, 24), sticky="ew")

        self.process_btn = ctk.CTkButton(
            btn_frame, text="Process Video", height=44, font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_processing,
        )
        self.process_btn.pack(side="left", padx=(0, 12))

        self.export_btn = ctk.CTkButton(
            btn_frame, text="Open Output Folder", height=44, fg_color="gray30", hover_color="gray40",
            command=self._open_output_folder, state="disabled",
        )
        self.export_btn.pack(side="left", padx=(0, 12))

        self.cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancel", height=44, fg_color="#8B0000", hover_color="#A52A2A",
            command=self._cancel_processing, state="disabled",
        )
        self.cancel_btn.pack(side="left")

    def _check_dependencies(self):
        if not check_ffmpeg():
            messagebox.showwarning(
                "FFmpeg Required",
                "FFmpeg was not found in your PATH.\n\n"
                "Install FFmpeg from https://ffmpeg.org/download.html\n"
                "and restart the application.",
            )

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select Video",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.m4v"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._set_input(Path(path))

    def _on_drop(self, event):
        data = event.data
        paths = self.tk.splitlist(data) if hasattr(self, "tk") else [data]
        if not paths:
            paths = [p.strip("{}") for p in str(data).split()]
        if paths:
            self._set_input(Path(paths[0]))

    def _set_input(self, path: Path):
        self.input_path = path
        self.file_label.configure(text=f"Selected: {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)")
        self.drop_label.configure(text=path.name)
        self.export_btn.configure(state="disabled")
        self.output_path = None

    def _select_bgm(self):
        path = filedialog.askopenfilename(
            title="Select Background Music",
            filetypes=[("Audio", "*.mp3 *.wav *.aac *.m4a *.ogg"), ("All files", "*.*")],
        )
        if path:
            self.bgm_path = path
            self.bgm_btn.configure(text=Path(path).name[:20])

    def _select_intro(self):
        path = filedialog.askopenfilename(title="Select Intro", filetypes=[("Video", "*.mp4 *.mov *.mkv")])
        if path:
            self.intro_path = path

    def _select_outro(self):
        path = filedialog.askopenfilename(title="Select Outro", filetypes=[("Video", "*.mp4 *.mov *.mkv")])
        if path:
            self.outro_path = path

    def _select_watermark(self):
        path = filedialog.askopenfilename(title="Branding Watermark", filetypes=[("Images", "*.png *.jpg *.webp")])
        if path:
            self.watermark_path = path
            self.wm_btn.configure(text=Path(path).name[:24])

    def _get_overrides(self) -> dict:
        return {
            "ai_analysis": {
                "logo_removal_enabled": self.var_logo_remove.get(),
                "whisper_subtitles": self.var_whisper.get(),
                "yolo_enabled": self.var_yolo.get(),
            },
            "editing": {
                "speed_change": self.var_speed.get(),
                "crop_percent": int(self.var_crop.get()),
                "mirror": self.var_mirror.get(),
                "auto_cut": self.var_autocut.get(),
                "color_lut": self.var_color.get(),
                "logo_removal_enabled": self.var_logo_remove.get(),
                "intro_path": self.intro_path,
                "outro_path": self.outro_path,
                "watermark_path": self.watermark_path,
                "burn_subtitles": self.var_burn_subs.get(),
            },
            "postprocessing": {
                "noise_reduction": self.var_noise.get(),
                "audio_eq": self.var_eq.get(),
                "audio_fingerprint_shift": self.var_fingerprint.get(),
                "metadata_rewrite": self.var_metadata.get(),
                "bgm_enabled": self.var_bgm.get(),
                "bgm_path": self.bgm_path,
            },
        }

    def _start_processing(self):
        if not self.input_path:
            messagebox.showinfo("No Video", "Please select or drop a video file first.")
            return
        if not check_ffmpeg():
            messagebox.showerror("FFmpeg Missing", "Install FFmpeg and add it to your system PATH.")
            return
        if self._processing:
            return

        self._processing = True
        self.process_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.export_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_label.configure(text="Starting pipeline...")

        thread = threading.Thread(target=self._run_pipeline, daemon=True)
        thread.start()

    def _run_pipeline(self):
        def on_progress(stage: str, percent: float, message: str):
            self.after(0, lambda: self._update_progress(stage, percent, message))

        try:
            report = self.controller.run(
                self.input_path,
                on_progress=on_progress,
                overrides=self._get_overrides(),
            )
            self.after(0, lambda: self._on_complete(report))
        except Exception as e:
            self.after(0, lambda: self._on_error(str(e)))

    def _update_progress(self, stage: str, percent: float, message: str):
        self.progress_bar.set(percent / 100)
        self.status_label.configure(text=f"[{stage}] {message}")

    def _on_complete(self, report):
        self._processing = False
        self.process_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")

        if report.state == PipelineState.COMPLETED:
            self.output_path = Path(report.output_path) if report.output_path else None
            self.progress_bar.set(1)
            self.status_label.configure(
                text=f"Done in {report.total_duration_sec:.1f}s — {self.output_path}"
            )
            self.export_btn.configure(state="normal")
            messagebox.showinfo(
                "Processing Complete",
                f"Video exported successfully!\n\n{report.output_path}\n\nDuration: {report.total_duration_sec:.1f}s",
            )
        else:
            self.status_label.configure(text=f"Failed: {report.error}")
            messagebox.showerror("Processing Failed", report.error or "Unknown error")

    def _on_error(self, error: str):
        self._processing = False
        self.process_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.status_label.configure(text=f"Error: {error}")
        messagebox.showerror("Error", error)

    def _cancel_processing(self):
        self.controller.cancel()
        self.status_label.configure(text="Cancelling...")

    def _open_output_folder(self):
        if self.output_path and self.output_path.exists():
            folder = str(self.output_path.parent)
        else:
            folder = str(Path(self.config_data.get("export", {}).get("output_dir", "output")).resolve())
            Path(folder).mkdir(parents=True, exist_ok=True)

        if os.name == "nt":
            os.startfile(folder)
        elif os.name == "posix":
            subprocess.run(["xdg-open", folder], check=False)
