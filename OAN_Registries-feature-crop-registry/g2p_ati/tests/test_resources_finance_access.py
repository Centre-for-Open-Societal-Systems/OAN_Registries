from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PFinanceAccess(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_01_create_access(self):
        """Test creating a new G2PFinanceAccess record."""
        new_access_data = {
            "name": "Bank Account",
            "code": "BA",
        }
        access = self.env["g2p.finance.access"].create(new_access_data)
        self.assertEqual(access.name, "Bank Account", "Finance access name is incorrect")
        self.assertEqual(access.code, "BA", "Finance access code is incorrect")

    def test_02_create_access_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.finance.access"].create({"name": "", "code": "BA"})

    def test_03_create_access_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.finance.access"].create({"name": "Credit Card", "code": ""})

    def test_04_unique_code(self):
        """Test that the code field is unique."""
        self.env["g2p.finance.access"].create({"name": "Debit Card", "code": "DC"})
        with self.assertRaises(ValidationError):
            self.env["g2p.finance.access"].create({"name": "Cash", "code": "DC"})
