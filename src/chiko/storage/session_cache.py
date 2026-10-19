"""Only generated session files are disposable. Backups and worlds are excluded."""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

MARKER='bedrock-live-map-session-v2'
LEGACY='bedrock-live-map-session-v1'

def preserve_legacy(parent):
    """Protect pre-migration sessions, including against an already running v1 watcher."""
    for marker in Path(parent).glob('session-*/.session.json'):
        try:
            value=json.loads(marker.read_text())
            if value.get('owner')!=LEGACY:continue
            value.update(owner='bedrock-live-map-preserved-v1',original_owner=LEGACY,preserved=True)
            temporary=marker.with_suffix('.json.tmp');temporary.write_text(json.dumps(value));temporary.replace(marker)
        except (OSError,ValueError):pass

def process_alive(pid):
    if os.name=='nt':
        import ctypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.OpenProcess(0x100000,False,pid)
        if not handle:return ctypes.get_last_error()!=87
        try:return kernel.WaitForSingleObject(handle,0)==258
        finally:kernel.CloseHandle(handle)
    return Path(f'/proc/{pid}').exists()


def remove_session(path, parent):
    path,parent=Path(path).resolve(),Path(parent).resolve()
    if path.parent!=parent or not path.name.startswith('session-'):
        raise ValueError('Destino não é uma pasta de sessão autorizada')
    marker=path/'.session.json'
    if not marker.is_file() or json.loads(marker.read_text()).get('owner')!=MARKER:
        raise ValueError('Marcador de sessão ausente')
    shutil.rmtree(path)


class SessionCache:
    def __init__(self, parent):
        self.parent=Path(parent).resolve()
        self.parent.mkdir(parents=True,exist_ok=True)
        preserve_legacy(self.parent)
        self.guard=None
        # Recover only marked sessions whose owning process is gone (e.g. power loss).
        for old in self.parent.glob('session-*'):
            try:
                metadata=json.loads((old/'.session.json').read_text())
                if metadata.get('owner')==MARKER and not process_alive(int(metadata['pid'])):
                    remove_session(old,self.parent)
            except (OSError,ValueError,KeyError):pass
        self.path=self.parent/('session-'+uuid.uuid4().hex)
        self.path.mkdir()
        (self.path/'.session.json').write_text(json.dumps({'owner':MARKER,'pid':os.getpid()}))
        (self.path/'logs').mkdir()

    def watch(self):
        # Detached watcher survives closing the server's console. It holds a process
        # handle, so reuse of a PID cannot make it monitor an unrelated process.
        flags=(subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0
        self.guard=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),str(os.getpid()),str(self.path)],
                         stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         creationflags=flags,close_fds=True)

    def close(self):
        if self.path.exists():
            remove_session(self.path,self.parent)
        if self.guard and self.guard.poll() is None:
            self.guard.terminate()
            self.guard.wait(timeout=5)


if __name__=='__main__':
    import ctypes
    pid,path=int(sys.argv[1]),Path(sys.argv[2])
    if os.name=='nt':
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.OpenProcess(0x100000,False,pid)
        if handle:
            kernel.WaitForSingleObject(handle,0xffffffff)
            kernel.CloseHandle(handle)
    else:
        while Path(f'/proc/{pid}').exists():
            time.sleep(1)
    for _ in range(30):
        try:
            if path.exists():
                remove_session(path,path.parent)
            break
        except (OSError,ValueError):
            time.sleep(1)
