from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InputParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            self.inputs.append(dict(attrs))


class LayerToggleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.app = (ROOT / "app.js").read_text(encoding="utf-8")
        cls.renewables = (ROOT / "data/solar-storage.js").read_text(encoding="utf-8")
        cls.province = (ROOT / "data/province-flow.js").read_text(encoding="utf-8")
        cls.flags = (ROOT / "data/interconnector-flags.js").read_text(encoding="utf-8")
        cls.colors = (ROOT / "data/layer-toggle-colors.css").read_text(encoding="utf-8")
        parser = InputParser()
        parser.feed(cls.html)
        cls.checkboxes = [x for x in parser.inputs if x.get("type") == "checkbox"]

    def test_all_layer_toggles_are_present_and_default_on(self):
        expected_ids = {
            "provinceFlowToggle", "solarToggle", "onshoreWindToggle", "storageToggle",
            "crossBorderToggle", "offshoreToggle", "cableToggle",
        }
        by_id = {x.get("id"): x for x in self.checkboxes if x.get("id")}
        self.assertTrue(expected_ids <= by_id.keys())
        for toggle_id in expected_ids:
            self.assertIn("checked", by_id[toggle_id], toggle_id)

        voltage = {x.get("value") for x in self.checkboxes if x.get("value")}
        self.assertEqual(voltage, {"380 kV", "220 kV", "150 kV", "110 kV"})
        self.assertEqual(len(self.checkboxes), 11)

    def test_no_old_combined_renewables_toggle_remains(self):
        self.assertNotIn("solarStorageToggle", self.html)
        self.assertNotIn("solarStorageToggle", self.renewables)

    def test_each_special_toggle_has_behavior_binding(self):
        for toggle_id in ("solarToggle", "onshoreWindToggle", "storageToggle"):
            self.assertIn(f"#{toggle_id}", self.renewables)
        self.assertIn("addEventListener('change',syncLOD)", self.renewables)

        self.assertIn("#provinceFlowToggle", self.province)
        self.assertIn("addEventListener('change',draw)", self.province)

        self.assertIn("#crossBorderToggle", self.flags)
        self.assertIn("addEventListener('change',sync)", self.flags)

        self.assertIn("#offshoreToggle", self.app)
        self.assertIn("#cableToggle", self.app)
        self.assertIn("document.querySelectorAll('.filters input')", self.app)
        self.assertIn("applyFilters", self.app)

    def test_semantic_colors_match_layer_types(self):
        expected = {
            ".filters .province-flow": "#b56cff",
            ".filters .solar": "#ffd65a",
            ".filters .wind-land": "#62d9ff",
            ".filters .offshore": "#62d9ff",
            ".filters .storage": "#69dff5",
        }
        compact = re.sub(r"\s+", "", self.colors).lower()
        for selector, color in expected.items():
            needle = re.sub(r"\s+", "", selector).lower() + "{"
            start = compact.find(needle)
            self.assertGreaterEqual(start, 0, selector)
            end = compact.find("}", start)
            self.assertIn(color, compact[start:end], selector)

    def test_wind_map_symbols_are_blue_not_green(self):
        compact = re.sub(r"\s+", "", self.colors).lower()
        self.assertIn(".onshore-wind-asset,.onshore-turbine-detail", compact)
        self.assertIn("border-color:#62d9ff!important", compact)
        self.assertIn("background:#bdf3ff!important", compact)


if __name__ == "__main__":
    unittest.main()
