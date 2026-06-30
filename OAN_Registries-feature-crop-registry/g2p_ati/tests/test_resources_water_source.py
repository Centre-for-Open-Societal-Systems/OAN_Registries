from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PWaterSource(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_01_create_water_source(self):
        """Test creating a new G2PWaterSource record."""
        new_water_source_data = {
            "name": "River",
            "code": "RV",
        }
        water_source = self.env["g2p.water.source"].create(new_water_source_data)
        self.assertEqual(water_source.name, "River", "Water source name is incorrect")
        self.assertEqual(water_source.code, "RV", "Water source code is incorrect")

    def test_02_create_source_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.water.source"].create({"name": "", "code": "RV"})

    def test_03_create_water_source_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.water.source"].create({"name": "Lake", "code": ""})

    def test_04_unique_code(self):
        """Test that the code field is unique."""
        self.env["g2p.water.source"].create({"name": "Spring", "code": "SP"})
        with self.assertRaises(ValidationError):
            self.env["g2p.water.source"].create({"name": "Well", "code": "SP"})
