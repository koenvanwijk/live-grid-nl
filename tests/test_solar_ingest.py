import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    'update_solar_parks', Path(__file__).parents[1] / 'scripts' / 'update_solar_parks.py'
)
solar = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(solar)


class SolarParsingTests(unittest.TestCase):
    def test_capacity_kw_is_converted_to_mw(self):
        self.assertEqual(solar.capacity_mw('25000', 'Vermogen_kWp'), 25.0)

    def test_capacity_mw_is_kept_as_mw(self):
        self.assertEqual(solar.capacity_mw('25,5', 'Vermogen MWp'), 25.5)

    def test_colocated_records_are_aggregated_before_threshold(self):
        rows = [
            {'lat': 52.0, 'lon': 5.0, 'mw': 15.0, 'name': 'Park A', 'municipality': 'Test', 'province': 'Utrecht'},
            {'lat': 52.001, 'lon': 5.001, 'mw': 12.0, 'name': 'Park A', 'municipality': 'Test', 'province': 'Utrecht'},
        ]
        parks = solar.aggregate(rows)
        self.assertEqual(len(parks), 1)
        self.assertEqual(parks[0]['capacity_mwp'], 27.0)
        self.assertEqual(parks[0]['subsidy_records'], 2)
        self.assertEqual(parks[0]['source'], 'ROM3D Zon op Kaart')

    def test_different_municipalities_are_not_merged(self):
        rows = [
            {'lat': 52.0, 'lon': 5.0, 'mw': 20.0, 'name': 'A', 'municipality': 'One', 'province': 'Utrecht'},
            {'lat': 52.0001, 'lon': 5.0001, 'mw': 20.0, 'name': 'B', 'municipality': 'Two', 'province': 'Utrecht'},
        ]
        self.assertEqual(solar.aggregate(rows), [])


if __name__ == '__main__':
    unittest.main()
