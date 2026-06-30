from psycopg2.errors import NotNullViolation

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PCrop(TransactionCase):
    def setUp(self):
        super().setUp()
        self.category = self.env["g2p.crop.category"].create({"name": "Test Category", "code": "TC"})

    def test_01_create_crop(self):
        """Test creating a new G2PCrop record."""
        # Define data for the new crop
        new_crop_data = {"name": "Sample Crop", "code": "SC1", "category": self.category.id}
        # Attempt to create a new crop with a unique code and associated category
        crop = self.env["g2p.crop"].create(new_crop_data)
        self.assertEqual(crop.name, "Sample Crop", "Crop name is incorrect")
        self.assertEqual(crop.code, "SC1", "Crop code is incorrect")
        self.assertEqual(crop.category.name, "Test Category", "Crop category association is incorrect")

    def test_02_create_crop_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.crop"].create({"name": "", "code": "A", "category": self.category.id})

    def test_03_create_crop_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.crop"].create({"name": "A", "code": "", "category": self.category.id})

    def test_04_crop_empty_category(self):
        """Test that every crop is associated with a valid category."""
        with self.assertRaises(NotNullViolation):
            self.env["g2p.crop"].create({"name": "Crop 1", "code": "CP1", "category": False})

    def test_05_unique_code(self):
        """Test that the code field is unique."""
        self.env["g2p.crop"].create({"name": "Crop 1", "code": "CP1", "category": self.category.id})
        with self.assertRaises(ValidationError):
            self.env["g2p.crop"].create({"name": "Crop 2", "code": "CP1", "category": self.category.id})
