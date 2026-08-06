from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PCropCategory(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_01_create_crop_category(self):
        """Test creating a new G2PCropCategory record."""
        new_crop_category_data = {
            "name": "Test Crop Category",
        }
        crop_category = self.env["g2p.crop.category"].create(new_crop_category_data)
        self.assertEqual(crop_category.name, "Test Crop Category", "Crop category name is incorrect")

    def test_02_create_category_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.crop.category"].create({"name": ""})
