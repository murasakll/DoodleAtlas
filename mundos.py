"""List worlds or explicitly back up a chosen world; never writes to the source."""
import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def discover():
    roots = [Path(os.environ['LOCALAPPDATA']) / 'Packages' / 'Microsoft.MinecraftUWP_8wekyb3d8bbwe' / 'LocalState' / 'games' / 'com.mojang',
             Path(os.environ['APPDATA']) / 'Minecraft Bedrock']
    worlds = []
    for root in roots:
        if root.exists():
            for name in root.rglob('levelname.txt'):
                if (name.parent / 'db').is_dir():
                    worlds.append({'name':name.read_text(encoding='utf-8').strip(), 'path':str(name.parent)})
    return worlds


def backup(source):
    source = Path(source).resolve()
    if not (source / 'level.dat').is_file() or not (source / 'db').is_dir():
        raise ValueError('Não é um mundo Bedrock')
    target = ROOT / 'data' / 'backups' / (source.name.rstrip('=') + '_' + time.strftime('%Y%m%d_%H%M%S'))
    if source == target or source in target.parents or target in source.parents:
        raise ValueError('Destino deve ser separado da origem')
    shutil.copytree(source, target)
    files = [p for p in source.rglob('*') if p.is_file()]
    for path in files:
        copied = target / path.relative_to(source)
        if hashlib.file_digest(path.open('rb'), 'sha256').digest() != hashlib.file_digest(copied.open('rb'), 'sha256').digest():
            raise RuntimeError('Backup divergente; feche o mundo e repita')
    print(json.dumps({'backup':str(target),'files':len(files),'verified':'SHA-256'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backup', help='Caminho do mundo salvo e fechado')
    args = parser.parse_args()
    if args.backup:
        backup(args.backup)
    else:
        print(json.dumps(discover(), ensure_ascii=False, indent=2))
