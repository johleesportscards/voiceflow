"""Load and validate config.yaml with sensible defaults."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

VALID_CLEANUP = {"auto", "claude", "ollama", "lmstudio", "raw"}
VALID_INJECT = {"paste", "type"}
VALID_DEVICE = {"auto", "cuda", "cpu"}


@dataclasses.dataclass
class Config:
    hotkey: str = "right ctrl"
    model: str = "large-v3"
    device: str = "auto"
    language: str = "auto"
    cleanup: str = "auto"
    ollama_model: str = "qwen3:8b"
    ollama_url: str = "http://localhost:11434"
    lmstudio_model: str = ""  # empty = first chat model LM Studio lists
    lmstudio_url: str = "http://localhost:1234"
    inject: str = "paste"
    overlay: bool = True


def load(path: Path = CONFIG_PATH) -> Config:
    cfg = Config()
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for field in dataclasses.fields(Config):
            if field.name in data and data[field.name] is not None:
                setattr(cfg, field.name, data[field.name])

    if cfg.cleanup not in VALID_CLEANUP:
        raise ValueError(f"cleanup must be one of {sorted(VALID_CLEANUP)}, got {cfg.cleanup!r}")
    if cfg.inject not in VALID_INJECT:
        raise ValueError(f"inject must be one of {sorted(VALID_INJECT)}, got {cfg.inject!r}")
    if cfg.device not in VALID_DEVICE:
        raise ValueError(f"device must be one of {sorted(VALID_DEVICE)}, got {cfg.device!r}")
    return cfg
