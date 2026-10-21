"""Application version independent of portal branding."""
import json, os
from pathlib import Path
VERSION = '0.3.1'
BUILD_REVISION = os.getenv('GATEARR_BUILD_REVISION', '')
CHANGELOG = json.loads(Path(__file__).with_name('releases.json').read_text())
