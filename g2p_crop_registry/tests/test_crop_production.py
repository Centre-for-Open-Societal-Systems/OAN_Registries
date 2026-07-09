from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestCropProduction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # --- Base partner / crop / registry fixtures ---
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Farmer',
            'is_farmer': 'yes',
        })

        cls.category = cls.env['g2p.crop.category'].create({
            'name': 'Cereal',
        })

        cls.crop = cls.env['g2p.crop'].create({
            'name': 'Maize',
            'category_id': cls.category.id,
        })

        cls.crop_registry = cls.env['g2p.crop.registry'].create({
            'partner_id': cls.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'farmer_display_id': 'Test Farmer',
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

    def test_crop_production_creation(self):
        production = self.env['g2p.crop.production'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
        })
        self.assertTrue(production.id)
        self.assertTrue(production.name.startswith('CROP/PROD/'))
        self.assertEqual(production.crop_name_id, self.crop)

    # ------------------------------------------------------------------
    # Land Region Compute
    # ------------------------------------------------------------------
    def test_compute_land_region(self):
        production = self.env['g2p.crop.production'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'land_info_id': self.land_info.id,
        })
        production._compute_land_region()
        self.assertEqual(production.land_region_id, self.region)

    # ------------------------------------------------------------------
    # Harvest Date Constraints and Onchanges
    # ------------------------------------------------------------------

    def test_harvest_date_before_sowing_raises(self):
        with self.assertRaises(ValidationError):
            self.env['g2p.crop.production'].create({
                'crop_registry_id': self.crop_registry.id,
                'crop_name_id': self.crop.id,
                'season_id': self.season.id,
                'actual_sowing_date': '2025-07-01',
                'harvest_date': '2025-06-15',
            })

    def test_harvest_date_after_sowing_valid(self):
        production = self.env['g2p.crop.production'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'actual_sowing_date': '2025-07-01',
            'harvest_date': '2025-10-15',
        })
        self.assertTrue(production.id)

    def test_onchange_harvest_date(self):
        production = self.env['g2p.crop.production'].new({
            'crop_registry_id': self.crop_registry.id,
            'actual_sowing_date': '2025-07-01',
        })
        production.harvest_date = '2025-06-15'
        res = production._onchange_harvest_date()
        self.assertFalse(production.harvest_date)
        self.assertIn('warning', res)
        self.assertEqual(res['warning']['title'], 'Invalid Harvest Date')

    # ------------------------------------------------------------------
    # Area Harvested Constraints and Onchanges
    # ------------------------------------------------------------------

    def test_area_harvested_exceeding_actual_raises(self):
        with self.assertRaises(ValidationError):
            self.env['g2p.crop.production'].create({
                'crop_registry_id': self.crop_registry.id,
                'crop_name_id': self.crop.id,
                'season_id': self.season.id,
                'actual_crop_area': 10.0,
                'area_harvested': 15.0,
            })

    def test_area_harvested_within_actual_valid(self):
        production = self.env['g2p.crop.production'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'actual_crop_area': 10.0,
            'area_harvested': 8.0,
        })
        self.assertTrue(production.id)

    def test_onchange_area_harvested(self):
        production = self.env['g2p.crop.production'].new({
            'crop_registry_id': self.crop_registry.id,
            'actual_crop_area': 10.0,
        })
        production.area_harvested = 15.0
        res = production._onchange_area_harvested()
        self.assertEqual(production.area_harvested, 10.0)
        self.assertIn('warning', res)
        self.assertEqual(res['warning']['title'], 'Invalid Area Harvested')

    # ------------------------------------------------------------------
    # Production Computed Results
    # ------------------------------------------------------------------

    def test_production_results_computes(self):
        production = self.env['g2p.crop.production'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'qty_harvested': 50.0,          # 50 quintals = 5000 kg
            'area_harvested': 10.0,         # 10 ha
            'expected_yield': 60.0,
            'planned_area': 12.0,
            'actual_seed_qty': 200.0,       # 200 kg
            'actual_fertilizer_qty': 500.0, # 500 kg
            'actual_yield_cached': 45.0,
        })

        self.assertAlmostEqual(production.yield_per_ha, 500.0)
        self.assertAlmostEqual(production.yield_performance_pct, 75.0)
        self.assertAlmostEqual(production.land_utilization_rate, 10.0 / 12.0)
        self.assertAlmostEqual(production.seed_productivity, 25.0)
        self.assertAlmostEqual(production.fertilizer_efficiency, 10.0)
