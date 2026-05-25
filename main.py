#!/usr/bin/env python3
"""
Video Automation Studio
Local desktop app for automated video processing.

Usage:
    python main.py
"""

import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    from app.ui.main_window import MainWindow

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
