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

        cls.season = cls.env['g2p.season'].search([], limit=1)
        if not cls.season:
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
        self.assertTrue(production.name)
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
                'actual_sowing_date': '2100-07-01',
                'harvest_date': '2100-06-15',
            })

    def test_harvest_date_after_sowing_valid(self):
        production = self.env['g2p.crop.production'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'actual_sowing_date': '2100-07-01',
            'harvest_date': '2100-10-15',
        })
        self.assertTrue(production.id)

    def test_onchange_harvest_date(self):
        production = self.env['g2p.crop.production'].new({
            'crop_registry_id': self.crop_registry.id,
            'actual_sowing_date': '2100-07-01',
        })
        production.harvest_date = '2100-06-15'
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
            'actual_crop_area': 12.0,
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

    # ------------------------------------------------------------------
    # Sowing Cluster Lines Workflow
    # ------------------------------------------------------------------

    def test_cluster_line_workflow(self):
        production = self.env['g2p.crop.production'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'actual_crop_area': 10.0,
        })

        cluster_info = self.env['g2p.cluster.information'].create({'cluster_name': 'Test Cluster'})
        # Add cluster line
        cluster_line = self.env['g2p.crop.production.cluster.line'].create({
            'production_id': production.id,
            'cluster_info_id': cluster_info.id,
            'area_sown': 5.0
        })
        self.assertTrue(cluster_line.id)
        self.assertEqual(len(production.production_cluster_line_ids), 1)
        self.assertEqual(production.production_cluster_line_ids.area_sown, 5.0)

    # ------------------------------------------------------------------
    # Cluster Information Computes & Constraints
    # ------------------------------------------------------------------

    def test_cluster_area_conversion_and_onchange(self):
        annual_line = self.env['g2p.annual.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'crop_planned_area': 5.0,
        })

        cluster_info = self.env['g2p.cluster.information'].create({
            'cluster_name': 'Valley Cluster',
            'annual_line_id': annual_line.id,
            'cluster_area_timad': 10.0, # 10 timad = 2.5 ha
        })

        self.assertAlmostEqual(cluster_info.cluster_area_hectare, 2.5)

        # Onchange area timad exceeding planned area (e.g. 30 timad = 7.5 ha > 5.0 ha)
        cluster_info_onchange = self.env['g2p.cluster.information'].new({
            'annual_line_id': annual_line.id,
            'cluster_area_timad': 30.0,
        })
        res = cluster_info_onchange._onchange_cluster_area_timad()
        self.assertEqual(cluster_info_onchange.cluster_area_timad, 0.0)
        self.assertIn('warning', res)
        self.assertEqual(res['warning']['title'], 'Area Exceeded')

    def test_cluster_farmer_line_onchange_and_constraints(self):
        cluster_info = self.env['g2p.cluster.information'].create({
            'cluster_name': 'Highland Cluster',
            'cluster_smallholders': 1,
            'cluster_farmer_line_ids': [
                (0, 0, {'farmer_id': self.partner.id}),
            ]
        })

        farmer_line_new = self.env['g2p.cluster.farmer.line'].new({
            'cluster_info_id': cluster_info.id,
            'farmer_id': self.partner.id,
        })
        farmer_line_new._onchange_farmer_id()
        self.assertEqual(farmer_line_new.farmer_name, self.partner.name)

        # Farmer count constraint violation (1 line != 2 smallholders)
        with self.assertRaises(ValidationError):
            cluster_info.write({'cluster_smallholders': 2})
            cluster_info.flush_recordset()

    def test_cluster_season_date_computes(self):
        cluster_info = self.env['g2p.cluster.information'].create({
            'cluster_name': 'Season Cluster',
            'season_id': self.season.id,
        })

        self.assertEqual(cluster_info.start_gc, self.season.start_gc)
        self.assertEqual(cluster_info.end_gc, self.season.end_gc)
        self.assertEqual(cluster_info.start_month, 6)
        self.assertEqual(cluster_info.start_day, 1)
        self.assertEqual(cluster_info.end_month, 9)
        self.assertEqual(cluster_info.end_day, 30)

    def test_actual_planted_date_sync_to_production(self):
        # Create an annual actual crop line
        sync_id = 'sync-planted-date-test-1'
        actual = self.env['g2p.annual.actual.line'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
            'collected_gc': '2025-06-15',
        })

        # We need a corresponding production record linked by sync_id
        production = self.env['g2p.crop.production'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'sync_id': sync_id,
        })

        # Call sync
        self.crop_registry._sync_production_cached_values()

        # Verify the actual_sowing_date on production matches actual's collected_gc
        self.assertEqual(production.actual_sowing_date.strftime('%Y-%m-%d'), '2025-06-15')

        # Now edit the actual crop line collected_gc directly
        actual.write({'collected_gc': '2025-07-20'})

        # The actual_sowing_date on production should update automatically
        self.assertEqual(production.actual_sowing_date.strftime('%Y-%m-%d'), '2025-07-20')

    def test_infestation_incident_computes_and_onchanges(self):
        # Create a production record
        production = self.env['g2p.crop.production'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'actual_crop_area': 10.0,
            'area_sown': 8.0,
        })

        # 1. Test _compute_crop_name_id
        incident = self.env['g2p.crop.infestation.incident'].create({
            'production_id': production.id,
            'severity_level': 'low',
        })
        self.assertEqual(incident.crop_name_id, self.crop)

        # 2. Test _compute_infestation_flags & _onchange_infestation_types
        inf_type_pest = self.env['g2p.infestation.type'].create({'name': 'Pest', 'code': 'pest'})
        incident.infestation_type_ids = [(4, inf_type_pest.id)]

        # Trigger compute
        incident._compute_infestation_flags()
        self.assertTrue(incident.is_pest)
        self.assertFalse(incident.is_weed)

        # Trigger onchange
        incident._onchange_infestation_types()
        self.assertTrue(incident.is_pest)

        # 3. Test _onchange_observation_date
        incident.observation_date = '2025-06-15'
        incident._onchange_observation_date()
        self.assertTrue(incident.observation_date_ec)

        # 4. Test _onchange_observation_date_ec
        # Let's test YYYY-MM-DD format (e.g. 2017-10-09 Ethiopian)
        incident.observation_date_ec = '09.10.2017'
        incident._onchange_observation_date_ec()
        self.assertTrue(incident.observation_date)

        # 5. Test _check_estimated_damage
        # Valid percent
        incident.estimated_damage = '50%'
        incident._check_estimated_damage() # Should not raise

        # Invalid percent
        with self.assertRaises(ValidationError):
            incident.estimated_damage = '150%'

        # Valid area (under sown area of 8.0)
        incident.estimated_damage = '5 ha'
        incident._check_estimated_damage() # Should not raise

        # Invalid area (exceeding sown area of 8.0)
        with self.assertRaises(ValidationError):
            incident.estimated_damage = '12 ha'

        # Invalid format
        with self.assertRaises(ValidationError):
            incident.estimated_damage = 'invalid'

    def test_production_cluster_flags_and_info(self):
        production = self.env['g2p.crop.production'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
        })

        cluster_status_ind = self.env['g2p.cluster.status'].create({'name': 'Independent'})
        production.cluster_status_ids = [(4, cluster_status_ind.id)]

        # Trigger compute
        production._compute_cluster_status_flags()
        self.assertTrue(production.is_independent)
        self.assertFalse(production.is_clustered)

        # Trigger cluster info ids compute
        production._compute_cluster_info_ids()

    def test_production_menu_title_and_approval_workflow(self):
        production = self.env['g2p.crop.production'].create({
            'crop_registry_id': self.crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
        })

        # 1. Test _compute_menu_title
        production.with_context(menu_title='Harvest Details')._compute_menu_title()
        self.assertEqual(production.menu_title, 'Harvest Details')

        # 2. Test _compute_can_approve & action_approve
        sms_group = self.env.ref('g2p_crop_registry.group_woreda_sms')
        self.env.user.write({'groups_id': [(4, sms_group.id)]})

        # Ensure state, lifecycle_stage, and sowing_state are set to draft/sowing
        production.crop_registry_id.write({
            'state': 'draft',
            'lifecycle_stage': 'cultivation_approved',
            'sowing_state': 'draft'
        })
        # Force recompute
        production._compute_can_approve()
        self.assertTrue(production.can_approve)

        # Run approve
        production.action_approve_sms()
        self.assertEqual(production.crop_registry_id.sowing_state, 'pending_wah')

        # 3. Test action_reject
        # It should return action for reject wizard
        reject_action = production.action_reject()
        self.assertEqual(reject_action['res_model'], 'g2p.crop.reject.wizard')

        # 4. Test action_set_draft
        production.action_set_draft()
        self.assertEqual(production.crop_registry_id.sowing_state, 'draft')

        # 5. Test action_suggest_edit
        edit_action = production.action_suggest_edit()
        self.assertEqual(edit_action['res_model'], 'g2p.crop.request.wiz')

