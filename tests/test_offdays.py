"""放假去哪生成器：窗口推導的固定案例（2027 官方假期）。"""
import datetime as dt
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_offdays", ROOT / "tools" / "build_offdays.py")
bo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bo)
H = json.loads((ROOT / "docs" / "data" / "holidays.json").read_text(encoding="utf-8"))
TODAY = dt.date(2026, 11, 9)


def windows(home):
    return {w["id"]: w for w in bo.find_windows(H, home, TODAY, dt.date(2027, 12, 31))}


class WindowTest(unittest.TestCase):
    def test_tw_qingming_is_four_days(self):
        w = windows("TPE")["2027-qingming-tw"]
        self.assertEqual((w["start"], w["end"], w["days"]), (dt.date(2027, 4, 3), dt.date(2027, 4, 6), 4))
        self.assertEqual(w["title"], "清明兒童節")

    def test_hk_easter_bridges_to_qingming(self):
        w = windows("HK")["2027-easter-hk"]
        longest = max(w["leave"], key=lambda o: o["days"])
        self.assertEqual((longest["leave"], longest["days"]), (4, 11))
        self.assertEqual(longest["end"], dt.date(2027, 4, 5))

    def test_single_weekday_holiday_needs_leave(self):
        w = windows("HK")["2027-buddha-hk"]
        self.assertTrue(w["needs_leave"])
        self.assertEqual((w["leave"][0]["leave"], w["leave"][0]["days"]), (1, 4))

    def test_new_year_eve_window_counts_as_next_year(self):
        self.assertIn("2028-newyear-tw", windows("TPE"))

    def test_hk_national_day_avoids_japan(self):
        regions = json.loads((ROOT / "docs/data/regions.json").read_text(encoding="utf-8"))["regions"]
        seasons = json.loads((ROOT / "docs/data/city_seasons.json").read_text(encoding="utf-8"))["cities"]
        events = json.loads((ROOT / "docs/data/seasonal.json").read_text(encoding="utf-8"))["events"]
        go, _, _ = bo.score_cities(windows("HK")["2027-national-hk"], regions, seasons, events, H)
        self.assertFalse({p["city"]["id"] for p in go} & {"tokyo", "kansai", "fukuoka", "hokkaido"})


if __name__ == "__main__":
    unittest.main()
