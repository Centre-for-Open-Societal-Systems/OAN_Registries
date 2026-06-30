from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PCropCategory(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_01_create_crop_category(self):
        """Test creating a new G2PCrop record."""
        new_crop_category_data = {
            "name": "Test Crop Category",
            "code": "SC1",
        }
        crop_category = self.env["g2p.crop.category"].create(new_crop_category_data)
        self.assertEqual(crop_category.name, "Test Crop Category", "Crop category name is incorrect")
        self.assertEqual(crop_category.code, "SC1", "Crop category code is incorrect")

    def test_02_create_category_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.crop.category"].create({"name": "", "code": "A"})

    def test_03_create_crop_category_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.crop.category"].create({"name": "A", "code": ""})

    def test_04_unique_code(self):
        """Test that the code field is unique."""
        self.env["g2p.crop.category"].create({"name": "Category 1", "code": "CAT1"})
        with self.assertRaises(ValidationError):
            self.env["g2p.crop.category"].create({"name": "Category 2", "code": "CAT1"})
