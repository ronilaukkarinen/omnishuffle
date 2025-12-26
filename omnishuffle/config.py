"""Configuration management for OmniShuffle."""

import os
import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG = {
    "spotify": {
        "client_id": "",
        "client_secret": "",
        "redirect_uri": "http://127.0.0.1:8080",
    },
    "pandora": {
        "email": "",
        "password": "",
        "proxy": "",  # e.g., "socks5://127.0.0.1:9050" for Tor
    },
    "youtube": {
        "auth_file": "",  # Path to ytmusicapi auth file
    },
    "general": {
        "default_mode": "shuffle",  # shuffle, radio
        "sources": ["spotify", "pandora", "youtube"],  # enabled sources
        "volume": 80,
    },
}


def get_config_dir() -> Path:
    """Get config directory, creating if needed."""
    config_dir = Path.home() / ".config" / "omnishuffle"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get path to config file."""
    return get_config_dir() / "config.json"


def load_config() -> Dict[str, Any]:
    """Load config from file, creating default if needed."""
    config_path = get_config_path()

    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
            # Merge with defaults
            merged = DEFAULT_CONFIG.copy()
            for key, value in config.items():
                if key in merged and isinstance(merged[key], dict):
                    merged[key].update(value)
                else:
                    merged[key] = value
            return merged
        except Exception:
            pass

    # Create default config
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    """Save config to file."""
    config_path = get_config_path()
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def update_config(section: str, key: str, value: Any) -> None:
    """Update a config value."""
    config = load_config()
    if section not in config:
        config[section] = {}
    config[section][key] = value
    save_config(config)
