import os
import yaml
from pathlib import Path

DEFAULT_CONFIG_DIR = Path.home() / ".paper-parser"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG = {
    "PAPER_WORKSPACE": str(Path.home() / "paper-parser-workspace"),
    "MINERU_API_TOKEN": "",
    "MINERU_API_BASE_URL": "https://mineru.net/api/v4",
    "MINERU_API_TIMEOUT": 600
}

class Config:
    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        self.config_path = Path(config_path)
        self.data = {}
        self.load()

    def load(self):
        """Load config from YAML file, creating it if it doesn't exist."""
        if not self.config_path.exists():
            self.create_default_config()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.data = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error loading config from {self.config_path}: {e}")
            self.data = {}

        # Merge with defaults for missing keys
        for key, value in DEFAULT_CONFIG.items():
            if key not in self.data:
                self.data[key] = value

    def create_default_config(self):
        """Create the config directory and a default config file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, allow_unicode=True)
            print(f"Created default config at {self.config_path}")
        except Exception as e:
            print(f"Error creating default config: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

# Global config instance
config = Config()
