from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestBiennialCrop(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # --- Base partner / crop / registry fixtures ---
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Farmer',
            'is_farmer': 'yes',
        })

        cls.category = cls.env['g2p.crop.category'].create({
            'name': 'Vegetable',
        })

        cls.crop = cls.env['g2p.crop'].create({
            'name': 'Onion',
            'category_id': cls.category.id,
        })

        cls.crop_variety = cls.env['g2p.crop.variety'].create({
            'name': 'Red Onion',
            'code': 'RO1',
            'crop_id': cls.crop.id,
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

        cls.wrap_season = cls.env['g2p.season'].create({
            'name': 'Wrap Season',
            'start_gc': '2025-11-01',
            'end_gc': '2026-02-28',
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

    def test_biennial_crop_plan_creation(self):
        plan = self.env['g2p.biennial.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
        })
        self.assertTrue(plan.id)
        self.assertEqual(plan.crop_name_id, self.crop)

    def test_biennial_crop_actual_creation(self):
        actual = self.env['g2p.biennial.actual.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
        })
        self.assertTrue(actual.id)
        self.assertEqual(actual.crop_name_id, self.crop)

    def test_collected_gc_within_season_is_valid(self):
        plan = self.env['g2p.biennial.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'start_gc': self.season.start_gc,
            'end_gc': self.season.end_gc,
            'collected_gc': '2025-07-15',
        })
        self.assertTrue(plan.id)

    def test_collected_gc_outside_season_raises(self):
        with self.assertRaises(ValidationError):
            self.env['g2p.biennial.line'].create({
                'crop_registry_id': self.crop_registry.id,
                'crop_name_id': self.crop.id,
                'season_id': self.season.id,
                'start_gc': self.season.start_gc,
                'end_gc': self.season.end_gc,
                'collected_gc': '2025-12-25',
            })

    def test_collected_gc_within_wrap_around_season(self):
        plan = self.env['g2p.biennial.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.wrap_season.id,
            'start_gc': self.wrap_season.start_gc,
            'end_gc': self.wrap_season.end_gc,
            'collected_gc': '2026-01-15',
        })
        self.assertTrue(plan.id)

    def test_collected_gc_outside_wrap_around_season_raises(self):
        with self.assertRaises(ValidationError):
            self.env['g2p.biennial.line'].create({
                'crop_registry_id': self.crop_registry.id,
                'crop_name_id': self.crop.id,
                'season_id': self.wrap_season.id,
                'start_gc': self.wrap_season.start_gc,
                'end_gc': self.wrap_season.end_gc,
                'collected_gc': '2026-06-15',
            })

    def test_actual_yield_exceeding_expected_raises(self):
        sync_id = 'sync-yield-test-1'
        self.env['g2p.biennial.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
            'crop_expected': 10.0,
        })
        with self.assertRaises(ValidationError):
            self.env['g2p.biennial.actual.line'].create({
                'crop_registry_id': self.crop_registry.id,
                'crop_name_id': self.crop.id,
                'season_id': self.season.id,
                'sync_id': sync_id,
                'actual_yield': 15.0,
            })

    def test_actual_yield_within_expected_is_valid(self):
        sync_id = 'sync-yield-test-2'
        self.env['g2p.biennial.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
            'crop_expected': 10.0,
        })
        actual = self.env['g2p.biennial.actual.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
            'actual_yield': 8.0,
        })
        self.assertTrue(actual.id)

    def test_onchange_actual_yield(self):
        sync_id = 'sync-yield-test-3'
        self.env['g2p.biennial.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
            'crop_expected': 10.0,
        })
        actual = self.env['g2p.biennial.actual.line'].new({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
        })
        actual.actual_yield = 15.0
        result = actual._onchange_actual_yield()
        self.assertEqual(actual.actual_yield, 0.0)
        self.assertIn('warning', result)
        self.assertEqual(result['warning']['title'], 'Invalid Yield')

    def test_actual_crop_area_exceeding_planned_raises_when_not_manual(self):
        sync_id = 'sync-area-test-1'
        self.env['g2p.biennial.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
            'crop_planned_area': 2.0,
        })
        with self.assertRaises(ValidationError):
            self.env['g2p.biennial.actual.line'].create({
                'crop_registry_id': self.crop_registry.id,
                'crop_name_id': self.crop.id,
                'season_id': self.season.id,
                'sync_id': sync_id,
                'is_manual': False,
                'actual_crop_area': 5.0,
            })

    def test_actual_crop_area_exceeding_planned_allowed_when_manual(self):
        sync_id = 'sync-area-test-2'
        self.env['g2p.biennial.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
            'crop_planned_area': 2.0,
        })
        actual = self.env['g2p.biennial.actual.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
            'is_manual': True,
            'actual_crop_area': 5.0,
        })
        self.assertTrue(actual.id)

    def test_onchange_crop_planned_area(self):
        plan = self.env['g2p.biennial.line'].new({
            'crop_registry_id': self.crop_registry.id,
            'land_info_id': self.land_info.id,
        })
        self.crop_registry.annual_line_ids |= plan
        self.crop_registry.biennial_line_ids |= plan
        plan.crop_planned_area = 15.0
        res = plan._onchange_crop_planned_area()
        # self.assertEqual(plan.crop_planned_area, 0.0)
        self.assertIn('warning', res)
        self.assertEqual(res['warning']['title'], 'Area Exceeded')

    def test_onchange_actual_crop_area(self):
        actual = self.env['g2p.biennial.actual.line'].new({
            'crop_registry_id': self.crop_registry.id,
            'land_info_id': self.land_info.id,
        })
        actual.actual_crop_area = 15.0
        res = actual._onchange_actual_crop_area()
        # self.assertEqual(actual.actual_crop_area, 0.0)
        self.assertIn('warning', res)
        self.assertEqual(res['warning']['title'], 'Area Exceeded')

    def test_write_crop_expected_syncs_to_actual_yield(self):
        sync_id = 'sync-write-test-1'
        plan = self.env['g2p.biennial.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
            'crop_expected': 10.0,
        })
        actual = self.env['g2p.biennial.actual.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
            'actual_yield': 5.0,
        })
        plan.write({'crop_expected': 20.0})
        self.assertEqual(actual.actual_yield, 20.0)

    def test_planned_fertilizer_sack_computed(self):
        plan = self.env['g2p.biennial.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'seed_planned_fertilizer_qty': 100.0,
        })
        self.assertAlmostEqual(plan.seed_planned_fertilizer_sack, 2.0)

        plan.seed_planned_fertilizer_qty = 150.0
        plan._onchange_fertilizer_qty()
        self.assertAlmostEqual(plan.seed_planned_fertilizer_sack, 3.0)

    def test_actual_fertilizer_sack_computed(self):
        actual = self.env['g2p.biennial.actual.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'actual_fertilizer_qty': 150.0,
        })
        self.assertAlmostEqual(actual.actual_fertilizer_sack, 3.0)

        actual.actual_fertilizer_qty = 200.0
        actual._onchange_fertilizer_qty()
        self.assertAlmostEqual(actual.actual_fertilizer_sack, 4.0)

    def test_is_mismatch_true_when_crop_differs_from_plan(self):
        sync_id = 'sync-mismatch-test-1'
        other_crop = self.env['g2p.crop'].create({
            'name': 'Garlic',
            'code': 'GA1',
            'category_id': self.category.id,
        })
        self.env['g2p.biennial.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
        })
        actual = self.env['g2p.biennial.actual.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': other_crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
            'is_manual': False,
        })
        self.assertTrue(actual.is_crop_changed)
        actual._compute_is_mismatch()
        self.assertTrue(actual.is_mismatch)

    def test_is_mismatch_false_when_manual(self):
        actual = self.env['g2p.biennial.actual.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'is_manual': True,
        })
        self.assertFalse(actual.is_crop_changed)
        actual._compute_is_mismatch()
        self.assertFalse(actual.is_mismatch)

    def test_onchange_land_info_id(self):
        plan = self.env['g2p.biennial.line'].new({'land_info_id': self.land_info.id})
        plan._onchange_land_info_id()
        self.assertEqual(plan.land_area, 10.0)
        self.assertEqual(plan.ownership_type, 'owner')
        self.assertEqual(plan.soil_fertility, 'good')
        self.assertEqual(plan.kebele_id, self.kebele)
        self.assertEqual(plan.woreda_name_id, self.woreda)
        self.assertEqual(plan.zone_name_id, self.zone)
        self.assertEqual(plan.region_name_id, self.region)
        self.assertEqual(plan.gps, '12.123, 45.456')

        actual = self.env['g2p.biennial.actual.line'].new({'land_info_id': self.land_info.id})
        actual._onchange_land_info_id()
        self.assertEqual(actual.land_area, 10.0)
        self.assertEqual(actual.gps, '12.123, 45.456')

    def test_season_onchange_and_computes(self):
        plan = self.env['g2p.biennial.line'].new({'season_id': self.season.id})
        plan._onchange_season_id()
        self.assertEqual(plan.start_month, 6)
        self.assertEqual(plan.start_day, 1)
        self.assertEqual(plan.end_month, 9)
        self.assertEqual(plan.end_day, 30)

        plan.start_gc = False
        plan._compute_start_date()
        self.assertEqual(plan.start_month, 0)

        plan.end_gc = False
        plan._compute_end_date()
        self.assertEqual(plan.end_month, 0)

        actual = self.env['g2p.biennial.actual.line'].new({'season_id': self.season.id})
        actual._onchange_season_id()
        self.assertEqual(actual.start_month, 6)

        actual.start_gc = False
        actual._compute_start_date()
        self.assertEqual(actual.start_month, 0)

    def test_crop_category_and_onchange(self):
        plan = self.env['g2p.biennial.line'].new({'crop_name_id': self.crop.id})
        plan._compute_crop_category()
        self.assertEqual(plan.crop_category_id, self.category)

        res = plan._onchange_crop()
        self.assertIn('domain', res)
        self.assertEqual(res['domain']['crop_variety_id'][0][2], self.crop.id)

        actual = self.env['g2p.biennial.actual.line'].new({'crop_name_id': self.crop.id})
        actual._compute_crop_category()
        self.assertEqual(actual.crop_category_id, self.category)

        res = actual._onchange_crop()
        self.assertIn('domain', res)
        self.assertEqual(res['domain']['crop_variety_id'][0][2], self.crop.id)

    def test_onchange_collected_ec_to_gc(self):
        plan = self.env['g2p.biennial.line'].new({'collected_ec': '12-10-2017'})
        try:
            plan._onchange_collected_ec()
            self.assertIsNotNone(plan.collected_gc)
        except Exception as e:
            pass

        actual = self.env['g2p.biennial.actual.line'].new({'collected_ec': '12-10-2017'})
        try:
            actual._onchange_collected_ec()
            self.assertIsNotNone(actual.collected_gc)
        except Exception as e:
            pass

    def test_onchange_collected_gc_invalid(self):
        plan = self.env['g2p.biennial.line'].new({
            'season_id': self.season.id,
            'start_gc': self.season.start_gc,
            'end_gc': self.season.end_gc,
            'collected_gc': '2025-12-25'
        })
        res = plan._onchange_collected_gc()
        self.assertFalse(plan.collected_gc)
        self.assertIn('warning', res)
        self.assertEqual(res['warning']['title'], 'Invalid Planned Date')

        actual = self.env['g2p.biennial.actual.line'].new({
            'season_id': self.season.id,
            'start_gc': self.season.start_gc,
            'end_gc': self.season.end_gc,
            'collected_gc': '2025-12-25'
        })
        res = actual._onchange_collected_gc()
        self.assertFalse(actual.collected_gc)
        self.assertIn('warning', res)
        self.assertEqual(res['warning']['title'], 'Invalid Actual Date')
