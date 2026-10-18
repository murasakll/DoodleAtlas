"""Snapshot of a LevelDB that the game may be writing to. Never writes to the source.

LevelDB table files (.ldb/.sst) are immutable once written; only MANIFEST, CURRENT and
the write-ahead log (.log) change. So: copy tables first, control files next, logs last,
then check that nothing that matters changed, and retry instead of giving up.
A growing .log is tolerated (assumption: LevelDB recovery ignores a partial last record).
"""
import os
import shutil
import time
import json
from pathlib import Path

TABLE_SUFFIXES = ('.ldb', '.sst')
SKIP = {'LOCK', 'LOG', 'LOG.old'}


class SnapshotInconsistent(RuntimeError):
    """The database kept changing in a way that matters; try again later."""


def _listing(folder):
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in folder.iterdir() if p.is_file()}


def _is_table(name):
    return name.endswith(TABLE_SUFFIXES)


def _is_log(name):
    return name.endswith('.log')


def _put(source, target, link):
    if link:
        try:
            os.link(source, target)  # tables are immutable: a hard link costs no disk space
            return
        except OSError:
            pass
    shutil.copy2(source, target)


def _attempt(source, destination, link):
    db, target = source / 'db', destination / 'db'
    first = _listing(db)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    names = [n for n in first if n not in SKIP]
    tables = sorted(n for n in names if _is_table(n))
    logs = sorted(n for n in names if _is_log(n))
    control = sorted(n for n in names if n not in tables and n not in logs)
    for name in tables:
        _put(db / name, target / name, link)
    for name in control:
        shutil.copy2(db / name, target / name)
    for name in logs:
        # Freeze a finite prefix: an actively growing WAL must not extend the copy forever.
        remaining=first[name][0]
        with (db/name).open('rb') as source_log, (target/name).open('wb') as copied:
            while remaining:
                data=source_log.read(min(1024*1024,remaining))
                if not data:raise SnapshotInconsistent('log encolheu durante a cópia')
                copied.write(data);remaining-=len(data)
    second = _listing(db)
    problems = []
    gone = [n for n in tables if n not in second]
    new_tables = [n for n in second if _is_table(n) and n not in first]
    new_logs = [n for n in second if _is_log(n) and n not in first]
    control_changed = [n for n in control if first[n] != second.get(n)]
    if gone:
        problems.append(f'tabelas removidas: {gone[:3]}')
    if any(first[n]!=second.get(n) for n in tables):
        problems.append('tabela alterada durante a cópia')
    if any(n not in second or second[n][0]<first[n][0] for n in logs):
        problems.append('log removido ou truncado')
    if new_tables:
        problems.append(f'tabelas novas: {new_tables[:3]}')
    if new_logs:
        problems.append(f'log rotacionado: {new_logs[:3]}')
    if control_changed:
        problems.append(f'controle alterado: {control_changed[:3]}')
    if problems:
        raise SnapshotInconsistent('; '.join(problems))


def snapshot(source, destination, attempts=5, delay=0.4, link=False):
    """Copy level.dat, levelname.txt and a consistent db/ into a new destination folder."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Snapshot deve ficar separado do mundo original')
    destination.mkdir(parents=True, exist_ok=False)
    for name in ('level.dat', 'levelname.txt'):
        shutil.copy2(source / name, destination / name)
    last = None
    for attempt in range(1, attempts + 1):
        try:
            _attempt(source, destination, link)
            (destination/'.snapshot.json').write_text(json.dumps({'attempts':attempt,'hard_links_requested':link,'wal':'bounded prefix; recovery validated separately'}))
            return destination
        except (SnapshotInconsistent, FileNotFoundError, PermissionError) as exc:
            last = exc
            if attempt < attempts:
                time.sleep(delay * attempt)
    raise SnapshotInconsistent(f'banco mudou durante {attempts} tentativas ({last})')
