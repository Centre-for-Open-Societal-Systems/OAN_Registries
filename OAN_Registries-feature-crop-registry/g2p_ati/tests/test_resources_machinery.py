from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PMachinery(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_01_create_machinery(self):
        """Test creating a new G2PMachinery record."""
        new_machinery_data = {
            "name": "Tractor",
            "code": "TR",
        }
        machinery = self.env["g2p.machinery"].create(new_machinery_data)
        self.assertEqual(machinery.name, "Tractor", "Machinery name is incorrect")
        self.assertEqual(machinery.code, "TR", "Machinery code is incorrect")

    def test_02_create_machinery_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.machinery"].create({"name": "", "code": "TR"})

    def test_03_create_machinery_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.machinery"].create({"name": "Harvester", "code": ""})

    def test_04_unique_code(self):
        """Test that the code field is unique."""
        self.env["g2p.machinery"].create({"name": "Combine Harvester", "code": "CH"})
        with self.assertRaises(ValidationError):
            self.env["g2p.machinery"].create({"name": "Sprayer", "code": "CH"})
