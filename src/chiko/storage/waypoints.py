"""Small persistent shared annotations; terrain and browser-local points stay separate."""
from contextlib import closing
import math
from pathlib import Path
import sqlite3
import threading
import time
import uuid


class WaypointLimit(ValueError):
    pass


class WaypointStore:
    limit = 1000

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        with closing(self.connect()) as db, db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS points (id TEXT PRIMARY KEY, name TEXT NOT NULL, x REAL NOT NULL, z REAL NOT NULL, dimension INTEGER NOT NULL, created REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS version (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL)')
            db.execute('INSERT OR IGNORE INTO version VALUES (1,0)')
            self.refresh(db)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA max_page_count=4096')  # At default 4 KiB pages: 16 MiB ceiling.
        return db

    def refresh(self, db):
        self.snapshot = {'available': True, 'limit': self.limit,
                         'revision': db.execute('SELECT revision FROM version WHERE id=1').fetchone()[0],
                         'points': [dict(row) for row in db.execute('SELECT * FROM points ORDER BY created,id')]}

    @staticmethod
    def validate(body):
        if not isinstance(body, dict):
            raise ValueError('Anotação inválida')
        name = body.get('name')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60 or any(ord(c) < 32 for c in name):
            raise ValueError('Use um nome entre 1 e 60 caracteres, sem controles')
        values = [body.get('x'), body.get('z')]
        if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 30000000 for v in values):
            raise ValueError('Coordenadas inválidas')
        dim = body.get('dimension')
        if type(dim) is not int or dim not in (0, 1, 2):
            raise ValueError('Dimensão inválida')
        return name.strip(), *values, dim

    def create(self, body):
        name, x, z, dim = self.validate(body)
        point = {'id': uuid.uuid4().hex, 'name': name, 'x': x, 'z': z, 'dimension': dim, 'created': time.time()}
        with self.lock, closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT count(*) FROM points').fetchone()[0] >= self.limit:
                raise WaypointLimit('Limite de 1.000 pontos compartilhados neste mundo')
            db.execute('INSERT INTO points VALUES (:id,:name,:x,:z,:dimension,:created)', point)
            db.execute('UPDATE version SET revision=revision+1 WHERE id=1')
            db.commit()
            self.refresh(db)
        return point

    def delete(self, point_id):
        with self.lock, closing(self.connect()) as db, db:
            if not db.execute('DELETE FROM points WHERE id=?', (point_id,)).rowcount:
                raise KeyError(point_id)
            db.execute('UPDATE version SET revision=revision+1 WHERE id=1')
            db.commit()
            self.refresh(db)
