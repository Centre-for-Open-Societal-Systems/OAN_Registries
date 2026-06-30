from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PSeason(TransactionCase):
    def setUp(self):
        super().setUp()
        self.G2PSeasonModel = self.env["g2p.season"]

    def test_01_create_season(self):
        """Test creating a new Season record."""
        season_data = {
            "name": "Test Season",
            "start_gc": date(2024, 8, 4),
            "end_gc": date(2024, 8, 5),
        }
        season = self.G2PSeasonModel.create(season_data)
        self.assertEqual(season.name, "Test Season", "Season name not set correctly")
        self.assertEqual(season.start_gc, date(2024, 8, 4), "Start GC date not set correctly")
        self.assertEqual(season.end_gc, date(2024, 8, 5), "End GC date not set correctly")

    def test_02_onchange_start_gc_sets_start_ec(self):
        """Test onchange method for start_gc updates start_ec correctly."""
        season = self.G2PSeasonModel.create(
            {
                "name": "Test Season",
                "start_gc": date(2024, 8, 4),
            }
        )
        season._compute_start_ec_from_start_gc()
        self.assertEqual(season.start_ec, "2016/11/28", "Start EC date not set correctly based on start GC")

    def test_03_onchange_start_ec_sets_start_gc(self):
        """Test onchange method for start_ec updates start_gc correctly."""
        season = self.G2PSeasonModel.create(
            {
                "name": "Test Season",
                "start_ec": "2016/11/28",
                "end_ec": "2016/11/29",
            }
        )
        season._compute_start_gc_from_start_ec()
        self.assertEqual(
            season.start_gc, date(2024, 8, 4), "Start GC date not set correctly based on start EC"
        )

    def test_04_onchange_end_gc_sets_end_ec(self):
        """Test onchange method for end_gc updates end_ec correctly."""
        season = self.G2PSeasonModel.create(
            {
                "name": "Test Season",
                "start_gc": date(2024, 8, 3),
                "end_gc": date(2024, 8, 4),
            }
        )
        season._compute_end_ec_from_end_gc()
        self.assertEqual(season.end_ec, "2016/11/28", "End EC date not set correctly based on end GC")

    def test_05_onchange_end_ec_sets_end_gc(self):
        """Test onchange method for end_ec updates end_gc correctly."""
        season = self.G2PSeasonModel.create(
            {
                "name": "Test Season",
                "start_ec": "2016/11/27",
                "end_ec": "2016/11/28",
            }
        )
        season._compute_end_gc_from_end_ec()
        self.assertEqual(season.end_gc, date(2024, 8, 4), "End GC date not set correctly based on end EC")

    def test_06_check_start_dates(self):
        with self.assertRaises(ValidationError):
            self.G2PSeasonModel.create(
                {
                    "name": "Test Season",
                    "start_gc": None,
                    "end_gc": date(2024, 12, 31),
                }
            )

    def test_07_check_end_dates(self):
        with self.assertRaises(ValidationError):
            self.G2PSeasonModel.create(
                {
                    "name": "Test Season",
                    "end_gc": None,
                    "start_gc": date(2024, 1, 1),
                }
            )

    def test_08_no_overlap_within_same_year_gc(self):
        """Test that overlapping seasons within the same year are not allowed."""
        self.G2PSeasonModel.create(
            {
                "name": "Season 1",
                "start_gc": date(2024, 1, 1),
                "end_gc": date(2024, 6, 30),
                "year_gc": 2024,
            }
        )
        with self.assertRaises(ValidationError):
            self.G2PSeasonModel.create(
                {
                    "name": "Season 2",
                    "start_gc": date(2024, 5, 1),
                    "end_gc": date(2024, 12, 31),
                    "year_gc": 2024,
                }
            )
