"""Rebuild the optional seed DLL from pinned MIT sources; no game files touched."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

from chiko.paths import NATIVE as DEST
CUBIOMES='e61f90580cbdd883214a8054670dacae655e59c0'
SEEDFORGE='8cb704bbde7e0de557060be06d51d8305280f11b'
ZIG_URL='https://ziglang.org/download/0.14.1/zig-x86_64-windows-0.14.1.zip'
ZIG_SHA='554f5378228923ffd558eac35e21af020c73789d87afeabf4bfd16f2e6feed2c'

def read(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Chiko-seed-build'})
    with urllib.request.urlopen(req,timeout=90) as response:return response.read()

def main():
    if os.name!='nt':raise SystemExit('This build recipe targets Windows x64.')
    DEST.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chiko-seed-build-') as temporary:
        scratch=Path(temporary).resolve()
        assert scratch.is_relative_to(Path(tempfile.gettempdir()).resolve())
        print('Fetching pinned Cubiomes and SeedForge patches...',flush=True)
        archive=read(f'https://codeload.github.com/Cubitect/cubiomes/tar.gz/{CUBIOMES}')
        with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:tar.extractall(scratch/'source',filter='data')
        source=next((scratch/'source').iterdir())
        patches=f'https://raw.githubusercontent.com/fwsoapy/seedforge/{SEEDFORGE}/'
        patch=scratch/'versions.patch';patch.write_bytes(read(patches+'vendor/patches/versions.patch'))
        for name in ['btree21_5.h','btree262.h','btree263.h']:
            (source/'tables'/name).write_bytes(read(patches+'vendor/patches/'+name))
        subprocess.run(['git','apply','--no-index','--whitespace=nowarn',str(patch)],cwd=source,check=True)
        (DEST/'LICENSE-cubiomes.txt').write_bytes((source/'LICENSE').read_bytes())
        (DEST/'LICENSE-seedforge.txt').write_bytes(read(patches+'LICENSE'))
        for file in source.rglob('*'):
            if file.is_file() and file.suffix in ('.c','.h'):
                target=DEST/'src'/file.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(file.read_bytes())
        (DEST/'versions.patch').write_bytes(patch.read_bytes())
        print('Fetching temporary Zig compiler (82 MB); verifying SHA-256...',flush=True)
        compiler=read(ZIG_URL)
        if hashlib.sha256(compiler).hexdigest()!=ZIG_SHA:raise RuntimeError('Zig checksum mismatch')
        with zipfile.ZipFile(io.BytesIO(compiler)) as zipped:
            for member in zipped.infolist():
                if not (scratch/'compiler'/member.filename).resolve().is_relative_to(scratch/'compiler'):raise RuntimeError('Unsafe compiler archive')
            zipped.extractall(scratch/'compiler')
        del compiler
        zig=next((scratch/'compiler').glob('*/zig.exe'))
        environment=os.environ.copy();environment['ZIG_GLOBAL_CACHE_DIR']=str(scratch/'zig-cache');environment['ZIG_LOCAL_CACHE_DIR']=str(scratch/'zig-local')
        names=['noise','biomes','layers','biomenoise','generator','finders','util','quadbase']
        command=[str(zig),'cc','-shared','-O2','-fwrapv','-DNDEBUG','-target','x86_64-windows-gnu','-I',str(DEST/'src'),str(DEST/'wrapper.c')]
        command += [str(DEST/'src'/(name+'.c')) for name in names]
        command += ['-o',str(scratch/'seed-generator.dll'),'-lm']
        print('Compiling the local seed generator...',flush=True)
        subprocess.run(command,cwd=scratch,env=environment,check=True)
        shutil.copyfile(scratch/'seed-generator.dll',DEST/'seed-generator.dll')
        hashes={str(p.relative_to(DEST)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.rglob('*') if p.is_file() and p.name!='manifest.json'}
        (DEST/'manifest.json').write_text(json.dumps({'cubiomes_commit':CUBIOMES,'seedforge_commit':SEEDFORGE,'zig':'0.14.1','mapping':'Bedrock 26.50 Overworld candidate -> patched MC_26_3; validation required','files':hashes},indent=2)+'\n',encoding='utf-8')
        print('DLL ready. Temporary compiler and build cache are being removed.',flush=True)

if __name__=='__main__':main()
