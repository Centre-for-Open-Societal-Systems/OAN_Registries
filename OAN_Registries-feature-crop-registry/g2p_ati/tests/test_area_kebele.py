from psycopg2.errors import NotNullViolation

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestKebele(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Ensure Woreda record exists since Kebele depends on it
        existing_woreda = cls.env["g2p.woreda"].search([], limit=1)
        if not existing_woreda:
            cls.woreda = cls.env["g2p.woreda"].create(
                {
                    "name": "Test Woreda",
                    "code": "TW",
                    "zone": cls.env["g2p.zone"]
                    .create(
                        {
                            "name": "Test Zone",
                            "code": "TZ",
                            "region": cls.env["g2p.region"]
                            .create({"name": "Test Region", "code": "NA", "iso_code": "001"})
                            .id,
                        }
                    )
                    .id,
                }
            )
        else:
            cls.woreda = existing_woreda

    def test_01_create_kebele(self):
        """Test creating a new Kebele record."""
        kebele_data = {
            "name": "Test Kebele",
            "code": "TK",
            "woreda": self.woreda.id,
        }
        kebele = self.env["g2p.kebele"].create(kebele_data)
        self.assertEqual(kebele.name, "Test Kebele", "Kebele name is incorrect")
        self.assertEqual(kebele.code, "TK", "Kebele code is incorrect")
        self.assertEqual(kebele.woreda, self.woreda, "Incorrect woreda assigned")

    def test_02_check_required_fields(self):
        with self.assertRaises(NotNullViolation):
            self.env["g2p.kebele"].create(
                {
                    "name": "A",
                }
            )

    def test_03_create_kebele_without_woreda(self):
        with self.assertRaises(NotNullViolation):
            self.env["g2p.kebele"].create({"name": "Test Kebele", "code": "TK", "woreda": None})

    def test_04_create_kebele_with_empty_name(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.kebele"].create({"name": "", "code": "TK", "woreda": self.woreda.id})

    def test_05_create_kebele_with_empty_code(self):
        with self.assertRaises(ValidationError):
            self.env["g2p.kebele"].create({"name": "Test Kebele", "code": "", "woreda": self.woreda.id})

    def test_06_create_kebele_duplicate_code(self):
        self.env["g2p.kebele"].create({"name": "Test", "code": "TCU", "woreda": self.woreda.id})

        with self.assertRaises(ValidationError):
            self.env["g2p.kebele"].create({"name": "Test", "code": "TCU", "woreda": self.woreda.id})
