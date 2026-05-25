"""Load YAML configuration."""

from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"


def load_config(path: Path | str | None = None) -> dict:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return _default_config()
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or _default_config()


def _default_config() -> dict:
    return {
        "pipeline": {"enabled_stages": ["preprocessing", "ai_analysis", "editing", "postprocessing"]},
        "preprocessing": {"validate_input": True},
        "ai_analysis": {"scene_detection": True},
        "editing": {"auto_cut": True, "speed_change": 1.05},
        "postprocessing": {"metadata_rewrite": True},
        "export": {"output_dir": "output", "filename_suffix": "_processed"},
    }
