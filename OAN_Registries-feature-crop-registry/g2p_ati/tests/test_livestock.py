from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PLivestockType(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_01_create_livestock_type(self):
        """Test creating a new G2PLivestockType record."""
        new_livestock_type_data = {
            "name": "Cattle",
            "code": "CT",
        }
        livestock_type = self.env["g2p.livestock.type"].create(new_livestock_type_data)
        self.assertEqual(livestock_type.name, "Cattle", "Livestock type name is incorrect")
        self.assertEqual(livestock_type.code, "CT", "Livestock type code is incorrect")

    def test_02_create_type_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.livestock.type"].create({"name": "", "code": "CT"})

    def test_03_create_livestock_type_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.livestock.type"].create({"name": "Sheep", "code": ""})

    def test_04_unique_code(self):
        """Test that the code field is unique."""
        self.env["g2p.livestock.type"].create({"name": "Poultry", "code": "POU"})
        with self.assertRaises(ValidationError):
            self.env["g2p.livestock.type"].create({"name": "Goat", "code": "POU"})
