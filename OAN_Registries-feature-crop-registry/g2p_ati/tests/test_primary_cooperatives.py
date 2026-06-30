from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PPrimaryCooperative(TransactionCase):
    def test_01_create_primary_cooperative(self):
        """Test creating a new Primary Cooperative record."""
        primary_cooperative_data = {
            "name": "Test Primary Cooperative",
            "code": "TPC",
        }
        primary_cooperative = self.env["g2p.primary.cooperative"].create(primary_cooperative_data)
        self.assertEqual(
            primary_cooperative.name, "Test Primary Cooperative", "Primary Cooperative name is incorrect"
        )
        self.assertEqual(primary_cooperative.code, "TPC", "Primary Cooperative code is incorrect")

    def test_02_create_primary_cooperative_duplicate_code(self):
        self.env["g2p.primary.cooperative"].create(
            {
                "name": "Initial Primary Cooperative",
                "code": "TPC",
            }
        )
        with self.assertRaises(ValidationError):
            self.env["g2p.primary.cooperative"].create(
                {"name": "Duplicate Primary Cooperative", "code": "TPC"}
            )

    def test_03_create_primary_cooperative_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.primary.cooperative"].create({"name": "", "code": "TPC"})

    def test_04_create_primary_cooperative_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.primary.cooperative"].create({"name": "Test Primary Cooperative", "code": ""})
