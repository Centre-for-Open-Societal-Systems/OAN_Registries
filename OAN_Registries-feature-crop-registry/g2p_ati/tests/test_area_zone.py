from psycopg2.errors import NotNullViolation

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestZone(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure a Region record exists since Zone depends on it
        existing_region = cls.env["g2p.region"].search([("code", "=", "NA")], limit=1)
        if not existing_region:
            cls.region = cls.env["g2p.region"].create(
                {"name": "Test Region", "code": "NA", "iso_code": "001"}
            )
        else:
            cls.region = existing_region

    def test_01_create_zone(self):
        """Test creating a new Zone record."""
        zone_data = {
            "name": "Test Zone",
            "code": "TZ",
            "region": self.region.id,
        }
        zone = self.env["g2p.zone"].create(zone_data)
        self.assertEqual(zone.name, "Test Zone", "Zone name is incorrect")
        self.assertEqual(zone.code, "TZ", "Zone code is incorrect")
        self.assertEqual(zone.region, self.region, "Incorrect region assigned")

    def test_02_create_zone_without_region(self):
        with self.assertRaises(NotNullViolation):
            self.env["g2p.zone"].create({"name": "Test Zone", "code": "TZ", "region": None})

    def test_02_check_required_fields(self):
        with self.assertRaises(NotNullViolation):
            self.env["g2p.zone"].create(
                {
                    "name": "A",
                }
            )

    def test_03_create_zone_with_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.zone"].create({"name": "", "code": "TZ", "region": self.region.id})

    def test_04_create_zone_with_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.zone"].create({"name": "Test Zone", "code": "", "region": self.region.id})

    def test_05_create_zone_duplicate_code(self):
        self.env["g2p.zone"].create({"name": "Test", "code": "TCU", "region": self.region.id})
        with self.assertRaises(ValidationError):
            self.env["g2p.zone"].create({"name": "Test", "code": "TCU", "region": self.region.id})
