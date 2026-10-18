"""Simulated LevelDB folders only: these tests prove the copy/retry logic, not real game behaviour."""
import hashlib
import os
import shutil
import struct
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

import snapshot_db
from audit_keys import census, halo_histogram


def digest(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(folder).iterdir()) if p.is_file()}


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='snapshot-test-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.world = self.tmp / 'world'
        (self.world / 'db').mkdir(parents=True)
        (self.world / 'level.dat').write_bytes(b'level')
        (self.world / 'levelname.txt').write_text('Teste')
        for name, data in {'000001.ldb': b'a' * 50, '000002.ldb': b'b' * 50, 'MANIFEST-000003': b'm',
                           'CURRENT': b'MANIFEST-000003\n', '000004.log': b'wal', 'LOCK': b'', 'LOG': b'info'}.items():
            (self.world / 'db' / name).write_bytes(data)

    def run_with_hook(self, hook, **kwargs):
        """Run snapshot() while `hook(call_number)` mutates the source after each file copy."""
        real, calls, attempts = shutil.copy2, [0], [0]
        real_attempt = snapshot_db._attempt

        def copy2(src, dst, *a, **k):
            result = real(src, dst, *a, **k)
            calls[0] += 1
            hook(calls[0], attempts[0])
            return result

        def attempt(*a, **k):
            attempts[0] += 1
            return real_attempt(*a, **k)

        with mock.patch.object(snapshot_db.shutil, 'copy2', copy2), mock.patch.object(snapshot_db, '_attempt', attempt):
            result = snapshot_db.snapshot(self.world, self.tmp / 'snap', delay=0, **kwargs)
        return result, attempts[0]

    def test_copies_needed_files_only_and_leaves_source_untouched(self):
        before = digest(self.world / 'db')
        result = snapshot_db.snapshot(self.world, self.tmp / 'snap')
        self.assertEqual(before, digest(self.world / 'db'))
        self.assertEqual({'000001.ldb', '000002.ldb', 'MANIFEST-000003', 'CURRENT', '000004.log'},
                         set(digest(result / 'db')))
        self.assertTrue((result / 'level.dat').exists())

    def test_growing_wal_is_tolerated_without_retry(self):
        def hook(call, attempt):
            with open(self.world / 'db' / '000004.log', 'ab') as f:
                f.write(b'more')
        _, attempts = self.run_with_hook(hook)
        self.assertEqual(1, attempts)

    def test_compaction_during_copy_triggers_retry_and_final_copy_is_current(self):
        def hook(call, attempt):
            if attempt == 1 and call == 3:  # first attempt, after the first table copy
                (self.world / 'db' / '000001.ldb').unlink()
                (self.world / 'db' / '000005.ldb').write_bytes(b'c' * 50)
        result, attempts = self.run_with_hook(hook)
        self.assertEqual(2, attempts)
        names = set(digest(result / 'db'))
        self.assertIn('000005.ldb', names)
        self.assertNotIn('000001.ldb', names)

    def test_vanished_file_is_retried(self):
        state = {'done': False}
        real_put = snapshot_db._put

        def put(src, dst, link):
            if not state['done']:
                state['done'] = True
                raise FileNotFoundError(src)
            return real_put(src, dst, link)

        with mock.patch.object(snapshot_db, '_put', put):
            result = snapshot_db.snapshot(self.world, self.tmp / 'snap', delay=0)
        self.assertIn('000001.ldb', set(digest(result / 'db')))

    def test_permanent_churn_gives_up_with_clear_error(self):
        counter = [10]

        def hook(call, attempt):
            counter[0] += 1
            (self.world / 'db' / f'0000{counter[0]}.ldb').write_bytes(b'x')
        with self.assertRaises(snapshot_db.SnapshotInconsistent):
            self.run_with_hook(hook, attempts=3)

    def test_refuses_overlap_with_source(self):
        with self.assertRaises(ValueError):
            snapshot_db.snapshot(self.world, self.world / 'inside')
        with self.assertRaises(ValueError):
            snapshot_db.snapshot(self.world, self.world)

    def test_hard_link_mode_shares_inode_when_supported(self):
        result = snapshot_db.snapshot(self.world, self.tmp / 'snap', link=True)
        a, b = os.stat(self.world / 'db' / '000001.ldb'), os.stat(result / 'db' / '000001.ldb')
        if (a.st_ino, a.st_dev) != (b.st_ino, b.st_dev):
            self.skipTest('hard links not supported on this filesystem (fell back to copy)')
        self.assertEqual(a.st_ino, b.st_ino)
        self.assertNotEqual((self.world / 'db' / 'CURRENT').stat().st_ino, (result / 'db' / 'CURRENT').stat().st_ino)


def key(x, z, tag, sub=None, dim=None):
    body = struct.pack('<ii', x, z) + (struct.pack('<i', dim) if dim is not None else b'') + bytes([tag])
    return body + (bytes([sub]) if sub is not None else b'')


class CensusTests(unittest.TestCase):
    def setUp(self):
        self.terrain = {(x, z) for x in range(-3, 4) for z in range(-3, 4) if x * x + z * z <= 9}
        self.halo = {(x, z) for x in range(-9, 10) for z in range(-9, 10)
                     if 9 < x * x + z * z <= 64 and (x, z) not in self.terrain}
        items = []
        for x, z in self.terrain:
            items += [(key(x, z, 47, 4), 900), (key(x, z, 44), 1), (key(x, z, 54), 1)]
        for x, z in self.halo:
            items.append((key(x, z, 49), 2))
        items += [(b'~local_player', 3000), (b'digp' + struct.pack('<ii', 1, 2), 8), (b'Overworld', 10),
                  (key(5, 5, 47, 1, dim=7), 100),  # a custom-dimension chunk record
                  ]
        self.odd = min(self.halo)  # an odd-length key that chunk_record() ignores, sharing x,z with a metadata-only chunk
        items.append((struct.pack('<ii', *self.odd) + bytes([49, 9, 9]), 4))
        self.report = census(items, coord_sample=1000)

    def test_counts_and_unknown_groups(self):
        c = self.report['coordinates']
        self.assertEqual(len(self.terrain), c['with_terrain'])
        self.assertEqual(len(self.halo), c['metadata_only'])
        shapes = {g['shape'] for g in self.report['unrecognized_key_groups']}
        self.assertIn('text:~local_player', shapes)
        self.assertEqual({'7': 1}, self.report['chunk_like_keys_in_other_dimensions'])

    def test_halo_histogram_matches_brute_force(self):
        expected = Counter(min(max(abs(x - tx), abs(z - tz)) for tx, tz in self.terrain) for x, z in self.halo)
        self.assertEqual({str(k): v for k, v in expected.items()}, self.report['halo_distance_histogram']['0'])
        self.assertEqual({'>2': 1}, halo_histogram({(0, 0)}, {(10, 10)}, max_d=2))

    def test_samples_list_every_key_for_the_coordinate(self):
        samples = {(s['x'], s['z']): s['all_keys_for_xz'] for s in self.report['metadata_only_samples']}
        self.assertEqual(self.halo, set(samples))
        self.assertEqual({9, 11}, {k['key_length'] for k in samples[self.odd]})


if __name__ == '__main__':
    unittest.main()
