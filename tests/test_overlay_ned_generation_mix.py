import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    'overlay_ned_generation_mix',
    Path(__file__).parents[1] / 'scripts' / 'overlay_ned_generation_mix.py',
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class NedGenerationMixTests(unittest.TestCase):
    def test_current_row_is_accepted_and_converted_to_mw(self):
        now = datetime.now(timezone.utc)
        row = {
            'capacity': 1234000,
            'validfrom': (now - timedelta(minutes=15)).isoformat(),
            'validto': now.isoformat(),
            'lastupdate': now.isoformat(),
        }
        out = mod.to_mix_row(row, 'B19', 'Wind op land', 'modelled')
        self.assertIsNotNone(out)
        self.assertEqual(out['mw'], 1234.0)
        self.assertEqual(out['source'], 'NED')
        self.assertEqual(out['temporal'], 'actual')
        self.assertEqual(out['provenance'], 'modelled')

    def test_stale_row_is_rejected(self):
        now = datetime.now(timezone.utc)
        row = {
            'capacity': 999000,
            'validfrom': (now - timedelta(minutes=mod.MAX_AGE_MINUTES + 10)).isoformat(),
        }
        self.assertIsNone(mod.to_mix_row(row, 'B19', 'Wind op land', 'modelled'))

    def test_negative_generation_is_rejected(self):
        now = datetime.now(timezone.utc)
        row = {'capacity': -1000, 'validfrom': now.isoformat()}
        self.assertIsNone(mod.to_mix_row(row, 'B04', 'Gas', 'derived'))

    def test_expected_ned_types_cover_visible_generation_mix(self):
        mapping = {name: type_id for type_id, _code, name, _prov in mod.NED_TYPES}
        for name in ('Steenkool', 'Gas', 'Kernenergie', 'Zon', 'Wind op zee', 'Afval', 'Overig', 'Wind op land'):
            self.assertIn(name, mapping)
        self.assertEqual(mapping['Wind op land'], 1)
        self.assertEqual(mapping['Zon'], 2)
        self.assertEqual(mapping['Gas'], 18)
        self.assertEqual(mapping['Steenkool'], 19)
        self.assertEqual(mapping['Kernenergie'], 20)


if __name__ == '__main__':
    unittest.main()
