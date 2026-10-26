import unittest
from datetime import date, datetime, timezone

import deals

ITEM = {
    "link": "/search/HKG1112KIX1?t=x&search_date=24102026&expected_price=957",
    "departure_at": "2026-12-11T14:45:00+08:00", "price": 957, "airline": "UO",
    "flight_number": "688", "origin_airport": "HKG", "destination_airport": "KIX",
    "gate": "Kiwi.com", "transfers": 0,
}


class DealsTest(unittest.TestCase):
    def test_observed_on_parses_search_date(self):
        self.assertEqual(deals.observed_on(ITEM["link"]), date(2026, 10, 24))
        self.assertIsNone(deals.observed_on("/search/HKG1112KIX1"))

    def test_fresh_deal_has_source_and_times(self):
        now = datetime(2026, 10, 26, 1, tzinfo=timezone.utc)
        deal, why = deals.to_deal(ITEM, "HKG", "OSA", "hkd", True, now, "999")
        self.assertEqual(why, "ok")
        self.assertTrue(deal["source"]["url"].startswith("https://www.aviasales.com/search/"))
        self.assertIn("marker=999", deal["source"]["url"])
        self.assertEqual(deal["observed_on"], "2026-10-24")
        self.assertEqual(deal["fetched_at"], "2026-10-26T01:00:00Z")
        self.assertEqual(deal["trip"], "one_way")

    def test_old_observation_is_dropped(self):
        late = datetime(2026, 10, 24 + deals.MAX_AGE_DAYS + 1, 1, tzinfo=timezone.utc)
        self.assertEqual(deals.to_deal(ITEM, "HKG", "OSA", "hkd", True, late, "")[1], "expired")

    def test_round_trip_needs_return(self):
        now = datetime(2026, 10, 26, 1, tzinfo=timezone.utc)
        self.assertEqual(deals.to_deal(ITEM, "HKG", "OSA", "hkd", False, now, "")[1], "no_return")
        rt = dict(ITEM, return_at="2026-12-15T21:15:00+09:00")
        deal, _ = deals.to_deal(rt, "HKG", "OSA", "hkd", False, now, "")
        self.assertEqual((deal["trip"], deal["return"]), ("round_trip", "2026-12-15"))

    def test_departure_day_expires(self):
        now = datetime(2026, 12, 11, 1, tzinfo=timezone.utc)  # 出發當日已下架
        obs = dict(ITEM, link="/search/x?search_date=09122026")
        self.assertEqual(deals.to_deal(obs, "HKG", "OSA", "hkd", True, now, "")[1], "expired")

    def test_russian_gates_blocked(self):
        now = datetime(2026, 10, 26, 1, tzinfo=timezone.utc)
        for gate in ("Biletix", "Авиасейлс"):
            self.assertEqual(deals.to_deal(dict(ITEM, gate=gate), "HKG", "OSA", "hkd", True, now, "")[1],
                             "blocked_gate")


if __name__ == "__main__":
    unittest.main()
