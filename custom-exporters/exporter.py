#!/usr/bin/env python3
"""
NHN Cloud Custom Prometheus Exporter (entry point).

Run with:
  python exporter.py
  python -m nhncloud_exporter
  nhncloud-exporter   # after: pip install .
"""

import sys
from pathlib import Path

# src layout: allow running without install (e.g. python exporter.py from repo root)
_root = Path(__file__).resolve().parent
_src = _root / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from nhncloud_exporter.main import main

if __name__ == "__main__":
    main()
