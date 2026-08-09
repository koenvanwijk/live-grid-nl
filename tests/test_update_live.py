import importlib.util
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "update_live", Path(__file__).parents[1] / "scripts" / "update_live.py"
)
update_live = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(update_live)


class TennetParsingTests(unittest.TestCase):
    def test_tennet_window_uses_required_format(self):
        start, end = update_live.tennet_window()
        self.assertRegex(start, r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}$")
        self.assertRegex(end, r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}$")

    @patch.object(update_live, "tennet_json")
    def test_metered_strings_are_converted_from_mwh_to_mw(self, get):
        get.return_value = {"Response": {"TimeSeries": [{"Period": {"Points": [{
            "timeInterval_start": "2026-08-09T16:00:00",
            "timeInterval_end": "2026-08-09T16:15:00",
            "measured_infeed": "1700.0",
            "scheduled_export": "-100.0",
            "scheduled_import": "200.0",
        }]}}]}}
        result = update_live.latest_tennet_metered()
        self.assertEqual(result["mw"], 8000.0)
        get.assert_called_once_with(update_live.TENNET_METERED, 23)

    @patch.object(update_live, "tennet_json")
    def test_balance_latest_parses_numeric_strings(self, get):
        get.return_value = {"Response": {"TimeSeries": [{"Period": [{"points": [{
            "timeInterval_start": "2026-08-09T16:00:00",
            "power_afrr_in": "20.5",
            "power_afrr_out": "4.5",
            "power_mari_in": "3.0",
            "power_mari_out": "1.0",
        }]}]}]}}
        result = update_live.latest_tennet_balance()
        self.assertEqual(result["up_mw"], 23.5)
        self.assertEqual(result["down_mw"], 5.5)
        self.assertEqual(result["delta_mw"], 18.0)
        get.assert_called_once_with(update_live.TENNET_BALANCE)


class NedQueryTests(unittest.TestCase):
    @patch.object(update_live, "get_json")
    @patch.object(update_live, "NED_TOKEN", "token-for-test")
    def test_ned_requests_only_latest_record_in_supported_window(self, get):
        get.return_value = {"hydra:member": []}
        update_live.ned_records(0, 2)
        params = get.call_args.args[1]
        self.assertEqual(params["itemsPerPage"], 1)
        self.assertEqual(params["order[validfrom]"], "desc")

    @patch.object(urllib.request, "urlopen")
    def test_http_requests_identify_the_application(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = b"{}"
        response.headers.get_content_charset.return_value = "utf-8"
        update_live.get_json("https://example.test/data", {})
        request = urlopen.call_args.args[0]
        self.assertTrue(request.get_header("User-agent").startswith("live-grid-nl/"))


if __name__ == "__main__":
    unittest.main()
