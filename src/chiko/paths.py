"""Package resources stay read-only; player data lives in CHIKO_HOME."""
import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('CHIKO_HOME', Path.cwd())).expanduser().resolve()
ASSETS = PACKAGE / 'assets'
WEB = PACKAGE / 'web'
PACK = PACKAGE / 'bedrock_pack'
NATIVE = PACKAGE / 'vendor' / 'seed-generator'
SETTINGS = ROOT / 'config' / 'settings.local.json'


def local_path(value, base=ROOT):
    path = Path(os.path.expandvars(str(value))).expanduser()
    return (path if path.is_absolute() else base / path).resolve()
