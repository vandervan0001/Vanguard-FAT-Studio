#!/usr/bin/env python3
"""Source-checkout entry point for the same client shipped in the Python package."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fat_studio.assistant import main  # noqa: E402

raise SystemExit(main())
