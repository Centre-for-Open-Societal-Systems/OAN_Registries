from psycopg2.errors import NotNullViolation

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestRegion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Check if a region with code 'NA' already exists
        existing_region = cls.env["g2p.region"].search([("code", "=", "NA")])
        if not existing_region:
            cls.region = cls.env["g2p.region"].create(
                {"name": "Test Region", "code": "NA", "iso_code": "001"}
            )
        else:
            cls.region = existing_region

    def test_01_create_region(self):
        """Test creating a new Region record."""
        region_data = {"name": "Another Test Region", "code": "AN", "iso_code": "002"}
        region = self.env["g2p.region"].create(region_data)
        self.assertEqual(region.name, "Another Test Region", "Region name is incorrect")
        self.assertEqual(region.code, "AN", "Region code is incorrect")
        self.assertEqual(region.iso_code, "002", "Region iso_code is incorrect")

    def test_02_check_required_fields(self):
        with self.assertRaises(NotNullViolation):
            self.env["g2p.region"].create(
                {
                    "name": "A",
                }
            )

    def test_03_create_region_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.region"].create({"name": "", "code": "A", "iso_code": "TA"})

    def test_04_create_region_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.region"].create({"name": "A", "code": "", "iso_code": "TA"})

    def test_05_create_region_empty_iso_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.region"].create({"name": "A", "code": "J", "iso_code": ""})

    def test_06_create_region_duplicate_code(self):
        self.env["g2p.region"].create({"name": "Test", "code": "TCU", "iso_code": "A"})
        with self.assertRaises(ValidationError):
            self.env["g2p.region"].create({"name": "Test", "code": "TCU", "iso_code": "A"})
