from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PIllnessType(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_01_create_illness_type(self):
        """Test creating a new G2PIllnessType record."""
        new_illness_type_data = {
            "name": "Flu",
            "code": "FLU",
            "illness_type": "crop",
        }
        illness_type = self.env["g2p.illness.type"].create(new_illness_type_data)
        self.assertEqual(illness_type.name, "Flu", "Illness type name is incorrect")
        self.assertEqual(illness_type.code, "FLU", "Illness type code is incorrect")
        self.assertEqual(illness_type.illness_type, "crop", "Illness type selection is incorrect")

    def test_02_create_type_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.illness.type"].create({"name": "", "code": "FLU", "illness_type": "crop"})

    def test_03_create_illness_type_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.illness.type"].create({"name": "Cold", "code": "", "illness_type": "crop"})

    def test_04_unique_code(self):
        """Test that the code field is unique."""
        self.env["g2p.illness.type"].create({"name": "Common Cold", "code": "CC", "illness_type": "crop"})
        with self.assertRaises(ValidationError):
            self.env["g2p.illness.type"].create(
                {"name": "Nasal Congestion", "code": "CC", "illness_type": "crop"}
            )
