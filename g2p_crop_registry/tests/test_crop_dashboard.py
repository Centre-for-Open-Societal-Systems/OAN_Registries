from odoo.tests.common import TransactionCase

class TestCropDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ---------------------------------------------------------
        # Setup Core Models: Partner, Crops, Seasons, Locations
        # ---------------------------------------------------------
        cls.partner_1 = cls.env['res.partner'].create({
            'name': 'Farmer One',
            'is_farmer': 'yes',
        })
        cls.partner_2 = cls.env['res.partner'].create({
            'name': 'Farmer Two',
            'is_farmer': 'yes',
        })

        cls.category_1 = cls.env['g2p.crop.category'].create({
            'name': 'Cereal',
        })
        cls.category_2 = cls.env['g2p.crop.category'].create({
            'name': 'Legumes',
        })

        cls.crop_1 = cls.env['g2p.crop'].create({
            'name': 'Wheat',
            'category_id': cls.category_1.id,
        })
        cls.crop_2 = cls.env['g2p.crop'].create({
            'name': 'Teff',
            'category_id': cls.category_1.id,
        })

        cls.season_1 = cls.env['g2p.season'].create({
            'name': 'Meher Season 1',
            'start_gc': '2025-06-01',
            'end_gc': '2025-09-30',
        })
        cls.season_2 = cls.env['g2p.season'].create({
            'name': 'Belg Season 2',
            'start_gc': '2025-02-01',
            'end_gc': '2025-05-31',
        })

        # Location Hierarchy
        cls.region_1 = cls.env['g2p.region'].create({'name': 'Oromia', 'code': 'R1'})
        cls.zone_1 = cls.env['g2p.zone'].create({'name': 'Arsi', 'code': 'Z1', 'region': cls.region_1.id})
        cls.woreda_1 = cls.env['g2p.woreda'].create({'name': 'Woreda 1', 'code': 'W1', 'zone': cls.zone_1.id})
        cls.kebele_1 = cls.env['g2p.kebele'].create({'name': 'Kebele 1', 'code': 'K1', 'woreda': cls.woreda_1.id})

        cls.region_2 = cls.env['g2p.region'].create({'name': 'Amhara', 'code': 'R2'})
        cls.zone_2 = cls.env['g2p.zone'].create({'name': 'Gojjam', 'code': 'Z2', 'region': cls.region_2.id})
        cls.woreda_2 = cls.env['g2p.woreda'].create({'name': 'Woreda 2', 'code': 'W2', 'zone': cls.zone_2.id})
        cls.kebele_2 = cls.env['g2p.kebele'].create({'name': 'Kebele 2', 'code': 'K2', 'woreda': cls.woreda_2.id})

        # Land Info
        cls.land_info_1 = cls.env['g2p.land.information'].create({
            'total_land_area': 10.0,
            'ownership_type': 'owner',
            'soil_fertility': 'good',
            'land_kebele': cls.kebele_1.id,
            'partner_id': cls.partner_1.id,
        })
        cls.land_info_2 = cls.env['g2p.land.information'].create({
            'total_land_area': 8.0,
            'ownership_type': 'owner',
            'soil_fertility': 'good',
            'land_kebele': cls.kebele_2.id,
            'partner_id': cls.partner_2.id,
        })

        # ---------------------------------------------------------
        # Setup Registries and Lines
        # ---------------------------------------------------------

        # Registry 1: Farmer One, Region 1, Zone 1, Woreda 1
        cls.registry_1 = cls.env['g2p.crop.registry'].create({
            'partner_id': cls.partner_1.id,
            'fyda_id': 'FAN-1111222233334444',
            'farmer_display_id': 'Farmer One',
            'region_id': cls.region_1.id,
            'zone_id': cls.zone_1.id,
            'woreda_id': cls.woreda_1.id,
            'kebele_id': cls.kebele_1.id,
        })

        # Planned Lines for Registry 1
        cls.planned_annual_1 = cls.env['g2p.annual.line'].create({
            'crop_registry_id': cls.registry_1.id,
            'crop_name_id': cls.crop_1.id,
            'season_id': cls.season_1.id,
            'crop_planned_area': 5.0,
            'crop_expected': 100.0,
            'land_info_id': cls.land_info_1.id,
            'sync_id': 'sync-plan-1',
        })

        # Actual Lines for Registry 1
        cls.actual_annual_1 = cls.env['g2p.annual.actual.line'].create({
            'crop_registry_id': cls.registry_1.id,
            'crop_name_id': cls.crop_1.id,
            'season_id': cls.season_1.id,
            'actual_crop_area': 4.0,
            'actual_yield': 80.0,
            'land_info_id': cls.land_info_1.id,
            'sync_id': 'sync-plan-1',
        })

        # Registry 2: Farmer Two, Region 2, Zone 2, Woreda 2
        cls.registry_2 = cls.env['g2p.crop.registry'].create({
            'partner_id': cls.partner_2.id,
            'fyda_id': 'FAN-5555666677778888',
            'farmer_display_id': 'Farmer Two',
            'region_id': cls.region_2.id,
            'zone_id': cls.zone_2.id,
            'woreda_id': cls.woreda_2.id,
            'kebele_id': cls.kebele_2.id,
        })

        # Planned Lines for Registry 2 (Annual & Perennial)
        cls.planned_annual_2 = cls.env['g2p.annual.line'].create({
            'crop_registry_id': cls.registry_2.id,
            'crop_name_id': cls.crop_2.id,
            'season_id': cls.season_2.id,
            'crop_planned_area': 3.0,
            'crop_expected': 60.0,
            'land_info_id': cls.land_info_2.id,
            'sync_id': 'sync-plan-2',
        })
        cls.planned_perennial_2 = cls.env['g2p.perennial.line'].create({
            'crop_registry_id': cls.registry_2.id,
            'crop_name_id': cls.crop_2.id,
            'season_id': cls.season_2.id,
            'crop_planned_area': 2.0,
            'crop_expected': 40.0,
            'land_info_id': cls.land_info_2.id,
            'sync_id': 'sync-plan-3',
        })

        # Actual Lines for Registry 2
        cls.actual_annual_2 = cls.env['g2p.annual.actual.line'].create({
            'crop_registry_id': cls.registry_2.id,
            'crop_name_id': cls.crop_2.id,
            'season_id': cls.season_2.id,
            'actual_crop_area': 3.0,
            'actual_yield': 60.0,
            'land_info_id': cls.land_info_2.id,
            'sync_id': 'sync-plan-2',
        })
        cls.actual_perennial_2 = cls.env['g2p.perennial.actual.line'].create({
            'crop_registry_id': cls.registry_2.id,
            'crop_name_id': cls.crop_2.id,
            'season_id': cls.season_2.id,
            'actual_crop_area': 1.0,
            'actual_yield': 20.0,
            'land_info_id': cls.land_info_2.id,
            'sync_id': 'sync-plan-3',
        })

        # Trigger computes on the registry records
        cls.registry_1._compute_primary_crop_details()
        cls.registry_2._compute_primary_crop_details()
        cls.env.flush_all()

    def test_get_dashboard_filter_options(self):
        """Test that get_dashboard_filter_options returns correct lists of regions, zones, woredas, crops, and seasons."""
        options = self.env['g2p.crop.registry'].get_dashboard_filter_options()

        self.assertIn('seasons', options)
        self.assertIn('crops', options)
        self.assertIn('regions', options)
        self.assertIn('zones', options)
        self.assertIn('woredas', options)

        # Check if the created items are present in the returned list
        season_ids = [s['id'] for s in options['seasons']]
        crop_ids = [c['id'] for c in options['crops']]
        region_ids = [r['id'] for r in options['regions']]
        zone_ids = [z['id'] for z in options['zones']]
        woreda_ids = [w['id'] for w in options['woredas']]

        self.assertIn(self.season_1.id, season_ids)
        self.assertIn(self.crop_1.id, crop_ids)
        self.assertIn(self.region_1.id, region_ids)
        self.assertIn(self.zone_1.id, zone_ids)
        self.assertIn(self.woreda_1.id, woreda_ids)

    def test_get_dashboard_stats_without_filters(self):
        """Test calculation of dashboard metrics and charts with no active filters."""
        stats = self.env['g2p.crop.registry'].get_dashboard_stats()

        # Expected Planned Area = 5 (plan 1) + 3 (plan 2) + 2 (perennial 2) = 10.0
        self.assertAlmostEqual(stats['total_planned_crop_area'], 10.0)

        # Expected Expected Yield = 100 + 60 + 40 = 200.0
        self.assertAlmostEqual(stats['total_expected_yield'], 200.0)

        # Expected Actual Area = 4 (actual 1) + 3 (actual 2) + 1 (actual perennial 2) = 8.0
        self.assertAlmostEqual(stats['total_actual_area'], 8.0)

        # Expected Actual Yield = 80 + 60 + 20 = 160.0
        self.assertAlmostEqual(stats['total_actual_yield'], 160.0)

        # Ratio Planned = 8.0 / 10.0 * 100 = 80.0
        self.assertAlmostEqual(stats['ratio_planned'], 80.0)

        # Yield Chart
        self.assertIn('Wheat', stats['top_crops_planned_labels'])
        self.assertIn('Teff', stats['top_crops_planned_labels'])

        # Top crops by area labels
        self.assertEqual(len(stats['top_crops_area_labels']), 2)
        
        # Region Yield Chart
        self.assertIn('Oromia', stats['region_labels'])
        self.assertIn('Amhara', stats['region_labels'])

        # Table data details
        self.assertEqual(len(stats['table_data']), 2) # Wheat (Registry 1), Teff (Registry 2)
        row_farmers = [row['farmer_name'] for row in stats['table_data']]
        self.assertIn('Farmer One', row_farmers)
        self.assertIn('Farmer Two', row_farmers)

    def test_get_dashboard_stats_with_crop_filter(self):
        """Test that get_dashboard_stats correctly filters stats based on crop_id."""
        stats = self.env['g2p.crop.registry'].get_dashboard_stats(filters={'crop_id': self.crop_1.id})

        # Since registry_1 has crop_1 (Wheat) and registry_2 has crop_2 (Teff)
        # Expected metrics for registry_1 only
        self.assertAlmostEqual(stats['total_planned_crop_area'], 5.0)
        self.assertAlmostEqual(stats['total_expected_yield'], 100.0)
        self.assertAlmostEqual(stats['total_actual_area'], 4.0)
        self.assertAlmostEqual(stats['total_actual_yield'], 80.0)

        self.assertEqual(stats['top_crops_planned_labels'], ['Wheat'])
        self.assertEqual(stats['top_crops_planned_data'], [100.0])
        self.assertEqual(stats['top_crops_actual_data'], [80.0])

    def test_get_dashboard_stats_with_region_filter(self):
        """Test that get_dashboard_stats correctly filters stats based on region_id."""
        stats = self.env['g2p.crop.registry'].get_dashboard_stats(filters={'region_id': self.region_2.id})

        # Amhara (registry_2) metrics:
        # planned area: 3.0 (annual) + 2.0 (perennial) = 5.0
        # actual area: 3.0 (annual) + 1.0 (perennial) = 4.0
        # expected yield: 60.0 (annual) + 40.0 (perennial) = 100.0
        # actual yield: 60.0 (annual) + 20.0 (perennial) = 80.0
        self.assertAlmostEqual(stats['total_planned_crop_area'], 5.0)
        self.assertAlmostEqual(stats['total_expected_yield'], 100.0)
        self.assertAlmostEqual(stats['total_actual_area'], 4.0)
        self.assertAlmostEqual(stats['total_actual_yield'], 80.0)

    def test_get_dashboard_stats_with_zone_filter(self):
        """Test that get_dashboard_stats correctly filters stats based on zone_id."""
        stats = self.env['g2p.crop.registry'].get_dashboard_stats(filters={'zone_id': self.zone_1.id})

        # Arsi (registry_1) metrics:
        self.assertAlmostEqual(stats['total_planned_crop_area'], 5.0)
        self.assertAlmostEqual(stats['total_expected_yield'], 100.0)
        self.assertAlmostEqual(stats['total_actual_area'], 4.0)
        self.assertAlmostEqual(stats['total_actual_yield'], 80.0)

    def test_get_dashboard_stats_with_woreda_filter(self):
        """Test that get_dashboard_stats correctly filters stats based on woreda_id."""
        stats = self.env['g2p.crop.registry'].get_dashboard_stats(filters={'woreda_id': self.woreda_2.id})

        # Woreda 2 (registry_2) metrics:
        self.assertAlmostEqual(stats['total_planned_crop_area'], 5.0)
        self.assertAlmostEqual(stats['total_expected_yield'], 100.0)
        self.assertAlmostEqual(stats['total_actual_area'], 4.0)
        self.assertAlmostEqual(stats['total_actual_yield'], 80.0)

    def test_get_dashboard_stats_with_season_filter(self):
        """Test that get_dashboard_stats correctly filters stats based on season_id."""
        stats = self.env['g2p.crop.registry'].get_dashboard_stats(filters={'season_id': self.season_1.id})

        # season_1 is associated only with annual_line of registry_1
        self.assertAlmostEqual(stats['total_planned_crop_area'], 5.0)
        self.assertAlmostEqual(stats['total_expected_yield'], 100.0)
        self.assertAlmostEqual(stats['total_actual_area'], 4.0)
        self.assertAlmostEqual(stats['total_actual_yield'], 80.0)

    def test_get_dashboard_stats_empty_results(self):
        """Test that get_dashboard_stats handles empty search results without error."""
        # Non-matching filter
        stats = self.env['g2p.crop.registry'].get_dashboard_stats(filters={'crop_id': 999999})

        self.assertAlmostEqual(stats['total_planned_crop_area'], 0.0)
        self.assertAlmostEqual(stats['total_expected_yield'], 0.0)
        self.assertAlmostEqual(stats['total_actual_area'], 0.0)
        self.assertAlmostEqual(stats['total_actual_yield'], 0.0)
        self.assertAlmostEqual(stats['ratio_planned'], 0.0)
        self.assertEqual(stats['top_crops_planned_labels'], [])
        self.assertEqual(stats['top_crops_planned_data'], [])
        self.assertEqual(stats['top_crops_actual_data'], [])
        self.assertEqual(stats['top_crops_area_labels'], [])
        self.assertEqual(stats['top_crops_area_data'], [])
        self.assertEqual(stats['table_data'], [])
