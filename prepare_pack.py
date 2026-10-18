"""Build a world-bound mcpack in the project; does not install or change a world."""
import argparse
import hashlib
import json
import uuid
import zipfile
from pathlib import Path
from mundos import discover

ROOT=Path(__file__).resolve().parent

def build(identifier):
    worlds=[w for w in discover() if Path(w['path']).name==identifier]
    if len(worlds)!=1:raise ValueError('Use o identificador exato listado por mundos.py')
    world=Path(worlds[0]['path']).resolve()
    world_id=hashlib.sha256(str(world).encode()).hexdigest()
    source=ROOT/'fallback'/'behavior_pack'
    manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    manifest['header']['name']='Bedrock Live Map - '+worlds[0]['name']
    manifest['header']['uuid']=str(uuid.uuid5(uuid.NAMESPACE_URL,'livemap-pack:'+world_id))
    manifest['modules'][0]['uuid']=str(uuid.uuid5(uuid.NAMESPACE_URL,'livemap-script:'+world_id))
    target=ROOT/'fallback'/'BedrockLiveMap.mcpack'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as output:
        for path in source.rglob('*'):
            if not path.is_file():continue
            name=path.relative_to(source).as_posix()
            data=path.read_bytes()
            if name=='manifest.json':data=json.dumps(manifest,ensure_ascii=False).encode()
            if name=='scripts/config.js':data=('export const WORLD_ID = '+json.dumps(world_id)+';\n').encode()
            output.writestr(name,data)
    print('Pacote preparado (ainda não instalado): '+str(target))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('world_id',help='Identificador da pasta do mundo, incluindo =')
    build(parser.parse_args().world_id)
