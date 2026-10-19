"""Independent census of EVERY key in a world snapshot (read-only; keeps one small JSON).

Why: audit_current.py compares Amulet with chunk_record(), so both share the same
assumptions about key shapes. This script looks at what chunk_record() does NOT understand
and at what the 'metadata-only' coordinates really contain, without any library's chunk index.
"""
import json
import struct
import tempfile
from collections import Counter, defaultdict
from itertools import takewhile
from pathlib import Path

from chiko.world.coverage import CHUNK_TAGS, chunk_record

TERRAIN_TAGS = {47, 48}
MARKER_TAGS = {44, 118}


def shape(key):
    for known in (b'digp',b'actorprefix'):
        if key.startswith(known):return 'text:'+known.decode('ascii'),len(key)
    prefix = bytes(takewhile(lambda b: 32 <= b < 127, key))
    label = 'text:' + prefix[:16].decode('ascii') if len(prefix) >= 4 else 'binary'
    return label, len(key)


def halo_histogram(terrain, meta, max_d=48):
    """Chebyshev distance from each metadata-only coordinate to the nearest terrain chunk."""
    terrain, meta = set(terrain), set(meta)
    seen, frontier, remaining = set(terrain), set(terrain), set(meta) - terrain
    histogram = Counter()
    for distance in range(1, max_d + 1):
        if not remaining or not frontier:
            break
        following = set()
        for x, z in frontier:
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    cell = (x + dx, z + dz)
                    if cell not in seen:
                        seen.add(cell)
                        following.add(cell)
        found = following & remaining
        if found:
            histogram[str(distance)] = len(found)
            remaining -= found
        frontier = following
    if remaining:
        histogram[f'>{max_d}'] = len(remaining)
    return dict(histogram)


def extent(coords):
    if not coords:
        return None
    xs, zs = [c[0] for c in coords], [c[1] for c in coords]
    return {'x': [min(xs), max(xs)], 'z': [min(zs), max(zs)]}


def census(items, sample=5, coord_sample=10):
    """items: list of (key_bytes, value_length). Returns a JSON-serialisable report."""
    by_tag, records = Counter(), defaultdict(set)
    unknown, examples, odd_dimensions = Counter(), {}, Counter()
    for key, _ in items:
        record = chunk_record(key)
        if record:
            dim, x, z, tag = record
            by_tag[f'{dim}:{tag}'] += 1
            records[(dim, x, z)].add(tag)
            continue
        group = shape(key)
        unknown[group] += 1
        examples.setdefault(group, [])
        if len(examples[group]) < sample:
            examples[group].append(key.hex())
        if len(key) in (13, 14):
            dim = struct.unpack_from('<i', key, 8)[0]
            tag = key[12]
            if tag in CHUNK_TAGS and dim not in (0, 1, 2):
                odd_dimensions[dim] += 1
    terrain = {c for c, tags in records.items() if tags & TERRAIN_TAGS}
    markers = {c for c, tags in records.items() if tags & MARKER_TAGS}
    metadata = set(records) - terrain - markers
    ordered = sorted(metadata)
    step = max(1, len(ordered) // coord_sample)
    chosen = ordered[::step][:coord_sample]
    prefixes = defaultdict(list)
    for dim,x,z in chosen:prefixes[struct.pack('<ii',x,z)].append((dim,x,z))
    samples = defaultdict(list)
    for key, length in items:
        if len(key) >= 9 and key[:8] in prefixes:
            for coord in prefixes[key[:8]]:samples[coord].append({'key_length': len(key), 'tail_hex': key[8:].hex(), 'value_bytes': length})
    halo, extents = {}, {}
    for dim in (0, 1, 2):
        t = [(x, z) for d, x, z in terrain if d == dim]
        m = [(x, z) for d, x, z in metadata if d == dim]
        if t or m:
            halo[str(dim)] = halo_histogram(t, m)
            extents[str(dim)] = {'terrain': extent(t), 'metadata_only': extent(m)}
    return {
        'total_keys': len(items),
        'chunk_keys_by_dimension_tag': dict(sorted(by_tag.items())),
        'coordinates': {'with_terrain': len(terrain), 'marker_only': len(markers - terrain),
                        'metadata_only': len(metadata)},
        'unrecognized_key_groups': [{'shape': g[0], 'length': g[1], 'count': n, 'examples_hex': examples[g]}
                                    for g, n in unknown.most_common(40)],
        'chunk_like_keys_in_other_dimensions': {str(k): v for k, v in odd_dimensions.items()},
        'metadata_only_samples': [{'dim': c[0], 'x': c[1], 'z': c[2], 'all_keys_for_xz': samples[c]} for c in chosen],
        'halo_distance_histogram': halo,
        'extents': extents,
    }


def main():
    from leveldb import LevelDB
    from chiko.storage.snapshot_db import snapshot
    from chiko.paths import ROOT as root
    from chiko.settings import load
    config = load()
    sessions = root / 'data' / 'sessions'
    sessions.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='keys-', dir=sessions) as folder:
        snap = snapshot(config['world'], Path(folder) / 'world')
        db = LevelDB(str(snap / 'db'))
        items = []
        try:
            for key, value in db.iterate():
                items.append((bytes(key), len(value)))
        finally:
            db.close()
    report = census(items)
    (root / 'logs').mkdir(exist_ok=True)
    (root / 'logs' / 'key-census.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('total_keys', 'coordinates', 'chunk_keys_by_dimension_tag',
                                              'halo_distance_histogram', 'chunk_like_keys_in_other_dimensions')}, indent=1))


if __name__ == '__main__':
    main()
