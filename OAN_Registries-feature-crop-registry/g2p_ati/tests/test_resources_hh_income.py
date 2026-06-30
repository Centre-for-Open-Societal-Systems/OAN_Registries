from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PHHIncome(TransactionCase):
    def setUp(self):
        super().setUp()

    def test_01_create_income(self):
        """Test creating a new G2PHHIncome record."""
        new_income_data = {
            "name": "Salary",
            "code": "SL",
        }
        income = self.env["g2p.hh.income"].create(new_income_data)
        self.assertEqual(income.name, "Salary", "Income name is incorrect")
        self.assertEqual(income.code, "SL", "Income code is incorrect")

    def test_02_create_income_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.hh.income"].create({"name": "", "code": "SL"})

    def test_03_create_income_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.hh.income"].create({"name": "Bonus", "code": ""})

    def test_04_unique_code(self):
        """Test that the code field is unique."""
        self.env["g2p.hh.income"].create({"name": "Bonus", "code": "BN"})
        with self.assertRaises(ValidationError):
            self.env["g2p.hh.income"].create({"name": "Overtime Pay", "code": "BN"})
