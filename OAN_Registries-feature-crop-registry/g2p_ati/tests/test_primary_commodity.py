from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PPrimaryCommodity(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_01_create_primary_commodity(self):
        """Test creating a new G2PPrimaryCommodity record."""
        new_commodity_data = {
            "name": "Wheat",
            "code": "WH",
        }
        commodity = self.env["g2p.primary.commodity"].create(new_commodity_data)
        self.assertEqual(commodity.name, "Wheat", "Commodity name is incorrect")
        self.assertEqual(commodity.code, "WH", "Commodity code is incorrect")

    def test_02_create_commodity_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.primary.commodity"].create({"name": "", "code": "WH"})

    def test_03_create_primary_commodity_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.primary.commodity"].create({"name": "Corn", "code": ""})

    def test_04_unique_code(self):
        """Test that the code field is unique."""
        self.env["g2p.primary.commodity"].create({"name": "Rice", "code": "RI"})
        with self.assertRaises(ValidationError):
            self.env["g2p.primary.commodity"].create({"name": "Soybean", "code": "RI"})
