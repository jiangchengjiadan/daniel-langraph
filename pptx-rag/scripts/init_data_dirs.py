#!/usr/bin/env python3
"""Initialize data directories for PPTx RAG"""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config


def init_directories():
    """Create all data directories"""
    print("Initializing data directories...")

    directories = [
        config.data_dir,
        config.upload_dir,
        config.images_dir,
        config.chunks_dir,
        config.indexes_dir,
        config.logs_dir,
    ]

    for dir_path in directories:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {dir_path}")

    print("\nAll directories initialized!")


if __name__ == "__main__":
    init_directories()
