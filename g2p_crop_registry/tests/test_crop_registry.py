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
            'farmer_display_id': 'Test Farmer',
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
            'farmer_display_id': 'Test Farmer',
        })
        crop_registry._compute_has_no_planning_data()
        self.assertTrue(crop_registry.has_no_planning_data)

    def test_has_no_planning_data_false(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'farmer_display_id': 'Test Farmer',
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

    # def test_onchange_land_info_id(self):
    #     crop_registry = self.env['g2p.crop.registry'].new({'land_info_id': self.land_info.id})
    #     crop_registry._onchange_land_info_id()
    #     self.assertEqual(crop_registry.land_area, 10.0)
    #     self.assertEqual(crop_registry.ownership_type, 'owner')
    #     self.assertEqual(crop_registry.woreda_id, self.woreda)
    #     self.assertEqual(crop_registry.kebele_id, self.kebele)

    # def test_onchange_crop_id_and_primary_details(self):
    #     crop_registry = self.env['g2p.crop.registry'].new({'crop_name_id': self.crop.id})
    #     crop_registry._onchange_crop_id_and_primary_details()
    #     self.assertEqual(crop_registry.crop_category_id, self.category)

    def test_compute_actual_crop_area_exceeded(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'farmer_display_id': 'Test Farmer',
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
            'farmer_display_id': 'Test Farmer',
            'land_info_id': self.land_info.id,
        })
        line = self.env['g2p.annual.line'].create({
            'crop_registry_id': crop_registry.id,
            'crop_name_id': self.crop.id,
            'season_id': self.season.id,
            'land_info_id': self.land_info.id,
            'crop_planned_area': 12.0
        })
        res = line._onchange_crop_planned_area()
        self.assertIn('warning', res)

    def test_check_actual_crop_area_limits(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'farmer_display_id': 'Test Farmer',
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
            'farmer_display_id': 'Test Farmer',
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
        crop_registry._onchange_sync_actual_to_production_annual()
        crop_registry._onchange_sync_production_to_actual()

        crop_registry._sync_production_cached_values()
        crop_registry._sync_crop_information()

        self.assertTrue(crop_registry.id)

    # ------------------------------------------------------------------
    # Approval and Rejection Workflows
    # ------------------------------------------------------------------

    def test_approval_workflow(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'farmer_display_id': 'Test Farmer',
        })
        self.assertEqual(crop_registry.state, 'draft')
        self.assertEqual(crop_registry.planning_state, 'draft')
        crop_registry.action_approve_sms()
        self.assertEqual(crop_registry.state, 'pending_wah')
        self.assertEqual(crop_registry.planning_state, 'pending_wah')
        crop_registry.action_approve_wah()
        self.assertEqual(crop_registry.planning_state, 'approved')
        self.assertEqual(crop_registry.lifecycle_stage, 'planning_approved')
        self.assertEqual(crop_registry.cultivation_state, 'draft')
        self.assertEqual(crop_registry.state, 'draft')

    def test_rejection_workflow(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'farmer_display_id': 'Test Farmer',
        })
        self.assertEqual(crop_registry.state, 'draft')

        # Simulate rejection via wizard
        wizard = self.env['g2p.crop.reject.wizard'].with_context(active_model='g2p.crop.registry', active_ids=[crop_registry.id]).create({
            'reason': 'Missing documentation.'
        })
        wizard.confirm_rejection()

        self.assertEqual(crop_registry.state, 'rejected')
        self.assertEqual(crop_registry.rejection_reason, 'Missing documentation.')

    def test_can_approve_logic(self):
        # Create users
        da_user = self.env['res.users'].create({
            'name': 'DA User',
            'login': 'da_user_test',
            'groups_id': [(6, 0, [self.env.ref('g2p_crop_registry.group_development_agent').id, self.env.ref('base.group_user').id])]
        })
        sms_user = self.env['res.users'].create({
            'name': 'SMS User',
            'login': 'sms_user_test',
            'groups_id': [(6, 0, [self.env.ref('g2p_crop_registry.group_woreda_sms').id, self.env.ref('base.group_user').id])]
        })
        wah_user = self.env['res.users'].create({
            'name': 'WAH User',
            'login': 'wah_user_test',
            'groups_id': [(6, 0, [self.env.ref('g2p_crop_registry.group_woreda_agri_office_head').id, self.env.ref('base.group_user').id])]
        })

        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'farmer_display_id': 'Test Farmer',
        })
        crop_registry.with_context(bypass_write=True).write({'state': 'approved'})

        self.assertTrue(da_user.has_group('g2p_crop_registry.group_development_agent'))
        self.assertTrue(sms_user.has_group('g2p_crop_registry.group_woreda_sms'))
        self.assertTrue(wah_user.has_group('g2p_crop_registry.group_woreda_agri_office_head'))

        # DA creates a change request
        change_request_da = self.env['g2p.crop.change.request'].with_user(da_user).create({
            'crop_registry_id': crop_registry.id,
            'requested_by': da_user.id,
            'new_values': {'land_area': 20.0},
        })
        self.assertEqual(change_request_da.requested_by, da_user)

        # SMS creates a change request
        change_request_sms = self.env['g2p.crop.change.request'].with_user(sms_user).create({
            'crop_registry_id': crop_registry.id,
            'requested_by': sms_user.id,
            'new_values': {'land_area': 30.0},
        })

        # Check permissions for DA's request
        self.assertFalse(change_request_da.with_user(da_user).can_approve)
        change_request_da.invalidate_recordset(['can_approve'])
        self.assertTrue(change_request_da.with_user(sms_user).can_approve)
        change_request_da.invalidate_recordset(['can_approve'])
        self.assertTrue(change_request_da.with_user(wah_user).can_approve)

        # Check permissions for SMS's request
        self.assertFalse(change_request_sms.with_user(da_user).can_approve)
        change_request_sms.invalidate_recordset(['can_approve'])
        self.assertFalse(change_request_sms.with_user(sms_user).can_approve)
        change_request_sms.invalidate_recordset(['can_approve'])
        self.assertTrue(change_request_sms.with_user(wah_user).can_approve)

    # ------------------------------------------------------------------
    # SMS Update Request Workflow
    # ------------------------------------------------------------------

    def test_sms_edit_intercept(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'farmer_display_id': 'Test Farmer',
        })
        crop_registry.with_context(bypass_write=True).write({'state': 'approved'})
        self.assertEqual(crop_registry.state, 'approved')

        # Create SMS User
        sms_user = self.env['res.users'].create({
            'name': 'Test SMS User',
            'login': 'testsms',
            'groups_id': [(6, 0, [self.env.ref('g2p_crop_registry.group_woreda_sms').id, self.env.ref('base.group_user').id])]
        })

        # Create WAH User
        wah_user = self.env['res.users'].create({
            'name': 'Test WAH User',
            'login': 'testwah',
            'groups_id': [(6, 0, [self.env.ref('g2p_crop_registry.group_woreda_agri_office_head').id, self.env.ref('base.group_user').id])]
        })

        # SMS user edits the approved record
        crop_registry.with_user(sms_user).write({
            'farmer_display_id': 'Updated Name by SMS'
        })

        # Verify state changed to update_requested
        self.assertEqual(crop_registry.state, 'update_requested')

        # Verify change request created
        change_request = self.env['g2p.crop.change.request'].search([('crop_registry_id', '=', crop_registry.id)])
        self.assertEqual(len(change_request), 1)
        self.assertEqual(change_request.state, 'pending')
        self.assertIn('farmer_display_id', change_request.new_values)
        self.assertEqual(change_request.new_values['farmer_display_id'], 'Updated Name by SMS')

        # WAH user approves the change request
        change_request.with_user(wah_user).approve_changes()

        # Verify record is updated and state restored
        self.assertEqual(crop_registry.farmer_display_id, 'Updated Name by SMS')
        self.assertEqual(crop_registry.state, 'approved')
        self.assertEqual(change_request.state, 'approved')

    def test_sms_edit_intercept_rejection(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'farmer_display_id': 'Original Name'
        })
        crop_registry.with_context(bypass_write=True).write({'state': 'approved'})

        # Create SMS User
        sms_user = self.env['res.users'].create({
            'name': 'Test SMS User',
            'login': 'testsms2',
            'groups_id': [(6, 0, [self.env.ref('g2p_crop_registry.group_woreda_sms').id, self.env.ref('base.group_user').id])]
        })

        # Create WAH User
        wah_user = self.env['res.users'].create({
            'name': 'Test WAH User',
            'login': 'testwah2',
            'groups_id': [(6, 0, [self.env.ref('g2p_crop_registry.group_woreda_agri_office_head').id, self.env.ref('base.group_user').id])]
        })

        # SMS user edits
        crop_registry.with_user(sms_user).write({
            'farmer_display_id': 'Hacked Name'
        })
        self.assertEqual(crop_registry.state, 'update_requested')

        change_request = self.env['g2p.crop.change.request'].search([('crop_registry_id', '=', crop_registry.id)])

        # WAH user rejects the change request
        change_request.with_user(wah_user).reject_changes()

        # Verify record is NOT updated and state restored
        self.assertEqual(crop_registry.farmer_display_id, 'Original Name')
        self.assertEqual(crop_registry.state, 'approved')
        self.assertEqual(change_request.state, 'rejected')

    def test_crop_edit_request_workflow(self):
        crop_registry = self.env['g2p.crop.registry'].create({
            'partner_id': self.partner.id,
            'fyda_id': 'FAN-1234567890123456',
            'farmer_display_id': 'Edit Request Test'
        })
        crop_registry.with_context(bypass_write=True).write({'state': 'approved', 'edit_state': 'locked'})

        # Create DA, SMS, and WAH users
        da_user = self.env['res.users'].create({
            'name': 'Test DA User',
            'login': 'testda_edit',
            'groups_id': [(6, 0, [self.env.ref('g2p_crop_registry.group_development_agent').id, self.env.ref('base.group_user').id])]
        })
        sms_user = self.env['res.users'].create({
            'name': 'Test SMS User',
            'login': 'testsms_edit',
            'groups_id': [(6, 0, [self.env.ref('g2p_crop_registry.group_woreda_sms').id, self.env.ref('base.group_user').id])]
        })
        wah_user = self.env['res.users'].create({
            'name': 'Test WAH User',
            'login': 'testwah_edit',
            'groups_id': [(6, 0, [self.env.ref('g2p_crop_registry.group_woreda_agri_office_head').id, self.env.ref('base.group_user').id])]
        })

        # Create edit request by DA
        edit_request = self.env['g2p.crop.edit.request'].with_user(da_user).create({
            'crop_registry_id': crop_registry.id,
            'reason': 'Need to edit crop details.',
            'type': 'edit',
        })

        # Verify default status and computes
        self.assertEqual(edit_request.status, 'newSuggestion')
        self.assertEqual(edit_request.requester_id, da_user)

        # Test can_approve logic: SMS and WAH can approve DA's request, but DA cannot
        self.assertFalse(edit_request.with_user(da_user).can_approve)
        edit_request.invalidate_recordset(['can_approve'])
        self.assertTrue(edit_request.with_user(sms_user).can_approve)
        edit_request.invalidate_recordset(['can_approve'])
        self.assertTrue(edit_request.with_user(wah_user).can_approve)

        # SMS approves: it should forward to WAH, appending forwarded message and changing requester_id to SMS user
        edit_request.with_user(sms_user).accept_request()
        self.assertEqual(edit_request.requester_id, sms_user)
        self.assertIn('[Forwarded by SMS:', edit_request.reason)
        # Verify status is still newSuggestion (not accepted yet)
        self.assertEqual(edit_request.status, 'newSuggestion')

        # WAH approves the forwarded request: should set status to accepted and open the registry
        edit_request.with_user(wah_user).accept_request()
        self.assertEqual(edit_request.status, 'accepted')
        self.assertEqual(crop_registry.edit_state, 'open')

        # Reject workflow:
        edit_request.with_user(wah_user).reject_request()
        self.assertEqual(edit_request.status, 'rejected')
        self.assertEqual(crop_registry.edit_state, 'locked')

