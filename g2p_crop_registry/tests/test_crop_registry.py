from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestCropRegistry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Farmer',
            'is_farmer': 'yes',
            'mobile': '+251911223344'
        })

        cls.category = cls.env['g2p.crop.category'].create({
            'name': 'Cereal',
        })

        cls.crop = cls.env['g2p.crop'].create({
            'name': 'Wheat',
            'category_id': cls.category.id,
        })

        cls.season = cls.env['g2p.season'].create({
            'name': 'Test Season',
            'start_gc': '2025-06-01',
            'end_gc': '2025-09-30',
        })

        cls.region = cls.env['g2p.region'].create({'name': 'Test Region', 'code': 'R1'})
        cls.zone = cls.env['g2p.zone'].create({'name': 'Test Zone', 'code': 'Z1', 'region': cls.region.id})
        cls.woreda = cls.env['g2p.woreda'].create({'name': 'Test Woreda', 'code': 'W1', 'zone': cls.zone.id})
        cls.kebele = cls.env['g2p.kebele'].create({'name': 'Test Kebele', 'code': 'K1', 'woreda': cls.woreda.id})

        cls.land_info = cls.env['g2p.land.information'].create({
            'total_land_area': 10.0,
            'ownership_type': 'owner',
            'soil_fertility': 'good',
            'land_kebele': cls.kebele.id,
            'polygon_data': '12.123, 45.456',
            'partner_id': cls.partner.id
        })

    # ------------------------------------------------------------------
    # Basic creation and sequence
    # ------------------------------------------------------------------

    def test_crop_registry_creation(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'farmer_display_id': 'Test Farmer',
        })
        self.assertTrue(crop_registry.id)
        self.assertTrue(crop_registry.name.startswith('CROP/REG/'))
        self.assertNotEqual(crop_registry.name, 'New')

    # ------------------------------------------------------------------
    # ID Validation (_check_ids & _check_mobile_numbers)
    # ------------------------------------------------------------------

    def test_fyda_id_invalid_raises(self):
        with self.assertRaises(ValidationError, msg="Fayda ID must be in this format: FAN-1234567890123456"):
            self.env['g2p.crop.registry'].create({
                'partner_id': self.partner.id,
                'fyda_id': 'INVALID-ID-FORMAT',
                'farmer_display_id': 'Test Farmer',
            })

    def test_fyda_id_valid_accepts(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-9876543210987654',
            'farmer_display_id': 'Test Farmer',
        })
        self.assertTrue(crop_registry.id)

    def test_check_mobile_numbers(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-9876543210987654',
        })
        # Should raise on badly formatted ethio mobile
        with self.assertRaises(ValidationError):
            crop_registry.surveyor_mobile_number = "1234"
            crop_registry._check_mobile_numbers()

        with self.assertRaises(ValidationError):
            crop_registry.surveyor_mobile_number = False
            crop_registry.supervisor_mobile_number = "1234"
            crop_registry._check_mobile_numbers()

    # ------------------------------------------------------------------
    # Computed Fields and Onchanges
    # ------------------------------------------------------------------

    def test_has_no_planning_data_true(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
        })
        crop_registry._compute_has_no_planning_data()
        self.assertTrue(crop_registry.has_no_planning_data)

    def test_has_no_planning_data_false(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
        })
        self.env['g2p.annual.line'].create({
            'crop_registry_id': crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
        })
        crop_registry._compute_has_no_planning_data()
        self.assertFalse(crop_registry.has_no_planning_data)

    def test_onchange_partner_id_details(self):
        crop_registry = self.env['g2p.crop.registry'].new({'partner_id': self.partner.id})
        crop_registry._onchange_partner_id_details()
        # Ensure details pull from partner
        self.assertEqual(crop_registry.farmer_display_id, self.partner.name)

    def test_onchange_land_info_id(self):
        crop_registry = self.env['g2p.crop.registry'].new({'land_info_id': self.land_info.id})
        crop_registry._onchange_land_info_id()
        self.assertEqual(crop_registry.region_id, self.region)
        self.assertEqual(crop_registry.zone_id, self.zone)
        self.assertEqual(crop_registry.woreda_id, self.woreda)
        self.assertEqual(crop_registry.kebele_id, self.kebele)

    def test_onchange_crop_id_and_primary_details(self):
        crop_registry = self.env['g2p.crop.registry'].new({'crop_name_id': self.crop.id})
        res = crop_registry._onchange_crop_id()
        self.assertIn('domain', res)

        crop_registry._compute_primary_crop_details()
        self.assertEqual(crop_registry.crop_category_id, self.category)

    def test_compute_actual_crop_area_exceeded(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'land_info_id': self.land_info.id,
        })
        # Mock actual lines exceeding 10.0 (total land area)
        self.env['g2p.annual.actual.line'].create({
            'crop_registry_id': crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'land_info_id': self.land_info.id,
            'actual_crop_area': 12.0,
            'is_manual': True
        })
        crop_registry._compute_actual_crop_area_exceeded()
        self.assertTrue(crop_registry.actual_crop_area_exceeded)

    # ------------------------------------------------------------------
    # Area limits (_check_planned_crop_area & _check_actual_crop_area_limits)
    # ------------------------------------------------------------------

    def test_check_planned_crop_area(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'land_info_id': self.land_info.id,
        })
        self.env['g2p.annual.line'].create({
            'crop_registry_id': crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'land_info_id': self.land_info.id,
            'crop_planned_area': 12.0
        })
        with self.assertRaises(ValidationError):
            crop_registry._check_planned_crop_area()

    def test_check_actual_crop_area_limits(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'land_info_id': self.land_info.id,
        })
        self.env['g2p.annual.actual.line'].create({
            'crop_registry_id': crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'land_info_id': self.land_info.id,
            'actual_crop_area': 12.0,
            'is_manual': True
        })
        with self.assertRaises(ValidationError):
            crop_registry._check_actual_crop_area_limits()

    # ------------------------------------------------------------------
    # Master Synchronization Engines (Executing all _onchange_sync_*)
    # ------------------------------------------------------------------

    def test_sync_engine_methods_execute_without_error(self):
        """Invoke all the massive sync loops to ensure they don't crash."""
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
        })
        sync_id = "test-sync-123"

        self.env['g2p.annual.line'].create({
            'crop_registry_id': crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
            'crop_expected': 100.0,
            'crop_planned_area': 5.0,
        })

        # Test full sync methods
        crop_registry._onchange_sync_annual_lines()
        crop_registry._onchange_sync_perennial_lines()
        crop_registry._onchange_sync_biennial_lines()

        crop_registry._onchange_sync_actual_to_production_annual()
        crop_registry._onchange_sync_actual_to_production_perennial()
        crop_registry._onchange_sync_actual_to_production_biennial()

        crop_registry._onchange_sync_production_to_actual()

        crop_registry._sync_production_cached_values()
        crop_registry._sync_crop_information()

        self.assertTrue(crop_registry.id)
