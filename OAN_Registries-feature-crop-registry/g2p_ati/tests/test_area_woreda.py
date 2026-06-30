from psycopg2.errors import NotNullViolation

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestWoreda(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure Region and Zone records exist since Woreda depends on them
        existing_region = cls.env["g2p.region"].search([("code", "=", "NA")], limit=1)
        if not existing_region:
            cls.region = cls.env["g2p.region"].create(
                {"name": "Test Region", "code": "NA", "iso_code": "001"}
            )
        else:
            cls.region = existing_region
        existing_zone = cls.env["g2p.zone"].search([("region", "=", cls.region.id)], limit=1)
        if not existing_zone:
            cls.zone = cls.env["g2p.zone"].create(
                {"name": "Test Zone", "code": "TZ", "region": cls.region.id}
            )
        else:
            cls.zone = existing_zone

    def test_01_create_woreda(self):
        """Test creating a new Woreda record."""
        woreda_data = {
            "name": "Test Woreda",
            "code": "TW",
            "zone": self.zone.id,
        }
        woreda = self.env["g2p.woreda"].create(woreda_data)
        self.assertEqual(woreda.name, "Test Woreda", "Woreda name is incorrect")
        self.assertEqual(woreda.code, "TW", "Woreda code is incorrect")
        self.assertEqual(woreda.zone, self.zone, "Incorrect zone assigned")

    def test_02_check_required_fields(self):
        with self.assertRaises(NotNullViolation):
            self.env["g2p.woreda"].create(
                {
                    "name": "A",
                }
            )

    def test_03_create_woreda_without_zone(self):
        with self.assertRaises(NotNullViolation):
            self.env["g2p.woreda"].create({"name": "Test Woreda", "code": "TW", "zone": ""})

    def test_04_create_woreda_with_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.woreda"].create({"name": "", "code": "TW", "zone": self.zone.id})

    def test_05_create_woreda_with_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.woreda"].create({"name": "Test Woreda", "code": "", "zone": self.zone.id})

    def test_06_create_woreda_duplicate_code(self):
        self.env["g2p.woreda"].create({"name": "Test", "code": "TCU", "zone": self.zone.id})
        with self.assertRaises(ValidationError):
            self.env["g2p.woreda"].create({"name": "Test", "code": "TCU", "zone": self.zone.id})
