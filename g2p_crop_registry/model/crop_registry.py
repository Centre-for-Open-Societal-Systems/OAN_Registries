from odoo import api, fields, models
import re
from odoo.exceptions import ValidationError
import uuid




class G2PCrop(models.Model):
    _name = 'g2p.crop.registry'
    _description = 'G2p Crop Registry'
    _rec_name = 'name'

    name = fields.Char(string='Registry ID', required=True, copy=False, readonly=True, default=lambda self: 'New')

    # =======================================
    # UI Fields: Farmer Identity
    # =======================================
    partner_id = fields.Many2one('res.partner', string="Farmer ID", domain="[('is_farmer', '=', 'yes')]", required=True)
    fyda_id = fields.Char(string="Fayda ID", required=True)
    farmer_display_id = fields.Char(string='Farmer Name', required=True)
    region_id = fields.Many2one('g2p.region', string="Region",
                                     store=True
                                     )
    zone_id = fields.Many2one('g2p.zone',
                                   string='Zone',
                                   store=True
                                   )
    woreda_id = fields.Many2one('g2p.woreda',
                                     string='Woreda',
                                     store=True
                                     )
    kebele_id = fields.Many2one(
        'g2p.kebele',
        string='Kebele',
        domain="[('woreda', '=', woreda_id)]",
    )
    gps = fields.Char(string="GPS")

    # =======================================
    # UI Fields: Planning
    # =======================================
    annual_line_ids = fields.One2many(
        "g2p.annual.line",
        "crop_registry_id",
        string="Planned Input",
    )
    has_no_planning_data = fields.Boolean(
        string="Has No Planning Data",
        compute="_compute_has_no_planning_data"
    )

    @api.depends('annual_line_ids')
    def _compute_has_no_planning_data(self):
        for rec in self:
            rec.has_no_planning_data = not rec.annual_line_ids

    # =======================================
    # UI Fields: Cultivation / Land Preparation
    # =======================================
    actual_annual_line_ids = fields.One2many(
        "g2p.annual.actual.line",
        "crop_registry_id",
        string="Actual Input",
    )

    actual_crop_area_exceeded = fields.Boolean(compute="_compute_actual_crop_area_exceeded")
    actual_crop_area_warning = fields.Text(compute="_compute_actual_crop_area_exceeded")

    @api.depends('actual_annual_line_ids.actual_crop_area', 'actual_annual_line_ids.land_info_id')
    def _compute_actual_crop_area_exceeded(self):
        for rec in self:
            land_areas = {}
            for line in rec.actual_annual_line_ids:
                if line.land_info_id:
                    land_areas[line.land_info_id] = land_areas.get(line.land_info_id, 0.0) + line.actual_crop_area

            exceeded = False
            warning_msg = []
            for land, total_actual in land_areas.items():
                if total_actual > land.total_land_area:
                    exceeded = True
                    warning_msg.append(
                        f"The total land area for Land ID '{land.land_id}' is {land.total_land_area:.2f} ha, "
                        f"but the current value of the actual crop records is higher than that ({total_actual:.2f} ha)."
                    )
            rec.actual_crop_area_exceeded = exceeded
            rec.actual_crop_area_warning = "\n".join(warning_msg) if warning_msg else ""

    # =======================================
    # UI Fields: Sowing
    # =======================================
    production_detail_ids = fields.One2many(
        "g2p.crop.production",
        "crop_registry_id",
        string="Sowing Details",
    )

    # =======================================
    # UI Fields: Harvesting
    # =======================================
    harvest_detail_ids = fields.One2many(
        "g2p.crop.production",
        "crop_registry_id",
        string="Harvesting Details",
    )

    # =======================================
    # UI Fields: Survey Personnel
    # =======================================
    surveyor_name = fields.Char(string="DA Name")
    surveyor_mobile_number = fields.Char(string="DA Mobile Number")
    supervisor_name = fields.Char(string="Supervisor Name")
    supervisor_mobile_number = fields.Char(string="Supervisor Mobile Number")
    @api.depends_context('show_farmer_name_only')
    def _compute_display_name(self):
        for record in self:
            if self.env.context.get('show_farmer_name_only') and record.farmer_display_id:
                record.display_name = record.farmer_display_id
            else:
                record.display_name = record.name

    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_wah', 'Approval Level 1'),
        ('rejected', 'Rejected'),
        ('update_requested', 'Update Requested'),
        ('approved', 'Approval Level 2'),
    ], string="Status", default='draft', tracking=True)

    rejected_at_stage = fields.Selection([
        ('sms', 'SMS'),
        ('wah', 'WAH')
    ], string="Rejected at Stage", copy=False)

    planning_state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_wah', 'Approval Level 1'),
        ('rejected', 'Planning Rejected'),
        ('update_requested', 'Update Requested'),
        ('approved', 'Approval Level 2'),
    ], string="Planning Status", default='draft', tracking=True)

    cultivation_state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_wah', 'Approval Level 1'),
        ('rejected', 'Cultivation Rejected'),
        ('update_requested', 'Update Requested'),
        ('approved', 'Approval Level 2'),
    ], string="Cultivation Status", default='draft', tracking=True)

    sowing_state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_wah', 'Approval Level 1'),
        ('rejected', 'Sowing Rejected'),
        ('update_requested', 'Update Requested'),
        ('approved', 'Approval Level 2'),
    ], string="Sowing Status", default='draft', tracking=True)

    harvesting_state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_wah', 'Approval Level 1'),
        ('rejected', 'Harvesting Rejected'),
        ('update_requested', 'Update Requested'),
        ('approved', 'Approval Level 2'),
    ], string="Harvesting Status", default='draft', tracking=True)

    lifecycle_stage = fields.Selection([
        ('draft', 'Draft'),
        ('pending_planning', 'Pending Planning Approval'),
        ('planning_rejected', 'Planning Rejected'),
        ('planning_approved', 'Planning Approved'),
        ('pending_cultivation', 'Pending Cultivation Approval'),
        ('cultivation_rejected', 'Cultivation Rejected'),
        ('cultivation_approved', 'Cultivation Approved'),
        ('pending_sowing', 'Pending Sowing Approval'),
        ('sowing_rejected', 'Sowing Rejected'),
        ('sowing_approved', 'Sowing Approved'),
        ('pending_harvesting', 'Pending Harvesting Approval'),
        ('harvesting_rejected', 'Harvesting Rejected'),
        ('harvesting_approved', 'Harvesting Approved')
    ], string="Lifecycle Stage", default='draft', tracking=True)


    edit_state = fields.Selection(selection=[("open", "Open"), ("locked", "Locked")], default="open")
    edit_count = fields.Integer(default=0)
    update_request_ids = fields.One2many("g2p.crop.change.request", "crop_registry_id", string="Update Requests")
    edit_suggestion_ids = fields.One2many("g2p.crop.edit.request", "crop_registry_id", string="Edit Suggestions")

    is_da = fields.Boolean(compute='_compute_is_da', string="Is Development Agent")

    def _compute_is_da(self):
        for record in self:
            record.is_da = self.env.user.has_group('g2p_crop_registry.group_development_agent')

    rejection_reason = fields.Text(string="Rejection Reason", readonly=True)
    can_approve = fields.Boolean(compute='_compute_can_approve', string="Can Approve")
    can_set_draft = fields.Boolean(compute='_compute_can_approve', string="Can Set Draft")

    @api.depends('lifecycle_stage', 'planning_state', 'cultivation_state', 'sowing_state', 'harvesting_state')
    @api.depends_context('uid', 'menu_title')
    def _compute_can_approve(self):
        user = self.env.user
        is_sms = user.has_group('g2p_crop_registry.group_woreda_sms')
        is_wah = user.has_group('g2p_crop_registry.group_woreda_agri_office_head')
        is_admin = self.env.is_superuser()

        for req in self:
            menu_title = self.env.context.get('menu_title', '')
            if 'Planning' in menu_title:
                active_state = req.planning_state
            elif 'Cultivation' in menu_title:
                active_state = req.cultivation_state
            elif 'Sowing' in menu_title:
                active_state = req.sowing_state
            elif 'Harvesting' in menu_title:
                active_state = req.harvesting_state
            else:
                active_state = 'approved'
                if req.lifecycle_stage in ['draft', 'pending_planning', 'planning_rejected']:
                    active_state = req.planning_state
                elif req.lifecycle_stage in ['planning_approved', 'pending_cultivation', 'cultivation_rejected']:
                    active_state = req.cultivation_state
                elif req.lifecycle_stage in ['cultivation_approved', 'pending_sowing', 'sowing_rejected']:
                    active_state = req.sowing_state
                elif req.lifecycle_stage in ['sowing_approved', 'pending_harvesting', 'harvesting_rejected']:
                    active_state = req.harvesting_state

            can_approve = False
            can_set_draft = False

            if is_admin:
                can_approve = True
                can_set_draft = (active_state != 'draft')
            else:
                if active_state in ['draft', 'rejected']:
                    if is_sms or is_wah:
                        can_approve = True
                elif active_state == 'pending_wah':
                    if is_wah:
                        can_approve = True

                # Logic for "Set To Draft" visibility
                if active_state != 'draft':
                    if (is_wah or is_sms) and active_state != 'approved':
                        can_set_draft = True

            req.can_approve = can_approve
            req.can_set_draft = can_set_draft

    def action_approve_sms(self):
        user = self.env.user
        is_sms = user.has_group('g2p_crop_registry.group_woreda_sms')
        is_admin = self.env.is_superuser()
        if not (is_sms or is_admin):
            return

        for record in self:
            menu_title = self.env.context.get('menu_title', '')
            if 'Planning' in menu_title or record.lifecycle_stage in ['draft', 'pending_planning', 'planning_rejected']:
                if record.planning_state in ['draft', 'rejected']:
                    record.planning_state = 'pending_wah'
                    record.lifecycle_stage = 'pending_planning'
                    record.state = 'pending_wah'
            elif 'Cultivation' in menu_title or record.lifecycle_stage in ['planning_approved', 'pending_cultivation', 'cultivation_rejected']:
                if record.cultivation_state in ['draft', 'rejected']:
                    record.cultivation_state = 'pending_wah'
                    record.lifecycle_stage = 'pending_cultivation'
                    record.state = 'pending_wah'
            elif 'Sowing' in menu_title or record.lifecycle_stage in ['cultivation_approved', 'pending_sowing', 'sowing_rejected']:
                if record.sowing_state in ['draft', 'rejected']:
                    record.sowing_state = 'pending_wah'
                    record.lifecycle_stage = 'pending_sowing'
                    record.state = 'pending_wah'
            elif 'Harvesting' in menu_title or record.lifecycle_stage in ['sowing_approved', 'pending_harvesting', 'harvesting_rejected']:
                if record.harvesting_state in ['draft', 'rejected']:
                    record.harvesting_state = 'pending_wah'
                    record.lifecycle_stage = 'pending_harvesting'
                    record.state = 'pending_wah'

    def action_approve_wah(self):
        user = self.env.user
        is_wah = user.has_group('g2p_crop_registry.group_woreda_agri_office_head')
        is_admin = self.env.is_superuser()
        if not (is_wah or is_admin):
            return

        for record in self:
            menu_title = self.env.context.get('menu_title', '')
            if 'Planning' in menu_title or record.lifecycle_stage in ['draft', 'pending_planning', 'planning_rejected']:
                if record.planning_state in ['pending_wah', 'rejected']:
                    record.planning_state = 'approved'
                    record.lifecycle_stage = 'planning_approved'
                    record.cultivation_state = 'draft'
                    record.state = 'draft'
                    record._sync_planned_to_actual_backend()
            elif 'Cultivation' in menu_title or record.lifecycle_stage in ['planning_approved', 'pending_cultivation', 'cultivation_rejected']:
                if record.cultivation_state in ['pending_wah', 'rejected']:
                    record.cultivation_state = 'approved'
                    record.lifecycle_stage = 'cultivation_approved'
                    record.sowing_state = 'draft'
                    record.state = 'draft'
            elif 'Sowing' in menu_title or record.lifecycle_stage in ['cultivation_approved', 'pending_sowing', 'sowing_rejected']:
                if record.sowing_state in ['pending_wah', 'rejected']:
                    record.sowing_state = 'approved'
                    record.lifecycle_stage = 'sowing_approved'
                    record.harvesting_state = 'draft'
                    record.state = 'draft'
            elif 'Harvesting' in menu_title or record.lifecycle_stage in ['sowing_approved', 'pending_harvesting', 'harvesting_rejected']:
                if record.harvesting_state in ['pending_wah', 'rejected']:
                    record.harvesting_state = 'approved'
                    record.lifecycle_stage = 'harvesting_approved'
                    record.state = 'approved'

    def _advance_lifecycle(self):
        pass

    def action_set_draft(self):
        for record in self:
            rejected_stage = record.rejected_at_stage
            record.rejected_at_stage = False
            menu_title = self.env.context.get('menu_title', '')

            stage = ''
            if menu_title:
                if 'Planning' in menu_title:
                    stage = 'planning'
                elif 'Cultivation' in menu_title:
                    stage = 'cultivation'
                elif 'Sowing' in menu_title:
                    stage = 'sowing'
                elif 'Harvesting' in menu_title:
                    stage = 'harvesting'

            if not stage:
                if record.lifecycle_stage in ('pending_sowing', 'sowing_rejected', 'sowing_approved'):
                    stage = 'sowing'
                elif record.lifecycle_stage in ('pending_harvesting', 'harvesting_rejected', 'harvesting_approved'):
                    stage = 'harvesting'
                elif record.lifecycle_stage in ('pending_cultivation', 'cultivation_rejected', 'cultivation_approved'):
                    stage = 'cultivation'
                else:
                    stage = 'planning'

            if stage == 'planning':
                if record.planning_state == 'approved' or (record.planning_state == 'rejected' and rejected_stage == 'wah'):
                    record.with_context(bypass_write=True).write({
                        'planning_state': 'pending_wah',
                        'lifecycle_stage': 'pending_planning',
                        'state': 'pending_wah'
                    })
                else:
                    record.with_context(bypass_write=True).write({
                        'planning_state': 'draft',
                        'lifecycle_stage': 'draft',
                        'state': 'draft'
                    })

            elif stage == 'cultivation':
                if record.cultivation_state == 'approved' or (record.cultivation_state == 'rejected' and rejected_stage == 'wah'):
                    record.with_context(bypass_write=True).write({
                        'cultivation_state': 'pending_wah',
                        'lifecycle_stage': 'pending_cultivation',
                        'state': 'pending_wah'
                    })
                else:
                    record.with_context(bypass_write=True).write({
                        'cultivation_state': 'draft',
                        'lifecycle_stage': 'planning_approved',
                        'state': 'draft'
                    })

            elif stage == 'sowing':
                if record.sowing_state == 'approved' or (record.sowing_state == 'rejected' and rejected_stage == 'wah'):
                    record.with_context(bypass_write=True).write({
                        'sowing_state': 'pending_wah',
                        'lifecycle_stage': 'pending_sowing',
                        'state': 'pending_wah'
                    })
                else:
                    record.with_context(bypass_write=True).write({
                        'sowing_state': 'draft',
                        'lifecycle_stage': 'cultivation_approved',
                        'state': 'draft'
                    })

            elif stage == 'harvesting':
                if record.harvesting_state == 'approved' or (record.harvesting_state == 'rejected' and rejected_stage == 'wah'):
                    record.with_context(bypass_write=True).write({
                        'harvesting_state': 'pending_wah',
                        'lifecycle_stage': 'pending_harvesting',
                        'state': 'pending_wah'
                    })
                else:
                    record.with_context(bypass_write=True).write({
                        'harvesting_state': 'draft',
                        'lifecycle_stage': 'sowing_approved',
                        'state': 'draft'
                    })

    def action_reject(self):
        return {
            "name": "Enter Rejection Reason",
            "type": "ir.actions.act_window",
            "res_model": "g2p.crop.reject.wizard",
            "view_mode": "form",
            "target": "new",
        }

    land_info_id = fields.Many2one('g2p.land.information', string="Land ID")
    crop_name_id = fields.Many2one('g2p.crop', string="Crop Name", compute="_compute_primary_crop_details", store=True)
    crop_category_id = fields.Many2one('g2p.crop.category', string="Crop Category", compute="_compute_primary_crop_details",
                                       store=True, readonly=True)
    crop_variety_id = fields.Many2one("g2p.crop.variety", string="Crop Variety", compute="_compute_primary_crop_details", store=True)



    @api.constrains('surveyor_mobile_number', 'supervisor_mobile_number')
    def _check_mobile_numbers(self):
        for rec in self:
            for field in ['surveyor_mobile_number', 'supervisor_mobile_number']:
                number = rec[field]
                if number:
                    if not re.match(r'^(\+251[79]\d{8}|0[79]\d{8})$', number):
                        raise ValidationError("Please enter a valid mobile number")


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('g2p.crop.registry') or 'New'


            # Prevent duplicates by ignoring create commands from harvest_detail_ids
            # since they are already created via production_detail_ids
            if 'harvest_detail_ids' in vals:
                filtered_harvest = []
                for cmd in vals['harvest_detail_ids']:
                    if cmd[0] == 0:
                        continue
                    filtered_harvest.append(cmd)
                vals['harvest_detail_ids'] = filtered_harvest

        records = super(G2PCrop, self).create(vals_list)
        for record in records:
            record._sync_crop_information()
            record._sync_production_cached_values()
        return records

    def action_add_another(self):
        self.ensure_one()
        # Create a new record with the same farmer and land info but empty crop/season details
        new_record = self.copy(default={
            'crop_name_id': False,
            'crop_variety_id': False,


            'production_detail_ids': [(5, 0, 0)],

        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Crop Sown Registry',
            'res_model': 'g2p.crop.registry',
            'view_mode': 'form',
            'res_id': new_record.id,
            'target': 'current',
        }

    def write(self, vals):
        if self.env.context.get('bypass_write'):
            return super(G2PCrop, self).write(vals)

        user = self.env.user
        is_sms = user.has_group('g2p_crop_registry.group_woreda_sms') or user.has_group('g2p_crop_registry.group_development_agent')
        is_wah = user.has_group('g2p_crop_registry.group_woreda_agri_office_head')
        is_admin = self.env.is_superuser()

        if is_sms and not is_wah and not is_admin:
            allowed_records = self.env['g2p.crop.registry']
            for record in self:
                editing_planning = any(f in vals for f in ['annual_line_ids'])
                editing_cultivation = any(f in vals for f in ['actual_annual_line_ids'])
                editing_sowing = any(f in vals for f in ['production_detail_ids'])
                editing_harvesting = any(f in vals for f in ['harvest_detail_ids'])

                is_planning_locked = record.planning_state in ['approved', 'update_requested'] and (editing_planning or record.lifecycle_stage in ['draft', 'pending_planning'])
                is_cultivation_locked = record.cultivation_state in ['approved', 'update_requested'] and (editing_cultivation or record.lifecycle_stage in ['planning_approved', 'pending_cultivation'])
                is_sowing_locked = record.sowing_state in ['approved', 'update_requested'] and (editing_sowing or record.lifecycle_stage in ['cultivation_approved', 'pending_sowing'])
                is_harvesting_locked = record.harvesting_state in ['approved', 'update_requested'] and (editing_harvesting or record.lifecycle_stage in ['sowing_approved', 'pending_harvesting'])

                if is_planning_locked or is_cultivation_locked or is_sowing_locked or is_harvesting_locked or record.state in ['approved', 'update_requested']:
                    sanitized_vals = {}
                    for k, v in vals.items():
                        if isinstance(v, models.BaseModel):
                            sanitized_vals[k] = v.id
                        else:
                            sanitized_vals[k] = v
                    self.env['g2p.crop.change.request'].create({
                        'crop_registry_id': record.id,
                        'new_values': sanitized_vals,
                        'state': 'pending',
                        'requested_by': user.id
                    })
                    update_vals = {'state': 'update_requested'}
                    if is_planning_locked or record.lifecycle_stage in ['draft', 'pending_planning']:
                        update_vals['planning_state'] = 'update_requested'
                    if is_cultivation_locked or record.lifecycle_stage in ['planning_approved', 'pending_cultivation']:
                        update_vals['cultivation_state'] = 'update_requested'
                    if is_sowing_locked or record.lifecycle_stage in ['cultivation_approved', 'pending_sowing']:
                        update_vals['sowing_state'] = 'update_requested'
                    if is_harvesting_locked or record.lifecycle_stage in ['sowing_approved', 'pending_harvesting']:
                        update_vals['harvesting_state'] = 'update_requested'
                    record.with_context(bypass_write=True).write(update_vals)
                else:
                    allowed_records |= record

            if not allowed_records:
                return True
            self = allowed_records

        sync_direction = None
        if 'actual_annual_line_ids' in vals:
            sync_direction = 'actual_to_prod'
        elif 'production_detail_ids' in vals or 'harvest_detail_ids' in vals:
            sync_direction = 'prod_to_actual'

        # Prevent duplicates by ignoring create commands from harvest_detail_ids
        if 'harvest_detail_ids' in vals:
            filtered_harvest = []
            for cmd in vals['harvest_detail_ids']:
                if cmd[0] == 0:
                    continue
                filtered_harvest.append(cmd)
            vals['harvest_detail_ids'] = filtered_harvest

        res = super(G2PCrop, self).write(vals)
        self._sync_crop_information()
        # Sync cached values into production records so computed fields work
        self._sync_production_cached_values(sync_direction=sync_direction)
        return res

    def _sync_production_cached_values(self, sync_direction=None):
        """Populate cached fields on g2p.crop.production records from planning
        and cultivation lines. This must run after save (not just onchange) so
        that stored computed fields (yield_performance_pct, land_utilization_rate,
        seed_productivity) have the data they need to compute."""
        for rec in self:
            # Sync cluster info for Cultivation lines
            for actual_line in rec.actual_annual_line_ids:
                if actual_line.sync_id:
                    planned_lines = rec.annual_line_ids.filtered(lambda l: l.sync_id == actual_line.sync_id)
                    if planned_lines:
                        planned = planned_lines[0]
                        if actual_line.has_cluster_farming != planned.has_cluster_farming:
                            actual_line.has_cluster_farming = planned.has_cluster_farming
                        if set(planned.cluster_info_ids.ids) != set(actual_line.cluster_info_ids.ids):
                            actual_line.cluster_info_ids = [(6, 0, planned.cluster_info_ids.ids)]

            for prod in rec.production_detail_ids:
                if not prod.sync_id:
                    continue

                # --- Look up planning line by sync_id ---
                planned_annual = rec.annual_line_ids.filtered(lambda l: l.sync_id == prod.sync_id)
                planned = planned_annual[0] if planned_annual else None

                expected_yield = planned.crop_expected if planned else 0.0
                planned_area = planned.crop_planned_area if planned else 0.0

                # --- Look up cultivation (actual) line by sync_id ---
                actual_annual = rec.actual_annual_line_ids.filtered(lambda l: l.sync_id == prod.sync_id)
                actual = actual_annual[0] if actual_annual else None

                seed_qty = actual.actual_seed_qty if actual else 0.0
                fert_qty = actual.actual_fertilizer_qty if actual else 0.0
                fert_type = actual.actual_fertilizer_type if actual else False
                actual_crop_area = actual.actual_crop_area if actual else 0.0
                actual_yield_val = actual.actual_yield if actual else 0.0
                seed_class = actual.actual_seed_class if actual and hasattr(actual, 'actual_seed_class') else False
                cultivated_by_val = actual.cultivated_by if actual and hasattr(actual, 'cultivated_by') else False

                # Write cached values directly to the DB record
                update_vals = {}
                if prod.expected_yield != expected_yield:
                    update_vals['expected_yield'] = expected_yield
                if prod.planned_area != planned_area:
                    update_vals['planned_area'] = planned_area
                if prod.actual_crop_area != actual_crop_area:
                    update_vals['actual_crop_area'] = actual_crop_area
                if prod.actual_seed_qty != seed_qty:
                    update_vals['actual_seed_qty'] = seed_qty
                if prod.actual_fertilizer_qty != fert_qty:
                    update_vals['actual_fertilizer_qty'] = fert_qty
                if fert_type and prod.actual_fertilizer_type != fert_type:
                    update_vals['actual_fertilizer_type'] = fert_type
                if prod.actual_seed_class != seed_class:
                    update_vals['actual_seed_class'] = seed_class
                if prod.cultivated_by != cultivated_by_val:
                    update_vals['cultivated_by'] = cultivated_by_val
                # Cache actual_yield from cultivation → used in yield_performance_pct formula
                if prod.actual_yield_cached != actual_yield_val:
                    update_vals['actual_yield_cached'] = actual_yield_val

                if actual:
                    season_val = actual.season_id.id if actual.season_id else False
                    crop_val = actual.crop_name_id.id if actual.crop_name_id else False
                    land_val = actual.land_info_id.id if actual.land_info_id else False
                    sowing_date = actual.collected_gc

                    if prod.season_id.id != season_val:
                        update_vals['season_id'] = season_val
                    if prod.crop_name_id.id != crop_val:
                        update_vals['crop_name_id'] = crop_val
                    if prod.land_info_id.id != land_val:
                        update_vals['land_info_id'] = land_val
                    if prod.actual_sowing_date != sowing_date:
                        update_vals['actual_sowing_date'] = sowing_date

                # NOTE: actual_yield is always set from crop_expected (planning → cultivation sync).
                # Do NOT overwrite it from qty_harvested here.

                if update_vals:
                    prod.write(update_vals)

                # Sync cluster lines
                existing_cluster_ids = prod.production_cluster_line_ids.mapped('cluster_info_id.id')
                for cinfo in prod.cluster_info_ids:
                    if cinfo.id not in existing_cluster_ids:
                        prod.write({
                            'production_cluster_line_ids': [(0, 0, {
                                'cluster_info_id': cinfo.id,
                            })]
                        })
                # Remove obsolete cluster lines
                obsolete_lines = prod.production_cluster_line_ids.filtered(lambda l: l.cluster_info_id.id not in prod.cluster_info_ids.ids)
                if obsolete_lines:
                    prod.write({
                        'production_cluster_line_ids': [(2, l.id, False) for l in obsolete_lines]
                    })

    def _sync_crop_information(self):
        for record in self:
            partner = record.partner_id

            if not partner:
                continue

            # Sync water resources to farmer profile directly


            def _sync_water_lines(partner, source_line):
                if hasattr(source_line, 'water_resource_line_ids'):
                    new_water_sources = [w.water_resource_id.id for w in source_line.water_resource_line_ids if w.water_resource_id]
                    if new_water_sources:
                        partner.write({
                            'crop_water_sources': [(4, ws_id) for ws_id in new_water_sources]
                        })

            if record.actual_annual_line_ids:
                for s_line in record.actual_annual_line_ids:
                    if not s_line.crop_name_id:
                        continue
                    existing = self.env['g2p.crop.information'].search([
                        ('partner_id', '=', partner.id),
                        ('crop', '=', s_line.crop_name_id.id),
                        ('collected_gc', '=', s_line.collected_gc),
                    ], limit=1)

                    vals = {
                        'partner_id': partner.id,
                        'crop': s_line.crop_name_id.id,
                        'season': s_line.season_id.id if 's_line' in locals() else False,
                        'collected_gc': s_line.collected_gc,
                        'collected_ec': s_line.collected_ec,
                    }
                    if existing:
                        existing.write(vals)
                        _sync_water_lines(partner, s_line)
                    else:
                        new_info = self.env['g2p.crop.information'].create(vals)
                        _sync_water_lines(partner, s_line)

    @api.onchange('partner_id')
    def _onchange_partner_id_details(self):
        if self.partner_id:
            farmer = self.partner_id
            if farmer:
                self.farmer_display_id = farmer.name
                self.region_id = farmer.region.id if hasattr(farmer, 'region') and farmer.region else False
                self.zone_id = farmer.zone.id if hasattr(farmer, 'zone') and farmer.zone else False
                self.woreda_id = farmer.woreda.id if hasattr(farmer, 'woreda') and farmer.woreda else False
                self.kebele_id = farmer.kebele.id if hasattr(farmer, 'kebele') and farmer.kebele else False

                if hasattr(farmer, 'partner_latitude') and hasattr(farmer, 'partner_longitude'):
                    if farmer.partner_latitude and farmer.partner_longitude:
                        self.gps = f"{farmer.partner_latitude}, {farmer.partner_longitude}"

                # Fetch Fayda ID
                uid_type = self.env['g2p.id.type'].search([('name', '=', 'UID')], limit=1)
                if uid_type:
                    fayda = self.env['g2p.reg.id'].search([
                        ('partner_id', '=', farmer.id),
                        ('id_type', '=', uid_type.id)
                    ], limit=1)
                    if fayda:
                        self.fyda_id = fayda.value
                    else:
                        self.fyda_id = False
                else:
                    self.fyda_id = False

                return {'domain': {'land_info_id': [('partner_id', '=', farmer.id)]}}
            else:
                return {'domain': {'land_info_id': [('id', '=', False)]}}
        else:
            self.farmer_display_id = False
            self.fyda_id = False
            self.region_id = False
            self.zone_id = False
            self.woreda_id = False
            self.kebele_id = False
            self.gps = False
            return {'domain': {'land_info_id': [('id', '=', False)]}}

    @api.onchange('land_info_id')
    def _onchange_land_info_id(self):
        if self.land_info_id:
            self.land_area = self.land_info_id.total_land_area
            self.ownership_type = self.land_info_id.ownership_type
            if hasattr(self.land_info_id, 'soil_fertility') and self.land_info_id.soil_fertility:
                self.soil_fertility = self.land_info_id.soil_fertility.lower()
            if self.land_info_id.land_kebele:
                self.kebele_id = self.land_info_id.land_kebele.id
                if self.land_info_id.land_kebele.woreda:
                    self.woreda_id = self.land_info_id.land_kebele.woreda.id
                    if self.land_info_id.land_kebele.woreda.zone:
                        self.zone_id = self.land_info_id.land_kebele.woreda.zone.id
                        if self.land_info_id.land_kebele.woreda.zone.region:
                            self.region_id = self.land_info_id.land_kebele.woreda.zone.region.id
                        else:
                            self.region_id = False
                    else:
                        self.zone_id = False
                        self.region_id = False
                else:
                    self.woreda_id = False
                    self.zone_id = False
                    self.region_id = False
            else:
                self.kebele_id = False
                self.woreda_id = False
                self.zone_id = False
                self.region_id = False

            if hasattr(self.land_info_id, 'polygon_data') and self.land_info_id.polygon_data:
                self.gps = self.land_info_id.polygon_data
            else:
                self.gps = False
    @api.onchange('crop_name_id')
    def _onchange_crop_id(self):
        self.crop_variety_id = False
        return {'domain': {'crop_variety_id': [('crop_id', '=', self.crop_name_id.id)]}}

    primary_land_id = fields.Many2one('g2p.land.information', compute='_compute_primary_crop_details', store=True, string="Land ID")
    primary_season_id = fields.Many2one('g2p.season', compute='_compute_primary_crop_details', store=True, string="Season")
    primary_plot_category = fields.Selection([('annual', 'Annual Crop'), ('perennial', 'Perennial Crop'), ('biennial', 'Biennial Crop')], compute='_compute_primary_crop_details', store=True, string="Plot Category")

    @api.depends('annual_line_ids.crop_name_id', 'annual_line_ids.crop_variety_id', 'annual_line_ids.land_info_id', 'annual_line_ids.season_id', 'annual_line_ids.land_category')
    def _compute_primary_crop_details(self):
        for rec in self:
            first_line = False
            if rec.annual_line_ids:
                first_line = rec.annual_line_ids[0]

            rec.crop_name_id = first_line.crop_name_id.id if first_line and first_line.crop_name_id else False
            rec.crop_category_id = first_line.crop_name_id.category_id.id if first_line and first_line.crop_name_id and first_line.crop_name_id.category_id else False
            rec.crop_variety_id = first_line.crop_variety_id.id if first_line and first_line.crop_variety_id else False
            rec.primary_land_id = first_line.land_info_id.id if first_line and first_line.land_info_id else False
            rec.primary_season_id = first_line.season_id.id if first_line and first_line.season_id else False
            rec.primary_plot_category = first_line.land_category if first_line and first_line.land_category else False

    @api.depends('crop_name_id', 'collected_gc', 'crop_variety_id')
    @api.constrains('fyda_id')
    def _check_ids(self):
        for rec in self:

            # Fayda ID validation -> FAN- + 16 digits
            if rec.fyda_id:
                fyda_pattern = r'^FAN-\d{16}$'
                if not re.match(fyda_pattern, rec.fyda_id):
                    raise ValidationError(
                        "Fayda ID must be in this format: FAN-1234567890123456"
                    )

    @api.constrains('actual_annual_line_ids')
    def _check_actual_crop_area_limits(self):
        for rec in self:
            if rec.actual_crop_area_exceeded:
                raise ValidationError(rec.actual_crop_area_warning)

    @api.onchange('annual_line_ids')
    def _onchange_sync_annual_lines(self):
        for rec in self:
            for planned_line in rec.annual_line_ids:
                if not planned_line.land_info_id and not planned_line.temporary_land_id and not planned_line.season_id and not planned_line.crop_name_id:
                    continue

                if not planned_line.sync_id:
                    planned_line.sync_id = str(uuid.uuid4())

                # Sync Actual Lines
                existing_actual = rec.actual_annual_line_ids.filtered(
                    lambda l: l.sync_id == planned_line.sync_id or (not l.sync_id and l.season_id == planned_line.season_id and l.crop_name_id == planned_line.crop_name_id)
                )
                if not existing_actual:
                    new_line = self.env['g2p.annual.actual.line'].new({
                        'sync_id': planned_line.sync_id,
                        'is_manual': False,
                        'is_planning': True,
                        'season_id': planned_line.season_id.id if planned_line.season_id else False,
                        'land_category': planned_line.land_category if planned_line.land_category else False,
                        'ownership_type': planned_line.ownership_type if planned_line.ownership_type else False,
                        'land_area': planned_line.land_area,
                        'soil_fertility': planned_line.soil_fertility,
                        'start_gc': planned_line.start_gc,
                        'end_gc': planned_line.end_gc,
                        'region_name_id': planned_line.region_name_id.id if planned_line.region_name_id else False,
                        'zone_name_id': planned_line.zone_name_id.id if planned_line.zone_name_id else False,
                        'woreda_name_id': planned_line.woreda_name_id.id if planned_line.woreda_name_id else False,
                        'kebele_id': planned_line.kebele_id.id if planned_line.kebele_id else False,
                        'land_info_id': planned_line.land_info_id.id if planned_line.land_info_id else False,
                        'gps': planned_line.gps,
                        'crop_name_id': planned_line.crop_name_id.id if planned_line.crop_name_id else False,
                        'crop_category_id': planned_line.crop_category_id.id if planned_line.crop_category_id else False,
                        'crop_variety_id': planned_line.crop_variety_id.id if planned_line.crop_variety_id else False,
                        'local_name': planned_line.local_name,
                        'scientific_name': planned_line.scientific_name,
                        'actual_crop_area': planned_line.crop_planned_area,
                        'actual_growth_duration': planned_line.crop_growth_duration,
                        'has_cluster_farming': planned_line.has_cluster_farming if planned_line.has_cluster_farming else False,
                        'actual_yield': planned_line.crop_expected if planned_line.crop_expected else 0.0,
                        'collected_gc': planned_line.collected_gc if planned_line.collected_gc else False,
                        'collected_ec': planned_line.collected_ec if planned_line.collected_ec else False,
                        'actual_seed_class': planned_line.seed_planned if planned_line.seed_planned else False,
                        'actual_seed_source': planned_line.seed_source if planned_line.seed_source else False,
                        'actual_seed_qty': planned_line.seed_planned_qty if planned_line.seed_planned_qty else 0.0,
                        'water_resource_line_ids': [(0, 0, {
                            'water_resource_id': w.water_resource_id.id,
                            'method_id': w.method_id,
                            'frequency': w.frequency,
                        }) for w in planned_line.water_resource_line_ids],
                        'actual_fertilizer_qty': planned_line.seed_planned_fertilizer_qty if planned_line.seed_planned_fertilizer_qty else 0.0,
                        'actual_fertilizer_type': planned_line.seed_planned_fertilizer_type if planned_line.seed_planned_fertilizer_type else False,
                        'cropping_system': planned_line.cropping_system if planned_line.cropping_system else False,
                        'cluster_info_ids': [(6, 0, planned_line.cluster_info_ids.ids)],
                    })
                    rec.actual_annual_line_ids += new_line
    def _sync_planned_to_actual_backend(self):
        for rec in self:
            # 1. Sync Annual Lines
            for planned_line in rec.annual_line_ids:
                if not planned_line.land_info_id and not planned_line.temporary_land_id and not planned_line.season_id and not planned_line.crop_name_id:
                    continue

                if not planned_line.sync_id:
                    planned_line.sync_id = str(uuid.uuid4())

                existing_actual = rec.actual_annual_line_ids.filtered(
                    lambda l: l.sync_id == planned_line.sync_id or (not l.sync_id and l.season_id == planned_line.season_id and l.crop_name_id == planned_line.crop_name_id)
                )
                if not existing_actual:
                    self.env['g2p.annual.actual.line'].create({
                        'crop_registry_id': rec.id,
                        'sync_id': planned_line.sync_id,
                        'is_manual': False,
                        'is_planning': True,
                        'season_id': planned_line.season_id.id if planned_line.season_id else False,
                        'land_category': planned_line.land_category if planned_line.land_category else False,
                        'ownership_type': planned_line.ownership_type if planned_line.ownership_type else False,
                        'land_area': planned_line.land_area,
                        'soil_fertility': planned_line.soil_fertility,
                        'start_gc': planned_line.start_gc,
                        'end_gc': planned_line.end_gc,
                        'region_name_id': planned_line.region_name_id.id if planned_line.region_name_id else False,
                        'zone_name_id': planned_line.zone_name_id.id if planned_line.zone_name_id else False,
                        'woreda_name_id': planned_line.woreda_name_id.id if planned_line.woreda_name_id else False,
                        'kebele_id': planned_line.kebele_id.id if planned_line.kebele_id else False,
                        'land_info_id': planned_line.land_info_id.id if planned_line.land_info_id else False,
                        'gps': planned_line.gps,
                        'crop_name_id': planned_line.crop_name_id.id if planned_line.crop_name_id else False,
                        'crop_category_id': planned_line.crop_category_id.id if planned_line.crop_category_id else False,
                        'crop_variety_id': planned_line.crop_variety_id.id if planned_line.crop_variety_id else False,
                        'local_name': planned_line.local_name,
                        'scientific_name': planned_line.scientific_name,
                        'actual_crop_area': planned_line.crop_planned_area,
                        'actual_growth_duration': planned_line.crop_growth_duration,
                        'has_cluster_farming': planned_line.has_cluster_farming if planned_line.has_cluster_farming else False,
                        'actual_yield': planned_line.crop_expected if planned_line.crop_expected else 0.0,
                        'collected_gc': planned_line.collected_gc if planned_line.collected_gc else False,
                        'collected_ec': planned_line.collected_ec if planned_line.collected_ec else False,
                        'actual_seed_class': planned_line.seed_planned if planned_line.seed_planned else False,
                        'actual_seed_source': planned_line.seed_source if planned_line.seed_source else False,
                        'actual_seed_qty': planned_line.seed_planned_qty if planned_line.seed_planned_qty else 0.0,
                        'actual_fertilizer_qty': planned_line.seed_planned_fertilizer_qty if planned_line.seed_planned_fertilizer_qty else 0.0,
                        'actual_fertilizer_type': planned_line.seed_planned_fertilizer_type if planned_line.seed_planned_fertilizer_type else False,
                        'cropping_system': planned_line.cropping_system if planned_line.cropping_system else False,
                        'water_resource_line_ids': [(0, 0, {
                            'water_resource_id': w.water_resource_id.id,
                            'method_id': w.method_id,
                            'frequency': w.frequency,
                        }) for w in planned_line.water_resource_line_ids],
                        'cluster_info_ids': [(6, 0, planned_line.cluster_info_ids.ids)],
                    })
                else:
                    for actual in existing_actual:
                        if actual.is_manual:
                            actual.is_manual = False
                            actual.is_planning = True
                        if not actual.sync_id:
                            actual.sync_id = planned_line.sync_id
                        if planned_line.crop_name_id and actual.crop_name_id != planned_line.crop_name_id:
                            actual.crop_name_id = planned_line.crop_name_id.id
                        if actual.crop_variety_id != planned_line.crop_variety_id:
                            actual.crop_variety_id = planned_line.crop_variety_id.id if planned_line.crop_variety_id else False
                        if planned_line.season_id and actual.season_id != planned_line.season_id:
                            actual.season_id = planned_line.season_id.id
                        if planned_line.land_info_id and actual.land_info_id != planned_line.land_info_id:
                            actual.land_info_id = planned_line.land_info_id.id
                        if planned_line.region_name_id and actual.region_name_id != planned_line.region_name_id:
                            actual.region_name_id = planned_line.region_name_id.id
                        if planned_line.zone_name_id and actual.zone_name_id != planned_line.zone_name_id:
                            actual.zone_name_id = planned_line.zone_name_id.id
                        if planned_line.woreda_name_id and actual.woreda_name_id != planned_line.woreda_name_id:
                            actual.woreda_name_id = planned_line.woreda_name_id.id
                        if planned_line.kebele_id and actual.kebele_id != planned_line.kebele_id:
                            actual.kebele_id = planned_line.kebele_id.id
                        if planned_line.gps and actual.gps != planned_line.gps:
                            actual.gps = planned_line.gps
                        if planned_line.ownership_type and actual.ownership_type != planned_line.ownership_type:
                            actual.ownership_type = planned_line.ownership_type
                        if planned_line.land_area and actual.land_area != planned_line.land_area:
                            actual.land_area = planned_line.land_area
                        if planned_line.soil_fertility and actual.soil_fertility != planned_line.soil_fertility:
                            actual.soil_fertility = planned_line.soil_fertility
                        if planned_line.land_category and actual.land_category != planned_line.land_category:
                            actual.land_category = planned_line.land_category
                        if planned_line.start_gc and actual.start_gc != planned_line.start_gc:
                            actual.start_gc = planned_line.start_gc
                        if planned_line.end_gc and actual.end_gc != planned_line.end_gc:
                            actual.end_gc = planned_line.end_gc
                        if planned_line.local_name != actual.local_name:
                            actual.local_name = planned_line.local_name
                        if planned_line.scientific_name != actual.scientific_name:
                            actual.scientific_name = planned_line.scientific_name
                        if planned_line.crop_planned_area and actual.actual_crop_area != planned_line.crop_planned_area:
                            actual.actual_crop_area = planned_line.crop_planned_area
                        if planned_line.crop_growth_duration and actual.actual_growth_duration != planned_line.crop_growth_duration:
                            actual.actual_growth_duration = planned_line.crop_growth_duration
                        if planned_line.seed_planned and actual.actual_seed_class != planned_line.seed_planned:
                            actual.actual_seed_class = planned_line.seed_planned
                        if actual.actual_seed_source != planned_line.seed_source:
                            actual.actual_seed_source = planned_line.seed_source
                        if planned_line.seed_planned_qty and actual.actual_seed_qty != planned_line.seed_planned_qty:
                            actual.actual_seed_qty = planned_line.seed_planned_qty
                        if planned_line.collected_gc and actual.collected_gc != planned_line.collected_gc:
                            actual.collected_gc = planned_line.collected_gc
                        if planned_line.collected_ec and actual.collected_ec != planned_line.collected_ec:
                            actual.collected_ec = planned_line.collected_ec
                        if planned_line.seed_planned_fertilizer_type and actual.actual_fertilizer_type != planned_line.seed_planned_fertilizer_type:
                            actual.actual_fertilizer_type = planned_line.seed_planned_fertilizer_type
                        if planned_line.seed_planned_fertilizer_qty and actual.actual_fertilizer_qty != planned_line.seed_planned_fertilizer_qty:
                            actual.actual_fertilizer_qty = planned_line.seed_planned_fertilizer_qty
                        if planned_line.has_cluster_farming != actual.has_cluster_farming:
                            actual.has_cluster_farming = planned_line.has_cluster_farming
                        if set(planned_line.cluster_info_ids.ids) != set(actual.cluster_info_ids.ids):
                            actual.cluster_info_ids = [(6, 0, planned_line.cluster_info_ids.ids)]
                            for cinfo in planned_line.cluster_info_ids:
                                if not cinfo.actual_cluster_plan:
                                    cinfo.actual_cluster_plan = cinfo.cluster_plan
                                if not cinfo.actual_cluster_collected_land:
                                    cinfo.actual_cluster_collected_land = cinfo.cluster_collected_land
                                if not cinfo.actual_cluster_collected_quintal:
                                    cinfo.actual_cluster_collected_quintal = cinfo.cluster_collected_quintal
                                if not cinfo.actual_cluster_participant_farmers:
                                    cinfo.actual_cluster_participant_farmers = cinfo.cluster_participant_farmers
                                if not cinfo.actual_collected_land:
                                    cinfo.actual_collected_land = cinfo.collected_land
                                if not cinfo.actual_collected_land_quintal:
                                    cinfo.actual_collected_land_quintal = cinfo.collected_land_quintal
                                if not cinfo.actual_collected_by_combiner:
                                    cinfo.actual_collected_by_combiner = cinfo.collected_by_combiner

                        actual.actual_yield = planned_line.crop_expected

                        if actual.cropping_system != planned_line.cropping_system:
                            actual.cropping_system = planned_line.cropping_system

                        planned_waters = {(w.water_resource_id.id, w.method_id, w.frequency) for w in planned_line.water_resource_line_ids}
                        actual_waters = {(w.water_resource_id.id, w.method_id, w.frequency) for w in actual.water_resource_line_ids}
                        if planned_waters != actual_waters:
                            actual.water_resource_line_ids = [(5, 0, 0)] + [(0, 0, {
                                'water_resource_id': w.water_resource_id.id,
                                'method_id': w.method_id,
                                'frequency': w.frequency,
                            }) for w in planned_line.water_resource_line_ids]

                # Sync Production Details
                existing_production = rec.production_detail_ids.filtered(
                    lambda p: p.sync_id == planned_line.sync_id or (not p.sync_id and p.season_id == planned_line.season_id and p.crop_name_id == planned_line.crop_name_id)
                )
                if not existing_production:
                    new_prod = self.env['g2p.crop.production'].create({
                        'crop_registry_id': rec.id,
                        'sync_id': planned_line.sync_id,
                        'season_id': planned_line.season_id.id if planned_line.season_id else False,
                        'land_info_id': planned_line.land_info_id.id if planned_line.land_info_id else False,
                        'crop_name_id': planned_line.crop_name_id.id if planned_line.crop_name_id else False,
                        'expected_yield': planned_line.crop_expected,
                    })
                else:
                    for prod in existing_production:
                        if not prod.sync_id:
                            prod.sync_id = planned_line.sync_id
                        if planned_line.crop_name_id and prod.crop_name_id != planned_line.crop_name_id:
                            prod.crop_name_id = planned_line.crop_name_id.id
                        if planned_line.season_id and prod.season_id != planned_line.season_id:
                            prod.season_id = planned_line.season_id.id
                        if planned_line.land_info_id and prod.land_info_id != planned_line.land_info_id:
                            prod.land_info_id = planned_line.land_info_id.id
                        if prod.expected_yield != planned_line.crop_expected:
                            prod.expected_yield = planned_line.crop_expected

            # Cleanup orphaned actual lines
            planned_annual_sync_ids = [l.sync_id for l in rec.annual_line_ids if l.sync_id]
            valid_sync_ids = planned_annual_sync_ids + \
                             [l.sync_id for l in rec.actual_annual_line_ids if l.sync_id and l.is_manual]

            orphaned_annual_actual = rec.actual_annual_line_ids.filtered(lambda l: l.sync_id and not l.is_manual and l.sync_id not in planned_annual_sync_ids)
            if orphaned_annual_actual:
                rec.actual_annual_line_ids -= orphaned_annual_actual

            orphaned_prod = rec.production_detail_ids.filtered(lambda p: p.sync_id and p.sync_id not in valid_sync_ids)
            if orphaned_prod:
                rec.production_detail_ids -= orphaned_prod

            rec.harvest_detail_ids = rec.production_detail_ids

    @api.onchange('actual_annual_line_ids')
    def _onchange_sync_actual_to_production_annual(self):
        for rec in self:
            for actual_line in rec.actual_annual_line_ids:
                if not actual_line.sync_id:
                    actual_line.sync_id = str(uuid.uuid4())
                prod_line = rec.production_detail_ids.filtered(lambda p: p.sync_id == actual_line.sync_id)
                planned_line = rec.annual_line_ids.filtered(lambda l: l.sync_id == actual_line.sync_id)
                expected_yield = planned_line[0].crop_expected if planned_line else 0.0
                planned_area = planned_line[0].crop_planned_area if planned_line else 0.0

                if prod_line:
                    # Assuming 1-to-1 mapping
                    prod_line = prod_line[0]

                    if prod_line.season_id != actual_line.season_id:
                        prod_line.season_id = actual_line.season_id
                    if prod_line.crop_name_id != actual_line.crop_name_id:
                        prod_line.crop_name_id = actual_line.crop_name_id
                    if prod_line.land_info_id != actual_line.land_info_id:
                        prod_line.land_info_id = actual_line.land_info_id.id
                    if prod_line.actual_sowing_date != actual_line.collected_gc:
                        prod_line.actual_sowing_date = actual_line.collected_gc
                    if prod_line.actual_fertilizer_type != actual_line.actual_fertilizer_type:
                        prod_line.actual_fertilizer_type = actual_line.actual_fertilizer_type
                    if prod_line.actual_fertilizer_qty != actual_line.actual_fertilizer_qty:
                        prod_line.actual_fertilizer_qty = actual_line.actual_fertilizer_qty
                    if prod_line.actual_seed_qty != actual_line.actual_seed_qty:
                        prod_line.actual_seed_qty = actual_line.actual_seed_qty
                    if prod_line.actual_crop_area != actual_line.actual_crop_area:
                        prod_line.actual_crop_area = actual_line.actual_crop_area
                    if prod_line.expected_yield != expected_yield:
                        prod_line.expected_yield = expected_yield
                    if prod_line.planned_area != planned_area:
                        prod_line.planned_area = planned_area
                else:
                    new_prod = self.env['g2p.crop.production'].new({
                        'sync_id': actual_line.sync_id,
                        'season_id': actual_line.season_id.id if actual_line.season_id else False,
                        'land_info_id': actual_line.land_info_id.id if actual_line.land_info_id else False,
                        'crop_name_id': actual_line.crop_name_id.id if actual_line.crop_name_id else False,
                        'actual_sowing_date': actual_line.collected_gc if actual_line.collected_gc else False,
                        'actual_fertilizer_qty': actual_line.actual_fertilizer_qty if actual_line.actual_fertilizer_qty else 0.0,
                        'actual_fertilizer_type': actual_line.actual_fertilizer_type if actual_line.actual_fertilizer_type else False,
                        'actual_seed_qty': actual_line.actual_seed_qty if actual_line.actual_seed_qty else 0.0,
                        'actual_crop_area': actual_line.actual_crop_area if actual_line.actual_crop_area else 0.0,
                        'expected_yield': expected_yield,
                        'planned_area': planned_area,
                        'qty_harvested': actual_line.actual_yield if actual_line.actual_yield else 0.0,

                    })
                    rec.production_detail_ids += new_prod
            # Cleanup orphaned production details when actual is deleted
            valid_sync_ids = [l.sync_id for l in rec.annual_line_ids if l.sync_id] + [l.sync_id for l in rec.actual_annual_line_ids if l.sync_id and l.is_manual]
            orphaned_prod = rec.production_detail_ids.filtered(lambda p: p.sync_id and p.sync_id not in valid_sync_ids)
            if orphaned_prod:
                rec.production_detail_ids -= orphaned_prod
        rec.harvest_detail_ids = rec.production_detail_ids

    @api.onchange('production_detail_ids', 'harvest_detail_ids')
    def _onchange_sync_production_to_actual(self):
        for rec in self:
            for prod_line in rec.production_detail_ids:
                if not prod_line.sync_id:
                    continue
                actual_annual = rec.actual_annual_line_ids.filtered(lambda l: l.sync_id == prod_line.sync_id)

            valid_sync_ids = [l.sync_id for l in rec.annual_line_ids if l.sync_id] + [l.sync_id for l in rec.actual_annual_line_ids if l.sync_id and l.is_manual]
            orphaned_prod = rec.production_detail_ids.filtered(lambda p: p.sync_id and p.sync_id not in valid_sync_ids)
            if orphaned_prod:
                rec.production_detail_ids -= orphaned_prod
        rec.harvest_detail_ids = rec.production_detail_ids

class G2PCropInformationInherit(models.Model):
    _inherit = 'g2p.crop.information'

    water_resource_line_ids = fields.One2many('g2p.water.resource.line', 'crop_information_id', string="Water Resources")


class ResPartnerCropRegistryInherit(models.Model):
    _inherit = 'res.partner'

    @api.depends_context('show_farmer_id')
    def _compute_display_name(self):
        super()._compute_display_name()
        if self.env.context.get('show_farmer_id'):
            for record in self:
                if record.is_farmer == 'yes' and record.farmer_id:
                    record.display_name = record.farmer_id

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if self.env.context.get('show_farmer_id'):
            args = args or []
            domain = ['|', ('farmer_id', operator, name), ('name', operator, name)] + args
            return self.search(domain, limit=limit).name_get()
        return super().name_search(name, args=args, operator=operator, limit=limit)

class G2PLandInformationInherit(models.Model):
    _inherit = 'g2p.land.information'

    @api.depends_context('show_land_id')
    def _compute_display_name(self):
        super()._compute_display_name()
        if self.env.context.get('show_land_id'):
            for record in self:
                if record.land_id:
                    record.display_name = record.land_id
                else:
                    record.display_name = f"Unnamed Plot ({record.partner_id.name or 'Unknown'})"

    def name_get(self):
        if self.env.context.get('show_land_id'):
            result = []
            for record in self:
                if record.land_id:
                    result.append((record.id, record.land_id))
                else:
                    result.append((record.id, f"Unnamed Plot ({record.partner_id.name or 'Unknown'})"))
            return result
        return super().name_get()

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if self.env.context.get('show_land_id'):
            args = args or []
            domain = ['|', ('land_id', operator, name), ('partner_id.name', operator, name)] + args
            return self.search(domain, limit=limit).name_get()
        return super().name_search(name, args=args, operator=operator, limit=limit)
