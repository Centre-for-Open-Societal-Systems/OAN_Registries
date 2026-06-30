from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestG2PCooperativeUnion(TransactionCase):
    def test_01_create_cooperative_union(self):
        """Test creating a new Cooperative Union record."""
        cooperative_union_data = {
            "name": "Test Cooperative Union",
            "code": "TCU",
        }
        cooperative_union = self.env["g2p.cooperative.union"].create(cooperative_union_data)
        self.assertEqual(
            cooperative_union.name, "Test Cooperative Union", "Cooperative Union name is incorrect"
        )
        self.assertEqual(cooperative_union.code, "TCU", "Cooperative Union code is incorrect")

    def test_02_create_cooperative_union_duplicate_code(self):
        self.env["g2p.cooperative.union"].create(
            {
                "name": "Initial Cooperative Union",
                "code": "TCU",
            }
        )
        with self.assertRaises(ValidationError):
            self.env["g2p.cooperative.union"].create({"name": "Duplicate Cooperative Union", "code": "TCU"})

    def test_03_create_cooperative_union_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.cooperative.union"].create({"name": "", "code": "TCU"})

    def test_04_create_cooperative_union_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.cooperative.union"].create({"name": "Test Cooperative Union", "code": ""})
