import unittest

from terrain import colour, palette_colour, PALETTE


class Cartographer(unittest.TestCase):
    def test_water_is_cyan_and_missing_stays_transparent(self):
        self.assertEqual((168,230,245,255), colour('minecraft:water'))
        self.assertEqual((0,0,0,0), colour('minecraft:air'))
        self.assertEqual(palette_colour(PALETTE['fallback']), colour('addon:unknown_material'))

    def test_palette_validation_and_no_marker_orange_in_terrain(self):
        for invalid in ('red', '#zzzzzz', '#fff', None):
            with self.assertRaises(ValueError):
                palette_colour(invalid)
        marker=palette_colour(PALETTE['identity']['marker'])
        for value in [*PALETTE['blocks'].values(), *[r['color'] for r in PALETTE['rules']]]:
            self.assertNotEqual(marker, palette_colour(value))
