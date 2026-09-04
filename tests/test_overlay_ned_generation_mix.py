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

    def test_ned_load_replaces_headline_but_preserves_tennet_metric(self):
        data = {
            'load_mw': 12558.0,
            'tennet': {'metered_injections': {
                'mw': 12558.02,
                'measured_at': '2026-08-16T23:45',
                'interval_end': '2026-08-17T00:00',
            }},
            'observations': {'system': {}},
            'provenance': {},
        }
        mod.preserve_tennet_transmission_load(data)
        mod.set_ned_load_headline(data, 14017.3, '2026-08-17T18:30:00+00:00')
        self.assertEqual(data['load_mw'], 14017.3)
        self.assertEqual(data['tennet_transmission_load_mw'], 12558.0)
        self.assertEqual(data['observations']['system']['load']['source'], 'NED')
        self.assertEqual(data['observations']['system']['tennet_transmission_load']['source'], 'TenneT')
        self.assertEqual(data['load_mw_measured_at'], '2026-08-17T18:30:00+00:00')

    def test_ned_becomes_national_headline_and_entso_is_reference(self):
        data = {
            'national_balance_source': 'ENTSO-E aligned',
            'balance_timestamp': '2026-09-04T12:00:00+00:00',
            'load_mw': 11151.1,
            'generation_mw': 6437.1,
            'net_import_mw': 617.9,
            'balance_residual_mw': 4096.1,
            'observations': {'system': {}},
        }
        ok = mod.apply_ned_national_headline(
            data, 14929.5, '2026-09-04T12:45:00+00:00',
            19609.8, '2026-09-04T12:45:00+00:00',
        )
        self.assertTrue(ok)
        self.assertEqual(data['load_mw'], 14929.5)
        self.assertEqual(data['generation_mw'], 19609.8)
        self.assertEqual(data['entso_load_mw'], 11151.1)
        self.assertEqual(data['entso_generation_mw'], 6437.1)
        self.assertEqual(data['entso_balance_residual_mw'], 4096.1)
        self.assertIsNone(data['balance_residual_mw'])
        self.assertIsNone(data['balance_timestamp'])
        self.assertEqual(data['expected_net_export_mw'], 4680.3)
        self.assertEqual(data['entso_physical_net_export_mw'], -617.9)
        self.assertEqual(data['cross_border_balance_gap_mw'], 5298.2)
        self.assertEqual(data['observations']['system']['load']['source'], 'NED')
        self.assertEqual(data['observations']['system']['generation']['source'], 'NED')
        self.assertTrue(data['national_balance_source'].startswith('NED national totals'))


if __name__ == '__main__':
    unittest.main()
