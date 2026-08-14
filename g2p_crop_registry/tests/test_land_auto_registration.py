from odoo.tests.common import TransactionCase


class TestLandAutoRegistration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_1 = cls.env['res.partner'].create({
            'name': 'Farmer One',
            'is_farmer': 'yes',
        })
        cls.partner_2 = cls.env['res.partner'].create({
            'name': 'Farmer Two',
            'is_farmer': 'yes',
        })

        cls.category = cls.env['g2p.crop.category'].create({'name': 'Cereal'})
        cls.crop = cls.env['g2p.crop'].create({
            'name': 'Wheat',
            'category_id': cls.category.id,
        })

        cls.registry_1 = cls.env['g2p.crop.registry'].create({
            'partner_id': cls.partner_1.id,
            'fyda_id': 'FAN-1111111111111111',
            'farmer_display_id': 'Farmer One',
        })
        cls.registry_2 = cls.env['g2p.crop.registry'].create({
            'partner_id': cls.partner_2.id,
            'fyda_id': 'FAN-2222222222222222',
            'farmer_display_id': 'Farmer Two',
        })

        seasons = cls.env['g2p.season'].search([], limit=1)
        cls.season = seasons[0] if seasons else cls.env['g2p.season'].create({
            'name': 'Test Season',
            'start_gc': '2025-06-01',
            'end_gc': '2025-09-30',
        })

        # Administrative fixtures
        cls.region = cls.env['g2p.region'].search([('code', '=', 'RU')], limit=1)
        if not cls.region:
            cls.region = cls.env['g2p.region'].create({'name': 'Region RU', 'code': 'RU', 'iso_code': 'RU'})
        
        cls.zone = cls.env['g2p.zone'].search([('code', '=', '12')], limit=1)
        if not cls.zone:
            cls.zone = cls.env['g2p.zone'].create({'name': 'Zone 12', 'code': '12', 'region': cls.region.id})

        cls.woreda = cls.env['g2p.woreda'].search([('code', '=', '12')], limit=1)
        if not cls.woreda:
            cls.woreda = cls.env['g2p.woreda'].create({'name': 'Woreda 12', 'code': '12', 'zone': cls.zone.id})

        cls.kebele = cls.env['g2p.kebele'].search([('code', '=', '123')], limit=1)
        if not cls.kebele:
            cls.kebele = cls.env['g2p.kebele'].create({'name': 'Kebele 123', 'code': '123', 'woreda': cls.woreda.id})

    def test_auto_registration_creates_land_info_with_ru_format(self):
        """Test creating a line with is_plot_not_registered=True auto-creates land_info with RU/... format."""
        plan = self.env['g2p.annual.line'].create({
            'crop_registry_id': self.registry_1.id,
            'is_plot_not_registered': True,
            'land_area': 3.5,
            'ownership_type': 'owner',
            'region_name_id': self.region.id,
            'zone_name_id': self.zone.id,
            'woreda_name_id': self.woreda.id,
            'kebele_id': self.kebele.id,
            'season_id': self.season.id,
            'crop_name_id': self.crop.id,
        })

        # Verify auto-registration converted temp plot to registered land
        self.assertFalse(plan.is_plot_not_registered)
        self.assertFalse(plan.temporary_land_id)
        self.assertTrue(plan.land_info_id)

        land = plan.land_info_id
        self.assertEqual(land.partner_id, self.partner_1)
        self.assertEqual(land.total_land_area, 3.5)
        self.assertEqual(land.ownership_type, 'owner')
        self.assertEqual(land.land_kebele, self.kebele)
        self.assertTrue(land.land_id.startswith('RU/12/12/123/'))

    def test_auto_registration_uses_provided_temporary_land_id(self):
        """Test that an explicitly provided temporary_land_id is used as the registered land_id."""
        plan = self.env['g2p.annual.line'].create({
            'crop_registry_id': self.registry_1.id,
            'is_plot_not_registered': True,
            'temporary_land_id': 'RU/12/12/123/99999',
            'land_area': 5.0,
            'ownership_type': 'tenant',
            'season_id': self.season.id,
            'crop_name_id': self.crop.id,
        })

        self.assertFalse(plan.is_plot_not_registered)
        self.assertTrue(plan.land_info_id)
        self.assertEqual(plan.land_info_id.land_id, 'RU/12/12/123/99999')
        self.assertEqual(plan.land_info_id.total_land_area, 5.0)

    def test_cross_farmer_collision_handling(self):
        """Test that if Farmer 2 inputs a temp land ID already owned by Farmer 1, Farmer 2 gets a unique new ID."""
        # Farmer 1 creates land
        plan_1 = self.env['g2p.annual.line'].create({
            'crop_registry_id': self.registry_1.id,
            'is_plot_not_registered': True,
            'temporary_land_id': 'RU/12/12/123/88888',
            'land_area': 2.0,
            'ownership_type': 'owner',
            'season_id': self.season.id,
            'crop_name_id': self.crop.id,
        })
        self.assertEqual(plan_1.land_info_id.land_id, 'RU/12/12/123/88888')

        # Farmer 2 tries to use the same temporary land ID
        plan_2 = self.env['g2p.annual.line'].create({
            'crop_registry_id': self.registry_2.id,
            'is_plot_not_registered': True,
            'temporary_land_id': 'RU/12/12/123/88888',
            'land_area': 4.0,
            'ownership_type': 'owner',
            'region_name_id': self.region.id,
            'zone_name_id': self.zone.id,
            'woreda_name_id': self.woreda.id,
            'kebele_id': self.kebele.id,
            'season_id': self.season.id,
            'crop_name_id': self.crop.id,
        })

        # Farmer 2 should receive a unique land_info_id owned by Farmer 2, NOT sharing Farmer 1's land
        self.assertNotEqual(plan_2.land_info_id, plan_1.land_info_id)
        self.assertEqual(plan_2.land_info_id.partner_id, self.partner_2)
        self.assertNotEqual(plan_2.land_info_id.land_id, 'RU/12/12/123/88888')
        self.assertTrue(plan_2.land_info_id.land_id.startswith('RU/12/12/123/'))

    def test_planning_to_cultivation_sync_preserves_registered_land(self):
        """Test that auto-registered land on Planning syncs seamlessly to Cultivation without duplicating."""
        plan = self.env['g2p.annual.line'].create({
            'crop_registry_id': self.registry_1.id,
            'is_plot_not_registered': True,
            'land_area': 6.0,
            'ownership_type': 'owner',
            'season_id': self.season.id,
            'crop_name_id': self.crop.id,
            'crop_planned_area': 6.0,
        })
        self.registry_1._onchange_sync_annual_lines()

        # Check Cultivation line created via sync
        actual_line = self.registry_1.actual_annual_line_ids.filtered(lambda l: l.sync_id == plan.sync_id)
        self.assertEqual(len(actual_line), 1)
        self.assertEqual(actual_line.land_info_id, plan.land_info_id)

        # Count total land records for Farmer 1 — must be exactly 1
        lands = self.env['g2p.land.information'].search([('partner_id', '=', self.partner_1.id)])
        self.assertEqual(len(lands), 1)
