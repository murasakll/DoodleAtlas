"""Generate an importable pack; installation belongs to the player."""
import hashlib
import json
import uuid
import zipfile
from pathlib import Path
from chiko.paths import PACK, ROOT, local_path


def build(identifier=None, output=None):
    world_id=''
    manifest=json.loads((PACK/'manifest.json').read_text(encoding='utf-8'))
    if identifier:
        from chiko.world.discovery import discover
        worlds=[w for w in discover() if Path(w['path']).name==identifier]
        if len(worlds)!=1:raise ValueError('Use o identificador listado em: python -m chiko worlds')
        world_id=hashlib.sha256(str(Path(worlds[0]['path']).resolve()).encode()).hexdigest()
        manifest['header']['name']='Chiko - '+worlds[0]['name']
        manifest['header']['uuid']=str(uuid.uuid5(uuid.NAMESPACE_URL,'livemap-pack:'+world_id))
        manifest['modules'][0]['uuid']=str(uuid.uuid5(uuid.NAMESPACE_URL,'livemap-script:'+world_id))
    target=local_path(output) if output else ROOT/'dist'/'Chiko-Universal.mcpack'
    if target.suffix.lower()!='.mcpack':raise ValueError('Use a extensão .mcpack')
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_suffix('.mcpack.tmp')
    # Só empacota. AAAAA, nada de sair instalando isso no save dos outros.
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACK.rglob('*')):
            if not path.is_file():continue
            name=path.relative_to(PACK).as_posix();data=path.read_bytes()
            if name=='manifest.json':data=json.dumps(manifest,ensure_ascii=False).encode('utf-8')
            if name=='scripts/config.js':data=('export const WORLD_ID = '+json.dumps(world_id)+';\n').encode('utf-8')
            archive.writestr(name,data)
    temporary.replace(target)
    return target
