import datetime

from odoo.tests.common import TransactionCase


class TestG2PFarmer(TransactionCase):
    def setUp(self):
        super().setUp()
        self.farmer = self.env["res.partner"].create(
            {
                "name": "Initial Name",
                "family_name": "Smith",
                "given_name": "John",
                "is_group": False,
                "is_registrant": True,
            }
        )

    def test_01_name_change_farmer(self):
        self.farmer.write(
            {
                "family_name": "Doe",
                "given_name": "Jane",
                "gf_name_eng": "",
            }
        )
        self.farmer.name_change_farmer()
        self.assertEqual(
            self.farmer.name,
            "JANE DOE ",
            "Name did not update correctly when all fields are filled except gf_name_eng.",
        )
        # Test when gf_name_eng is also filled
        self.farmer.write(
            {
                "family_name": "Doe",
                "given_name": "Jane",
                "gf_name_eng": "English Name",
            }
        )
        self.farmer.name_change_farmer()
        self.assertEqual(
            self.farmer.name,
            "JANE DOE ENGLISH NAME",
            "Name did not update correctly when gf_name_eng is filled.",
        )
        # Test when is_group is True
        self.farmer.write(
            {
                "is_group": True,
                "family_name": "Doe",
                "given_name": "Jane",
                "gf_name_eng": "English Name",
            }
        )
        self.farmer.name_change_farmer()
        self.assertEqual(
            self.farmer.name, "JANE DOE ENGLISH NAME", "Name did not update correctly when is_group is True."
        )
        # Test when is_group is False but no personal names are provided
        self.farmer.write(
            {
                "is_group": False,
                "family_name": "",
                "given_name": "",
                "gf_name_eng": "",
            }
        )
        self.farmer.name_change_farmer()
        self.assertEqual(
            self.farmer.name, "", "Name did not update correctly when no personal names are provided."
        )
        # Test when is_group is False and only personal names are provided
        self.farmer.write(
            {
                "is_group": False,
                "family_name": "Doe",
                "given_name": "Jane",
                "gf_name_eng": "BE",
            }
        )
        self.farmer.name_change_farmer()
        self.assertEqual(
            self.farmer.name,
            "JANE DOE BE",
            "Name did not update correctly when only personal names are provided.",
        )

    def test_04_onchange_birthdate_ec_updates_birthdate(self):
        """Test onchange method for birthdate_ec updates birthdate correctly."""
        self.farmer.write(
            {
                "birthdate_ec": "2016-11-28",
            }
        )
        self.farmer._onchange_birthdate_ec()
        self.assertEqual(
            self.farmer.birthdate,
            datetime.date(2024, 8, 4),
            "birthdate not updated correctly based on birthdate_ec",
        )

    def test_05_onchange_birthdate_updates_birthdate_ec(self):
        """Test onchange method for birthdate_ec updates birthdate correctly."""
        self.farmer.write(
            {
                "birthdate": "2024-8-4",
            }
        )
        self.farmer._onchange_birthdate()
        self.assertEqual(
            self.farmer.birthdate_ec, "2016/11/28", "birthdate_ec not updated correctly based on birthdate"
        )

    def test_06_state_approve_and_reject(self):
        self.farmer.state_approve()
        self.assertEqual(self.farmer.state, "approved", "State approval failed")
        self.farmer.state_reject()
        self.assertEqual(self.farmer.state, "rejected", "State rejection failed")

    def test_compute_total_land_area(self):
        self.env["g2p.land.information"].create(
            {
                "partner_id": self.farmer.id,
                "total_land_area": 50,
                "land_id": 8989,
                "ownership_type": "owner",
            }
        )
        self.env["g2p.land.information"].create(
            {
                "partner_id": self.farmer.id,
                "total_land_area": 30,
                "land_id": 8990,
                "ownership_type": "owner",
            }
        )
        self.farmer._invalidate_cache()
        self.assertEqual(self.farmer.total_land_area, 80.00, "Total land area computation failed")

    def test_compute_land_ownership(self):
        land_info_owner = self.env["g2p.land.information"].create(
            {
                "partner_id": self.farmer.id,
                "total_land_area": 100,
                "land_id": 8989,
                "ownership_type": "owner",
            }
        )
        self.farmer._invalidate_cache()
        self.assertEqual(
            self.farmer.land_ownership, "owner", "Land ownership computation failed for owner-only scenario"
        )
        # Test tenant-only scenario
        land_info_owner.write({"ownership_type": "tenant"})
        self.farmer._invalidate_cache()
        self.assertEqual(
            self.farmer.land_ownership, "tenant", "Land ownership computation failed for tenant-only scenario"
        )
        # Test hybrid scenario
        self.env["g2p.land.information"].create(
            {
                "partner_id": self.farmer.id,
                "total_land_area": 50,
                "land_id": 8991,
                "ownership_type": "owner",
            }
        )
        self.farmer._invalidate_cache()
        self.assertEqual(
            self.farmer.land_ownership, "hybrid", "Land ownership computation failed for hybrid scenario"
        )
