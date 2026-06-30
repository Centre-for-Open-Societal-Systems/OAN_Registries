from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PLandInformation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({"name": "Test Partner"})

    def test_01_create_land_information(self):
        """Test creating a new Land Information record."""
        land_info_data = {
            "partner_id": self.partner.id,
            "land_id": 125,
            "total_land_area": 2000,
            "ownership_type": "owner",
        }
        land_info = self.env["g2p.land.information"].create(land_info_data)
        self.assertEqual(land_info.partner_id, self.partner, "Incorrect partner assigned")
        self.assertEqual(land_info.land_id, "125", "Incorrect land id assigned")
        self.assertEqual(land_info.total_land_area, 2000, "Area not set correctly")
        self.assertEqual(land_info.ownership_type, "owner", "Ownership Type not set correctly")

    def test_05_check_area_must_be_positive(self):
        """Test that the area must be a positive number."""
        with self.assertRaises(ValidationError):
            self.env["g2p.land.information"].create(
                {
                    "partner_id": self.partner.id,
                    "land_id": 250,
                    "total_land_area": -100,
                    "ownership_type": "owner",
                }
            )
