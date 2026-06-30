import datetime

from psycopg2.errors import InvalidDatetimeFormat

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PLiveStockInformation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.farmer = self.env["res.partner"].create({"name": "Test Farmer"})
        self.livestock_type = self.env["g2p.livestock.type"].create(
            {"name": "Test Livestock Type", "code": "TLT"}
        )
        self.disease = self.env["g2p.illness.type"].create(
            {"name": "Test Disease", "code": "TD", "illness_type": "animal"}
        )
        self.season_gc = self.env["g2p.season"].create(
            {"name": "Test Season GC", "start_gc": "2020-01-01", "end_gc": "2020-12-31"}
        )
        self.season_ec = self.env["g2p.season"].create(
            {"name": "Test Season EC", "start_ec": "2016-01-01", "end_ec": "2016-12-31"}
        )

    def test_01_create_live_stock_information(self):
        """Test creating a new Live Stock Information record."""
        live_stock_info_data = {
            "partner_id": self.farmer.id,
            "livestock_type": self.livestock_type.id,
            "is_diseased": "no",
            "number_of_livestock": 5,
            "collected_gc": "2020-01-15",
            "collected_ec": "2020-07-15",
            "season": self.season_gc.id,
        }
        live_stock_info = self.env["g2p.livestock.information"].create(live_stock_info_data)
        self.assertEqual(live_stock_info.partner_id, self.farmer, "Incorrect farmer assigned")
        self.assertEqual(
            live_stock_info.livestock_type, self.livestock_type, "Incorrect livestock type assigned"
        )
        self.assertEqual(
            live_stock_info.is_diseased, "no", "Livestock information incorrectly marked as diseased"
        )
        self.assertEqual(live_stock_info.number_of_livestock, 5, "Incorrect number of livestock")

    def test_02_onchange_collected_gc_sets_season_correctly(self):
        """Test onchange method for collected_gc sets the correct season."""
        live_stock_info = self.env["g2p.livestock.information"].create(
            {
                "partner_id": self.farmer.id,
                "livestock_type": self.livestock_type.id,
                "is_diseased": "no",
                "number_of_livestock": 5,
                "collected_gc": "2020-01-15",
            }
        )
        live_stock_info._onchange_collected_gc()
        self.assertEqual(
            live_stock_info.season, self.season_gc, "Season not set correctly based on collected_gc"
        )

    def test_05_onchange_collected_gc_updates_collected_ec(self):
        """Test onchange method for collected_gc updates collected_ec correctly."""
        live_stock_info = self.env["g2p.livestock.information"].create(
            {
                "partner_id": self.farmer.id,
                "livestock_type": self.livestock_type.id,
                "is_diseased": "no",
                "number_of_livestock": 5,
                "collected_gc": datetime.date(2024, 8, 4),
            }
        )
        live_stock_info._onchange_collected_gc()
        self.assertEqual(
            live_stock_info.collected_ec,
            "2016/11/28",
            "collected_ec not updated correctly based on collected_gc",
        )

    def test_06_create_live_stock_information_with_invalid_collected_gc_dates(self):
        """Test creating a Live Stock Information record with invalid dates raises ValidationError."""
        with self.assertRaises(InvalidDatetimeFormat):
            self.env["g2p.livestock.information"].create(
                {
                    "partner_id": self.farmer.id,
                    "livestock_type": self.livestock_type.id,
                    "is_diseased": "no",
                    "number_of_livestock": 5,
                    "collected_gc": "invalid-date",
                }
            )

    def test_07_create_record_without_required_fields(self):
        """Test creating a record without required fields."""
        with self.assertRaises(ValidationError):
            self.env["g2p.livestock.information"].create(
                {
                    "partner_id": self.farmer.id,
                    "livestock_type": self.livestock_type.id,
                    "is_diseased": "yes",
                    "number_of_livestock": 5,
                    "collected_gc": "2020-01-01",
                    "collected_ec": "2020-01-01",
                    "season": self.season_gc.id,
                }
            )

    def test_08_check_illness_type_required(self):
        """Test checking if illness_type is required when is_diseased is 'yes'."""
        with self.assertRaises(ValidationError):
            self.env["g2p.livestock.information"].create(
                {
                    "partner_id": self.farmer.id,
                    "livestock_type": self.livestock_type.id,
                    "is_diseased": "yes",
                    "number_of_livestock": 5,
                    "collected_gc": "2020-01-01",
                    "collected_ec": "2020-01-01",
                    "season": self.season_gc.id,
                }
            )

    def test_09_check_collected_dates_empty(self):
        """Test error when both collected_gc and collected_ec are empty."""
        with self.assertRaises(ValidationError):
            self.env["g2p.livestock.information"].create(
                {
                    "partner_id": self.farmer.id,
                    "livestock_type": self.livestock_type.id,
                    "is_diseased": "no",
                    "number_of_livestock": 5,
                    "collected_gc": False,
                    "collected_ec": False,
                }
            )
