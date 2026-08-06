from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PCrop(TransactionCase):
    def setUp(self):
        super().setUp()
        self.category = self.env["g2p.crop.category"].create({"name": "Test Category"})

    def test_01_create_crop(self):
        """Test creating a new G2PCrop record."""
        # Define data for the new crop
        new_crop_data = {"name": "Sample Crop", "category_id": self.category.id}
        # Attempt to create a new crop
        crop = self.env["g2p.crop"].create(new_crop_data)
        self.assertEqual(crop.name, "Sample Crop", "Crop name is incorrect")
        self.assertEqual(crop.category_id.name, "Test Category", "Crop category association is incorrect")

    def test_02_create_crop_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.crop"].create({"name": "", "category_id": self.category.id})
