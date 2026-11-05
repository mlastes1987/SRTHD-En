"""Local game inputs stay outside version control; no machine-specific defaults."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = Path(os.environ.get('SRW_ORIGINAL_DIR', str(ROOT/'local/original'))).resolve()
RPCS3_DIR = Path(os.environ['SRW_RPCS3_DIR']).resolve() if os.environ.get('SRW_RPCS3_DIR') else None
