from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2pLang(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_01_create_language(self):
        """Test creating a new G2pLang record."""
        new_language_data = {
            "name": "Spanish",
            "code": "SP",
        }
        language = self.env["g2p.lang"].create(new_language_data)
        self.assertEqual(language.name, "Spanish", "Language name is incorrect")
        self.assertEqual(language.code, "SP", "Language code is incorrect")

    def test_02_create_language_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.lang"].create({"name": "", "code": "SP"})

    def test_03_create_language_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.lang"].create({"name": "French", "code": ""})

    def test_04_unique_code(self):
        """Test that the code field is unique."""
        self.env["g2p.lang"].create({"name": "English", "code": "EN"})
        with self.assertRaises(ValidationError):
            self.env["g2p.lang"].create({"name": "German", "code": "EN"})
