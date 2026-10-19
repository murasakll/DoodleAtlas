import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from chiko.storage.observed_points import ObservedPoints,extract_points,point_kind,DETECTOR_VERSION


class ObservedPointTests(unittest.TestCase):
    def chunk(self,blocks,palette):
        class Blocks:
            sub_chunks=(3,)
            def get_sub_chunk(self,sy):return blocks
        return SimpleNamespace(blocks=Blocks(),block_palette=[SimpleNamespace(namespaced_name=n) for n in palette])

    def test_hidden_bed_and_full_portal_under_roof_are_found(self):
        blocks=np.zeros((16,16,16),dtype=np.uint16)
        blocks[:,15,:]=1
        blocks[4,2,5]=2;blocks[5,2,5]=2
        blocks[8,2:5,9]=3
        points=extract_points(self.chunk(blocks,['minecraft:air','minecraft:oak_planks','minecraft:red_bed','minecraft:portal']),0,-1,2)
        self.assertEqual(5,len(points));self.assertIn(['bed',0,-12,50,37],points)
        self.assertEqual(3,sum(p[0]=='nether_portal' for p in points))

    def test_namespace_and_frame_are_not_a_portal(self):
        for name in ('minecraft:obsidian','minecraft:end_portal_frame','minecraft:bedrock','addon:bed'):
            self.assertIsNone(point_kind(name))
        self.assertEqual('end_portal',point_kind('minecraft:end_portal'))

    def test_cross_chunk_grouping_dimensions_persistence_and_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'points.sqlite';store=ObservedPoints(path)
            store.put(0,0,0,'one',[['bed',0,15,64,0],['nether_portal',0,8,60,8],['nether_portal',0,8,61,8]])
            store.put(0,1,0,'two',[['bed',0,16,64,0]])
            store.put(1,0,0,'three',[['bed',1,15,64,0]])
            before=store.snapshot();self.assertEqual(3,len(before['points']))
            self.assertEqual(16,next(p['x'] for p in before['points'] if p['kind']=='bed' and p['dimension']==0))
            self.assertEqual(before,ObservedPoints(path).snapshot())
            self.assertEqual(DETECTOR_VERSION+':one',store.signatures()[(0,0,0)])
            store.put(0,0,0,'changed',[])
            self.assertFalse(any(p['kind']=='nether_portal' for p in store.snapshot()['points']))
            store.prune({(0,1,0)})
            self.assertEqual(1,store.snapshot()['scanned_chunks']);self.assertEqual(1,len(store.snapshot()['points']))

    def test_empty_chunk_is_checkpointed_without_invented_points(self):
        with tempfile.TemporaryDirectory() as directory:
            store=ObservedPoints(Path(directory)/'points.sqlite');store.put(0,0,0,'unchanged',[])
            self.assertEqual([],store.snapshot()['points']);self.assertEqual(1,store.snapshot()['scanned_chunks'])

