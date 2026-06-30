from odoo import api, fields, models
import re
from odoo.exceptions import ValidationError
from datetime import date
from odoo.addons.g2p_ati.models.utils import eth_date
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
    biennial_line_ids = fields.One2many(
        "g2p.biennial.line",
        "crop_registry_id",
        string="Biennial Crops",
    )
    perennial_line_ids = fields.One2many(
        "g2p.perennial.line",
        "crop_registry_id",
        string="Perennial Crops",
    )

    has_no_planning_data = fields.Boolean(
        string="Has No Planning Data",
        compute="_compute_has_no_planning_data"
    )

    @api.depends('annual_line_ids', 'perennial_line_ids', 'biennial_line_ids')
    def _compute_has_no_planning_data(self):
        for rec in self:
            rec.has_no_planning_data = not (rec.annual_line_ids or rec.perennial_line_ids or rec.biennial_line_ids)

    # =======================================
    # UI Fields: Cultivation / Land Preparation
    # =======================================
    actual_annual_line_ids = fields.One2many(
        "g2p.annual.actual.line",
        "crop_registry_id",
        string="Actual Input",
    )
    actual_biennial_line_ids = fields.One2many(
        "g2p.biennial.actual.line",
        "crop_registry_id",
        string="Biennial Crops (Actual)",
    )
    actual_perennial_line_ids = fields.One2many(
        "g2p.perennial.actual.line",
        "crop_registry_id",
        string="Perennial Crops (Actual)",
    )

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
        string="Harvest Details",
    )

    # =======================================
    # UI Fields: Survey Personnel
    # =======================================
    surveyor_name = fields.Char(string="Surveyor Name")
    surveyor_mobile_number = fields.Char(string="Surveyor Mobile Number")
    supervisor_name = fields.Char(string="Supervisor Name")
    supervisor_mobile_number = fields.Char(string="Supervisor Mobile Number")
    first_approvel_status = fields.Selection([
        ('draft', 'Draft'),
    ], string="First approvel status")

    land_info_id = fields.Many2one('g2p.land.information', string="Land ID")
    # owner_name = fields.Char(string="Owner Name")
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

    @api.constrains('annual_line_ids')
    def _check_planned_crop_area(self):
        pass # land_area has been moved from the parent record to the lines

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('g2p.crop.registry') or 'New'
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
            'actual_perennial_line_ids': [(5, 0, 0)],
            'actual_biennial_line_ids': [(5, 0, 0)],

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
        sync_direction = None
        if any(f in vals for f in ['actual_annual_line_ids', 'actual_perennial_line_ids', 'actual_biennial_line_ids']):
            sync_direction = 'actual_to_prod'
        elif 'production_detail_ids' in vals:
            sync_direction = 'prod_to_actual'

        res = super(G2PCrop, self).write(vals)
        self._sync_crop_information()
        if 'partner_id' in vals:
            for rec in self:
                partner = rec.partner_id
                if partner:
                    pass
        # Sync cached values into production records so computed fields work
        self._sync_production_cached_values(sync_direction=sync_direction)
        return res

    def _sync_production_cached_values(self, sync_direction=None):
        """Populate cached fields on g2p.crop.production records from planning
        and cultivation lines. This must run after save (not just onchange) so
        that stored computed fields (yield_performance_pct, land_utilization_rate,
        seed_productivity) have the data they need to compute."""
        for rec in self:
            for prod in rec.production_detail_ids:
                if not prod.sync_id:
                    continue

                # --- Look up planning line (any category) by sync_id ---
                planned_annual = rec.annual_line_ids.filtered(lambda l: l.sync_id == prod.sync_id)
                planned_perennial = rec.perennial_line_ids.filtered(lambda l: l.sync_id == prod.sync_id)
                planned_biennial = rec.biennial_line_ids.filtered(lambda l: l.sync_id == prod.sync_id)
                planned_line = (planned_annual or planned_perennial or planned_biennial)
                planned = planned_line[0] if planned_line else None

                expected_yield = planned.crop_expected if planned else 0.0
                planned_area = planned.crop_planned_area if planned else 0.0

                # --- Look up cultivation (actual) line by sync_id ---
                actual_annual = rec.actual_annual_line_ids.filtered(lambda l: l.sync_id == prod.sync_id)
                actual_perennial = rec.actual_perennial_line_ids.filtered(lambda l: l.sync_id == prod.sync_id)
                actual_biennial = rec.actual_biennial_line_ids.filtered(lambda l: l.sync_id == prod.sync_id)
                actual_line = (actual_annual or actual_perennial or actual_biennial)
                actual = actual_line[0] if actual_line else None

                seed_qty = actual.actual_seed_qty if actual else 0.0
                fert_qty = actual.actual_fertilizer_qty if actual else 0.0
                fert_type = actual.actual_fertilizer_type if actual else False
                actual_crop_area = actual.actual_crop_area if actual else 0.0
                actual_yield_val = actual.actual_yield if actual else 0.0

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

                if actual and prod.qty_harvested != actual_yield_val:
                    if sync_direction == 'actual_to_prod':
                        update_vals['qty_harvested'] = actual_yield_val
                    elif sync_direction == 'prod_to_actual':
                        actual.write({'actual_yield': prod.qty_harvested})
                    else:
                        if prod.qty_harvested == 0.0:
                            update_vals['qty_harvested'] = actual_yield_val
                        elif actual_yield_val == 0.0:
                            actual.write({'actual_yield': prod.qty_harvested})
                        else:
                            actual.write({'actual_yield': prod.qty_harvested})

                if update_vals:
                    prod.write(update_vals)

    def _sync_crop_information(self):
        for record in self:
            partner = record.partner_id
            
            if not partner:
                continue
                
            # Sync water resources to farmer profile directly

            
            def _sync_water_lines(crop_info, source_line):
                crop_info.water_resource_line_ids.unlink()
                if hasattr(source_line, 'water_resource_line_ids'):
                    for w in source_line.water_resource_line_ids:
                        if w.water_resource_id:
                            self.env['g2p.water.resource.line'].create({
                                'crop_information_id': crop_info.id,
                                'water_resource_id': w.water_resource_id.id,
                                'method_id': w.method_id,
                                'frequency': w.frequency,
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
                        'season': s_line.season_id.id if 's_line' in locals() else (h_line.season_id.id if 'h_line' in locals() else False),
                    }
                    if existing:
                        existing.write(vals)
                        _sync_water_lines(existing, s_line if "s_line" in locals() else h_line)
                    else:
                        new_info = self.env['g2p.crop.information'].create(vals)
                        _sync_water_lines(new_info, s_line if "s_line" in locals() else h_line)
                    
            elif record.actual_biennial_line_ids:
                for b_line in record.actual_biennial_line_ids:
                    b_line.is_mismatch = False
            elif record.actual_perennial_line_ids:
                for h_line in record.actual_perennial_line_ids:
                    if not h_line.crop_name_id:
                        continue
                    existing = self.env['g2p.crop.information'].search([
                        ('partner_id', '=', partner.id),
                        ('crop', '=', h_line.crop_name_id.id),
                        ('collected_gc', '=', h_line.collected_gc),
                    ], limit=1)
                    
                    vals = {
                        'partner_id': partner.id,
                        'crop': h_line.crop_name_id.id,
                        'season': s_line.season_id.id if 's_line' in locals() else (h_line.season_id.id if 'h_line' in locals() else False),
                    }
                    if existing:
                        existing.write(vals)
                    else:
                        new_info = self.env['g2p.crop.information'].create(vals)

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

    # @api.onchange('crop_name_id')
    # def _onchange_crop_name_id(self):
    #     for rec in self:
    #         if rec.crop_name_id:
    #             rec.crop_category_id = rec.crop_name_id.category.id
    #         else:
    #             rec.crop_category_id = False

    @api.depends('annual_line_ids.crop_name_id', 'annual_line_ids.crop_variety_id',
                 'perennial_line_ids.crop_name_id', 'perennial_line_ids.crop_variety_id')
    def _compute_primary_crop_details(self):
        for rec in self:
            crop_name = False
            crop_variety = False
            if rec.annual_line_ids:
                first_line = rec.annual_line_ids[0]
                crop_name = first_line.crop_name_id
                crop_variety = first_line.crop_variety_id
            elif rec.perennial_line_ids:
                first_line = rec.perennial_line_ids[0]
                crop_name = first_line.crop_name_id
                crop_variety = first_line.crop_variety_id
                
            rec.crop_name_id = crop_name.id if crop_name else False
            rec.crop_category_id = crop_name.category.id if crop_name and crop_name.category else False
            rec.crop_variety_id = crop_variety.id if crop_variety else False

    @api.depends('crop_name_id', 'actual_crop_name_id',
                 'collected_gc', 'actual_collected_gc',
                 'crop_variety_id', 'actual_crop_variety_id')
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

    @api.onchange('annual_line_ids')
    def _onchange_sync_annual_lines(self):
        for rec in self:
            for planned_line in rec.annual_line_ids:
                if not planned_line.season_id or not planned_line.crop_name_id:
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
                        'land_info_id': planned_line.land_info_id.id if planned_line.land_info_id else False,
                        'woreda_name_id': planned_line.woreda_name_id.id if planned_line.woreda_name_id else False,
                        'kebele_id': planned_line.kebele_id.id if planned_line.kebele_id else False,
                        'land_info_id': planned_line.land_info_id.id if planned_line.land_info_id else False,
                        'gps': planned_line.gps,
                        'crop_name_id': planned_line.crop_name_id.id,
                        'crop_category_id': planned_line.crop_category_id.id if planned_line.crop_category_id else False,
                        'crop_variety_id': planned_line.crop_variety_id.id if planned_line.crop_variety_id else False,
                        'actual_crop_area': planned_line.crop_planned_area,
                        'actual_growth_duration': planned_line.crop_growth_duration,
                        'has_cluster_farming': planned_line.has_cluster_farming if planned_line.has_cluster_farming else False,
                        'actual_cluster_plan': planned_line.cluster_plan if planned_line.cluster_plan else 0.0,
                        'actual_cluster_collected_land': planned_line.cluster_collected_land if planned_line.cluster_collected_land else 0.0,
                        'actual_cluster_collected_quintal': planned_line.cluster_collected_quintal if planned_line.cluster_collected_quintal else 0.0,
                        'actual_cluster_participant_farmers': planned_line.cluster_participant_farmers if planned_line.cluster_participant_farmers else 0,
                        'actual_collected_land': planned_line.collected_land if planned_line.collected_land else 0.0,
                        'actual_collected_land_quintal': planned_line.collected_land_quintal if planned_line.collected_land_quintal else 0.0,
                        'actual_collected_by_combiner': planned_line.collected_by_combiner if planned_line.collected_by_combiner else 0.0,
                        'actual_yield': planned_line.crop_expected if planned_line.crop_expected else 0.0,
                        'collected_gc': planned_line.collected_gc if planned_line.collected_gc else False,
                        'collected_ec': planned_line.collected_ec if planned_line.collected_ec else False,
                        'actual_seed_class': planned_line.seed_planned if planned_line.seed_planned else False,
                        'actual_seed_qty': planned_line.seed_planned_qty if planned_line.seed_planned_qty else 0.0,
                        'water_resource_line_ids': [(0, 0, {
                            'water_resource_id': w.water_resource_id.id,
                            'method_id': w.method_id,
                            'frequency': w.frequency,
                        }) for w in planned_line.water_resource_line_ids],
                        'actual_fertilizer_qty': planned_line.seed_planned_fertilizer_qty if planned_line.seed_planned_fertilizer_qty else 0.0,
                        'actual_fertilizer_type': planned_line.seed_planned_fertilizer_type if planned_line.seed_planned_fertilizer_type else False,
                    })
                    rec.actual_annual_line_ids += new_line
                else:
                    for actual in existing_actual:
                        if actual.is_manual:
                            actual.is_manual = False
                            actual.is_planning = True
                        if not actual.sync_id:
                            actual.sync_id = planned_line.sync_id
                        if planned_line.crop_name_id and actual.crop_name_id != planned_line.crop_name_id:
                            actual.crop_name_id = planned_line.crop_name_id.id
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
                        if planned_line.crop_planned_area and actual.actual_crop_area != planned_line.crop_planned_area:
                            actual.actual_crop_area = planned_line.crop_planned_area
                        if planned_line.crop_growth_duration and actual.actual_growth_duration != planned_line.crop_growth_duration:
                            actual.actual_growth_duration = planned_line.crop_growth_duration
                        if planned_line.seed_planned and actual.actual_seed_class != planned_line.seed_planned:
                            actual.actual_seed_class = planned_line.seed_planned
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
                        if planned_line.cluster_plan != actual.actual_cluster_plan:
                            actual.actual_cluster_plan = planned_line.cluster_plan
                        if planned_line.cluster_collected_land != actual.actual_cluster_collected_land:
                            actual.actual_cluster_collected_land = planned_line.cluster_collected_land
                        if planned_line.cluster_collected_quintal != actual.actual_cluster_collected_quintal:
                            actual.actual_cluster_collected_quintal = planned_line.cluster_collected_quintal
                        if planned_line.cluster_participant_farmers != actual.actual_cluster_participant_farmers:
                            actual.actual_cluster_participant_farmers = planned_line.cluster_participant_farmers
                        if planned_line.collected_land != actual.actual_collected_land:
                            actual.actual_collected_land = planned_line.collected_land
                        if planned_line.collected_land_quintal != actual.actual_collected_land_quintal:
                            actual.actual_collected_land_quintal = planned_line.collected_land_quintal
                        if planned_line.collected_by_combiner != actual.actual_collected_by_combiner:
                            actual.actual_collected_by_combiner = planned_line.collected_by_combiner
                        
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
                    new_prod = self.env['g2p.crop.production'].new({
                        'sync_id': planned_line.sync_id,
                        'season_id': planned_line.season_id.id if planned_line.season_id else False,
                        'land_info_id': planned_line.land_info_id.id if planned_line.land_info_id else False,
                        'crop_name_id': planned_line.crop_name_id.id,
                    })
                    rec.production_detail_ids += new_prod
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
            
            # Cleanup orphaned annual actual lines
            planned_sync_ids = [l.sync_id for l in rec.annual_line_ids if l.sync_id]
            valid_sync_ids = planned_sync_ids + [l.sync_id for l in rec.perennial_line_ids if l.sync_id] + [l.sync_id for l in rec.biennial_line_ids if l.sync_id] + [l.sync_id for l in rec.actual_annual_line_ids if l.sync_id and l.is_manual] + [l.sync_id for l in rec.actual_perennial_line_ids if l.sync_id and l.is_manual] + [l.sync_id for l in rec.actual_biennial_line_ids if l.sync_id and l.is_manual]
            if True:
                orphaned_actual = rec.actual_annual_line_ids.filtered(lambda l: l.sync_id and not l.is_manual and l.sync_id not in planned_sync_ids)
                if orphaned_actual:
                    rec.actual_annual_line_ids -= orphaned_actual
                
                orphaned_prod = rec.production_detail_ids.filtered(lambda p: p.sync_id and p.sync_id not in valid_sync_ids)
                if orphaned_prod:
                    rec.production_detail_ids -= orphaned_prod
    

    @api.onchange('perennial_line_ids')
    def _onchange_sync_perennial_lines(self):
        for rec in self:
            for planned_line in rec.perennial_line_ids:
                if not planned_line.season_id or not planned_line.crop_name_id:
                    continue
                
                if not planned_line.sync_id:
                    planned_line.sync_id = str(uuid.uuid4())
                
                # Sync Actual Lines
                existing_actual = rec.actual_perennial_line_ids.filtered(
                    lambda l: l.sync_id == planned_line.sync_id or (not l.sync_id and l.season_id == planned_line.season_id and l.crop_name_id == planned_line.crop_name_id)
                )
                if not existing_actual:
                    new_line = self.env['g2p.perennial.actual.line'].new({
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
                        'land_info_id': planned_line.land_info_id.id if planned_line.land_info_id else False,
                        'woreda_name_id': planned_line.woreda_name_id.id if planned_line.woreda_name_id else False,
                        'kebele_id': planned_line.kebele_id.id if planned_line.kebele_id else False,
                        'land_info_id': planned_line.land_info_id.id if planned_line.land_info_id else False,
                        'gps': planned_line.gps,
                        'crop_name_id': planned_line.crop_name_id.id,
                        'crop_category_id': planned_line.crop_category_id.id if planned_line.crop_category_id else False,
                        'crop_variety_id': planned_line.crop_variety_id.id if planned_line.crop_variety_id else False,
                        'actual_crop_area': planned_line.crop_planned_area,
                        'actual_growth_duration': planned_line.crop_growth_duration,
                        'has_cluster_farming': planned_line.has_cluster_farming if planned_line.has_cluster_farming else False,
                        'actual_cluster_plan': planned_line.cluster_plan if planned_line.cluster_plan else 0.0,
                        'actual_cluster_collected_land': planned_line.cluster_collected_land if planned_line.cluster_collected_land else 0.0,
                        'actual_cluster_collected_quintal': planned_line.cluster_collected_quintal if planned_line.cluster_collected_quintal else 0.0,
                        'actual_cluster_participant_farmers': planned_line.cluster_participant_farmers if planned_line.cluster_participant_farmers else 0,
                        'actual_collected_land': planned_line.collected_land if planned_line.collected_land else 0.0,
                        'actual_collected_land_quintal': planned_line.collected_land_quintal if planned_line.collected_land_quintal else 0.0,
                        'actual_collected_by_combiner': planned_line.collected_by_combiner if planned_line.collected_by_combiner else 0.0,
                        'actual_yield': planned_line.crop_expected if planned_line.crop_expected else 0.0,
                        'collected_gc': planned_line.collected_gc if planned_line.collected_gc else False,
                        'collected_ec': planned_line.collected_ec if planned_line.collected_ec else False,
                        'actual_seed_class': planned_line.seed_planned if planned_line.seed_planned else False,
                        'actual_seed_qty': planned_line.seed_planned_qty if planned_line.seed_planned_qty else 0.0,
                        'water_resource_line_ids': [(0, 0, {
                            'water_resource_id': w.water_resource_id.id,
                            'method_id': w.method_id,
                            'frequency': w.frequency,
                        }) for w in planned_line.water_resource_line_ids],
                        'actual_fertilizer_qty': planned_line.seed_planned_fertilizer_qty if planned_line.seed_planned_fertilizer_qty else 0.0,
                        'actual_fertilizer_type': planned_line.seed_planned_fertilizer_type if planned_line.seed_planned_fertilizer_type else False,
                    })
                    rec.actual_perennial_line_ids += new_line
                else:
                    for actual in existing_actual:
                        if actual.is_manual:
                            actual.is_manual = False
                            actual.is_planning = True
                        if not actual.sync_id:
                            actual.sync_id = planned_line.sync_id
                        if planned_line.crop_name_id and actual.crop_name_id != planned_line.crop_name_id:
                            actual.crop_name_id = planned_line.crop_name_id.id
                        if planned_line.seed_planned and actual.actual_seed_class != planned_line.seed_planned:
                            actual.actual_seed_class = planned_line.seed_planned
                        if planned_line.crop_planned_area and actual.actual_crop_area != planned_line.crop_planned_area:
                            actual.actual_crop_area = planned_line.crop_planned_area
                        if planned_line.crop_growth_duration and actual.actual_growth_duration != planned_line.crop_growth_duration:
                            actual.actual_growth_duration = planned_line.crop_growth_duration
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
                        if planned_line.land_category and actual.land_category != planned_line.land_category:
                            actual.land_category = planned_line.land_category
                        if planned_line.has_cluster_farming != actual.has_cluster_farming:
                            actual.has_cluster_farming = planned_line.has_cluster_farming
                        if planned_line.cluster_plan != actual.actual_cluster_plan:
                            actual.actual_cluster_plan = planned_line.cluster_plan
                        if planned_line.cluster_collected_land != actual.actual_cluster_collected_land:
                            actual.actual_cluster_collected_land = planned_line.cluster_collected_land
                        if planned_line.cluster_collected_quintal != actual.actual_cluster_collected_quintal:
                            actual.actual_cluster_collected_quintal = planned_line.cluster_collected_quintal
                        if planned_line.cluster_participant_farmers != actual.actual_cluster_participant_farmers:
                            actual.actual_cluster_participant_farmers = planned_line.cluster_participant_farmers
                        if planned_line.collected_land != actual.actual_collected_land:
                            actual.actual_collected_land = planned_line.collected_land
                        if planned_line.collected_land_quintal != actual.actual_collected_land_quintal:
                            actual.actual_collected_land_quintal = planned_line.collected_land_quintal
                        if planned_line.collected_by_combiner != actual.actual_collected_by_combiner:
                            actual.actual_collected_by_combiner = planned_line.collected_by_combiner

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
                    new_prod = self.env['g2p.crop.production'].new({
                        'sync_id': planned_line.sync_id,
                        'season_id': planned_line.season_id.id if planned_line.season_id else False,
                        'land_info_id': planned_line.land_info_id.id if planned_line.land_info_id else False,
                        'crop_name_id': planned_line.crop_name_id.id,
                    })
                    rec.production_detail_ids += new_prod
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
                            
            # Cleanup orphaned perennial actual lines
            planned_perennial_sync_ids = [l.sync_id for l in rec.perennial_line_ids if l.sync_id]
            valid_sync_ids = planned_perennial_sync_ids + [l.sync_id for l in rec.annual_line_ids if l.sync_id] + [l.sync_id for l in rec.actual_annual_line_ids if l.sync_id and l.is_manual] + [l.sync_id for l in rec.actual_perennial_line_ids if l.sync_id and l.is_manual] + [l.sync_id for l in rec.actual_biennial_line_ids if l.sync_id and l.is_manual]
            if True:
                orphaned_perennial_actual = rec.actual_perennial_line_ids.filtered(lambda l: l.sync_id and not l.is_manual and l.sync_id not in planned_perennial_sync_ids)
                if orphaned_perennial_actual:
                    rec.actual_perennial_line_ids -= orphaned_perennial_actual
                
                # Check for orphaned production lines
                orphaned_perennial_prod = rec.production_detail_ids.filtered(lambda p: p.sync_id and p.sync_id not in valid_sync_ids)
                if orphaned_perennial_prod:
                    rec.production_detail_ids -= orphaned_perennial_prod


    @api.onchange('biennial_line_ids')
    def _onchange_sync_biennial_lines(self):
        for rec in self:
            for planned_line in rec.biennial_line_ids:
                if not planned_line.season_id or not planned_line.crop_name_id:
                    continue
                
                if not planned_line.sync_id:
                    planned_line.sync_id = str(uuid.uuid4())
                
                # Sync Actual Lines
                existing_actual = rec.actual_biennial_line_ids.filtered(
                    lambda l: l.sync_id == planned_line.sync_id or (not l.sync_id and l.season_id == planned_line.season_id and l.crop_name_id == planned_line.crop_name_id)
                )
                if not existing_actual:
                    new_line = self.env['g2p.biennial.actual.line'].new({
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
                        'land_info_id': planned_line.land_info_id.id if planned_line.land_info_id else False,
                        'woreda_name_id': planned_line.woreda_name_id.id if planned_line.woreda_name_id else False,
                        'kebele_id': planned_line.kebele_id.id if planned_line.kebele_id else False,
                        'land_info_id': planned_line.land_info_id.id if planned_line.land_info_id else False,
                        'gps': planned_line.gps,
                        'crop_name_id': planned_line.crop_name_id.id,
                        'crop_category_id': planned_line.crop_category_id.id if planned_line.crop_category_id else False,
                        'crop_variety_id': planned_line.crop_variety_id.id if planned_line.crop_variety_id else False,
                        'actual_crop_area': planned_line.crop_planned_area,
                        'actual_growth_duration': planned_line.crop_growth_duration,
                        'has_cluster_farming': planned_line.has_cluster_farming if planned_line.has_cluster_farming else False,
                        'actual_cluster_plan': planned_line.cluster_plan if planned_line.cluster_plan else 0.0,
                        'actual_cluster_collected_land': planned_line.cluster_collected_land if planned_line.cluster_collected_land else 0.0,
                        'actual_cluster_collected_quintal': planned_line.cluster_collected_quintal if planned_line.cluster_collected_quintal else 0.0,
                        'actual_cluster_participant_farmers': planned_line.cluster_participant_farmers if planned_line.cluster_participant_farmers else 0,
                        'actual_collected_land': planned_line.collected_land if planned_line.collected_land else 0.0,
                        'actual_collected_land_quintal': planned_line.collected_land_quintal if planned_line.collected_land_quintal else 0.0,
                        'actual_collected_by_combiner': planned_line.collected_by_combiner if planned_line.collected_by_combiner else 0.0,
                        'actual_yield': planned_line.crop_expected if planned_line.crop_expected else 0.0,
                        'collected_gc': planned_line.collected_gc if planned_line.collected_gc else False,
                        'collected_ec': planned_line.collected_ec if planned_line.collected_ec else False,
                        'actual_seed_class': planned_line.seed_planned if planned_line.seed_planned else False,
                        'actual_seed_qty': planned_line.seed_planned_qty if planned_line.seed_planned_qty else 0.0,
                        'water_resource_line_ids': [(0, 0, {
                            'water_resource_id': w.water_resource_id.id,
                            'method_id': w.method_id,
                            'frequency': w.frequency,
                        }) for w in planned_line.water_resource_line_ids],
                        'actual_fertilizer_qty': planned_line.seed_planned_fertilizer_qty if planned_line.seed_planned_fertilizer_qty else 0.0,
                        'actual_fertilizer_type': planned_line.seed_planned_fertilizer_type if planned_line.seed_planned_fertilizer_type else False,
                    })
                    rec.actual_biennial_line_ids += new_line
                else:
                    for actual in existing_actual:
                        if actual.is_manual:
                            actual.is_manual = False
                            actual.is_planning = True
                        if not actual.sync_id:
                            actual.sync_id = planned_line.sync_id
                        if planned_line.crop_name_id and actual.crop_name_id != planned_line.crop_name_id:
                            actual.crop_name_id = planned_line.crop_name_id.id
                        if planned_line.seed_planned and actual.actual_seed_class != planned_line.seed_planned:
                            actual.actual_seed_class = planned_line.seed_planned
                        if planned_line.crop_planned_area and actual.actual_crop_area != planned_line.crop_planned_area:
                            actual.actual_crop_area = planned_line.crop_planned_area
                        if planned_line.crop_growth_duration and actual.actual_growth_duration != planned_line.crop_growth_duration:
                            actual.actual_growth_duration = planned_line.crop_growth_duration
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
                        if planned_line.land_category and actual.land_category != planned_line.land_category:
                            actual.land_category = planned_line.land_category
                        if planned_line.has_cluster_farming != actual.has_cluster_farming:
                            actual.has_cluster_farming = planned_line.has_cluster_farming
                        if planned_line.cluster_plan != actual.actual_cluster_plan:
                            actual.actual_cluster_plan = planned_line.cluster_plan
                        if planned_line.cluster_collected_land != actual.actual_cluster_collected_land:
                            actual.actual_cluster_collected_land = planned_line.cluster_collected_land
                        if planned_line.cluster_collected_quintal != actual.actual_cluster_collected_quintal:
                            actual.actual_cluster_collected_quintal = planned_line.cluster_collected_quintal
                        if planned_line.cluster_participant_farmers != actual.actual_cluster_participant_farmers:
                            actual.actual_cluster_participant_farmers = planned_line.cluster_participant_farmers
                        if planned_line.collected_land != actual.actual_collected_land:
                            actual.actual_collected_land = planned_line.collected_land
                        if planned_line.collected_land_quintal != actual.actual_collected_land_quintal:
                            actual.actual_collected_land_quintal = planned_line.collected_land_quintal
                        if planned_line.collected_by_combiner != actual.actual_collected_by_combiner:
                            actual.actual_collected_by_combiner = planned_line.collected_by_combiner

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
                    new_prod = self.env['g2p.crop.production'].new({
                        'sync_id': planned_line.sync_id,
                        'season_id': planned_line.season_id.id if planned_line.season_id else False,
                        'land_info_id': planned_line.land_info_id.id if planned_line.land_info_id else False,
                        'crop_name_id': planned_line.crop_name_id.id,
                    })
                    rec.production_detail_ids += new_prod
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
                            
            # Cleanup orphaned biennial actual lines
            planned_biennial_sync_ids = [l.sync_id for l in rec.biennial_line_ids if l.sync_id]
            valid_sync_ids = planned_biennial_sync_ids + [l.sync_id for l in rec.annual_line_ids if l.sync_id] + [l.sync_id for l in rec.actual_annual_line_ids if l.sync_id and l.is_manual] + [l.sync_id for l in rec.actual_biennial_line_ids if l.sync_id and l.is_manual] + [l.sync_id for l in rec.actual_biennial_line_ids if l.sync_id and l.is_manual]
            if True:
                orphaned_biennial_actual = rec.actual_biennial_line_ids.filtered(lambda l: l.sync_id and not l.is_manual and l.sync_id not in planned_biennial_sync_ids)
                if orphaned_biennial_actual:
                    rec.actual_biennial_line_ids -= orphaned_biennial_actual
                
                # Check for orphaned production lines
                orphaned_biennial_prod = rec.production_detail_ids.filtered(lambda p: p.sync_id and p.sync_id not in valid_sync_ids)
                if orphaned_biennial_prod:
                    rec.production_detail_ids -= orphaned_biennial_prod

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
                    if prod_line.qty_harvested != actual_line.actual_yield:
                        prod_line.qty_harvested = actual_line.actual_yield
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
            valid_sync_ids = [l.sync_id for l in rec.annual_line_ids if l.sync_id] + [l.sync_id for l in rec.perennial_line_ids if l.sync_id] + [l.sync_id for l in rec.biennial_line_ids if l.sync_id] + [l.sync_id for l in rec.actual_annual_line_ids if l.sync_id and l.is_manual] + [l.sync_id for l in rec.actual_perennial_line_ids if l.sync_id and l.is_manual] + [l.sync_id for l in rec.actual_biennial_line_ids if l.sync_id and l.is_manual]
            orphaned_prod = rec.production_detail_ids.filtered(lambda p: p.sync_id and p.sync_id not in valid_sync_ids)
            if orphaned_prod:
                rec.production_detail_ids -= orphaned_prod

    @api.onchange('actual_perennial_line_ids')
    def _onchange_sync_actual_to_production_perennial(self):
        for rec in self:
            for actual_line in rec.actual_perennial_line_ids:
                if not actual_line.sync_id:
                    actual_line.sync_id = str(uuid.uuid4())
                prod_line = rec.production_detail_ids.filtered(lambda p: p.sync_id == actual_line.sync_id)
                planned_line = rec.perennial_line_ids.filtered(lambda l: l.sync_id == actual_line.sync_id)
                expected_yield = planned_line[0].crop_expected if planned_line else 0.0
                planned_area = planned_line[0].crop_planned_area if planned_line else 0.0

                if prod_line:
                    prod_line = prod_line[0]
                    if prod_line.season_id != actual_line.season_id:
                        prod_line.season_id = actual_line.season_id
                    if prod_line.crop_name_id != actual_line.crop_name_id:
                        prod_line.crop_name_id = actual_line.crop_name_id
                    if prod_line.land_info_id != actual_line.land_info_id:
                        prod_line.land_info_id = actual_line.land_info_id.id
                    if prod_line.actual_sowing_date != actual_line.collected_gc:
                        prod_line.actual_sowing_date = actual_line.collected_gc
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
                    if prod_line.qty_harvested != actual_line.actual_yield:
                        prod_line.qty_harvested = actual_line.actual_yield
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
            valid_sync_ids = [l.sync_id for l in rec.annual_line_ids if l.sync_id] + [l.sync_id for l in rec.perennial_line_ids if l.sync_id] + [l.sync_id for l in rec.biennial_line_ids if l.sync_id] + [l.sync_id for l in rec.actual_annual_line_ids if l.sync_id and l.is_manual] + [l.sync_id for l in rec.actual_perennial_line_ids if l.sync_id and l.is_manual] + [l.sync_id for l in rec.actual_biennial_line_ids if l.sync_id and l.is_manual]
            orphaned_prod = rec.production_detail_ids.filtered(lambda p: p.sync_id and p.sync_id not in valid_sync_ids)
            if orphaned_prod:
                rec.production_detail_ids -= orphaned_prod


    @api.onchange('actual_biennial_line_ids')
    def _onchange_sync_actual_to_production_biennial(self):
        for rec in self:
            for actual_line in rec.actual_biennial_line_ids:
                if not actual_line.sync_id:
                    actual_line.sync_id = str(uuid.uuid4())
                prod_line = rec.production_detail_ids.filtered(lambda p: p.sync_id == actual_line.sync_id)
                planned_line = rec.biennial_line_ids.filtered(lambda l: l.sync_id == actual_line.sync_id)
                expected_yield = planned_line[0].crop_expected if planned_line else 0.0
                planned_area = planned_line[0].crop_planned_area if planned_line else 0.0

                if prod_line:
                    prod_line = prod_line[0]
                    if prod_line.season_id != actual_line.season_id:
                        prod_line.season_id = actual_line.season_id
                    if prod_line.crop_name_id != actual_line.crop_name_id:
                        prod_line.crop_name_id = actual_line.crop_name_id
                    if prod_line.land_info_id != actual_line.land_info_id:
                        prod_line.land_info_id = actual_line.land_info_id.id
                    if prod_line.actual_sowing_date != actual_line.collected_gc:
                        prod_line.actual_sowing_date = actual_line.collected_gc
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
                    if prod_line.qty_harvested != actual_line.actual_yield:
                        prod_line.qty_harvested = actual_line.actual_yield
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

    @api.onchange('production_detail_ids')
    def _onchange_sync_production_to_actual(self):
        for rec in self:
            for prod_line in rec.production_detail_ids:
                if not prod_line.sync_id:
                    continue
                # Find corresponding actual line (could be annual, perennial, or biennial)
                actual_annual = rec.actual_annual_line_ids.filtered(lambda l: l.sync_id == prod_line.sync_id)
                actual_perennial = rec.actual_perennial_line_ids.filtered(lambda l: l.sync_id == prod_line.sync_id)
                actual_biennial = rec.actual_biennial_line_ids.filtered(lambda l: l.sync_id == prod_line.sync_id)
                actual_line = (actual_annual or actual_perennial or actual_biennial)
                if actual_line:
                    actual = actual_line[0]
                    if actual.actual_yield != prod_line.qty_harvested:
                        actual.actual_yield = prod_line.qty_harvested

            # Cleanup orphaned production details when actual is deleted
            valid_sync_ids = [l.sync_id for l in rec.annual_line_ids if l.sync_id] + [l.sync_id for l in rec.biennial_line_ids if l.sync_id] + [l.sync_id for l in rec.biennial_line_ids if l.sync_id] + [l.sync_id for l in rec.actual_annual_line_ids if l.sync_id and l.is_manual] + [l.sync_id for l in rec.actual_biennial_line_ids if l.sync_id and l.is_manual] + [l.sync_id for l in rec.actual_biennial_line_ids if l.sync_id and l.is_manual]
            orphaned_prod = rec.production_detail_ids.filtered(lambda p: p.sync_id and p.sync_id not in valid_sync_ids)
            if orphaned_prod:
                rec.production_detail_ids -= orphaned_prod

class G2PPerennialLine(models.Model):
    _name = "g2p.perennial.line"
    _description = "Perennial Crop Planned Line"

    crop_registry_id = fields.Many2one("g2p.crop.registry", string="Crop Registry", ondelete="cascade")
    sync_id = fields.Char(string="Sync ID", default=lambda self: str(uuid.uuid4()))
    land_info_id = fields.Many2one('g2p.land.information', string="Land ID")
    region_name_id = fields.Many2one('g2p.region', string='Region')
    zone_name_id = fields.Many2one('g2p.zone', string='Zone')
    woreda_name_id = fields.Many2one('g2p.woreda', string='Woreda')
    kebele_id = fields.Many2one('g2p.kebele', string='Kebele')
    gps = fields.Char(string='GPS Coordinates')

    ownership_type = fields.Selection([('owner', 'Owner'), ('tenant', 'Tenant'), ('crop_share', 'Crop Sharing'), ('family_gift', 'Family Gift')], string="Ownership Type")
    land_area = fields.Float(string="Total Land Area (ha)")
    land_category = fields.Selection([('annual', 'Annual Crop'), ('perennial', 'Perennial Crop'), ('biennial', 'Biennial Crop')], string="Plot Category")
    soil_fertility = fields.Char(string="Soil Fertility")
    season_id = fields.Many2one('g2p.season', string="Season", required=True)
    start_gc = fields.Date(string="Start GC")
    start_month = fields.Integer(string="Start Month", compute="_compute_start_date", store=True)
    start_day = fields.Integer(string="Start Day", compute="_compute_start_date", store=True)
    end_gc = fields.Date(string="End GC")
    end_month = fields.Integer(string="End Month", compute="_compute_end_date", store=True)
    end_day = fields.Integer(string="End Day", compute="_compute_end_date", store=True)
    
    crop_name_id = fields.Many2one("g2p.crop", string="Crop", required=True)
    crop_id_ref = fields.Char(related="crop_name_id.crop_id", string="Crop ID", readonly=True)
    collected_gc = fields.Date(string="Planned Date (GC)")
    collected_ec = fields.Char(string="Planned Date (EC)")
    crop_category_id = fields.Many2one("g2p.crop.category", string="Crop Category", compute="_compute_crop_category", store=True, readonly=True)
    crop_variety_id = fields.Many2one("g2p.crop.variety", string="Crop Variety")
    
    crop_planned_area = fields.Float(string="Planned Crop Area (ha)")

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
                    self.woreda_name_id = self.land_info_id.land_kebele.woreda.id
                    if self.land_info_id.land_kebele.woreda.zone:
                        self.zone_name_id = self.land_info_id.land_kebele.woreda.zone.id
                        if self.land_info_id.land_kebele.woreda.zone.region:
                            self.region_name_id = self.land_info_id.land_kebele.woreda.zone.region.id
                        else:
                            self.region_name_id = False
                    else:
                        self.zone_name_id = False
                        self.region_name_id = False
                else:
                    self.woreda_name_id = False
                    self.zone_name_id = False
                    self.region_name_id = False
            else:
                self.kebele_id = False
                self.woreda_name_id = False
                self.zone_name_id = False
                self.region_name_id = False

            if hasattr(self.land_info_id, 'polygon_data') and self.land_info_id.polygon_data:
                self.gps = self.land_info_id.polygon_data
            else:
                self.gps = False
    crop_growth_duration = fields.Float(string="Average Growth Duration (days)")
    crop_expected = fields.Float(string="Expected Yield (quintals)")
    
    seed_planned = fields.Selection([('local', 'Local'), ('improved', 'Improved')], string="Seed Type")
    seed_planned_qty = fields.Float(string="Planned Seed Quantity (kg)")
    seed_planned_fertilizer_type = fields.Selection([
        ('organic', 'Organic'),
        ('inorganic', 'Inorganic'),
        ('biofertilizer', 'Bio Fertilizer')
    ], string="Planned Fertilizer Type")

    seed_planned_fertilizer_qty = fields.Float(string="Planned Fertilizer Quantity (kg)")
    seed_planned_fertilizer_sack = fields.Float(string="Planned Fertilizer Sacks Count", compute="_compute_planned_fertilizer_sacks", store=True)
    water_resource_line_ids = fields.One2many('g2p.water.resource.line', 'perennial_line_id', string="Water Resources")
    
    # Actual Inputs Fields
    actual_season_id = fields.Many2one('g2p.season', string="Actual Season")
    actual_start_gc = fields.Date(string="Actual Start GC")
    actual_start_month = fields.Integer(string="Actual Start Month")
    actual_start_day = fields.Integer(string="Actual Start Day")
    actual_end_gc = fields.Date(string="Actual End GC")
    actual_end_month = fields.Integer(string="Actual End Month")
    actual_end_day = fields.Integer(string="Actual End Day")
    
    actual_crop_name_id = fields.Many2one("g2p.crop", string="Actual Crop")
    actual_collected_gc = fields.Date(string="Actual Date (GC)")
    actual_collected_ec = fields.Char(string="Actual Date (EC)")
    actual_crop_category_id = fields.Many2one("g2p.crop.category", string="Actual Crop Category", compute="_compute_actual_crop_category", store=True)
    actual_crop_variety_id = fields.Many2one("g2p.crop.variety", string="Actual Crop Variety")

    actual_crop_area = fields.Float(string="Actual Crop Area (ha)")
    actual_growth_duration = fields.Float(string="Actual Growth Duration (days)")
    
    actual_seed_class = fields.Selection([('local', 'Local'), ('improved', 'Improved')], string="Seed Type")
    actual_seed_qty = fields.Float(string="Actual Seed Quantity (kg)")
    actual_fertilizer_type = fields.Selection([
        ('organic', 'Organic'),
        ('inorganic', 'Inorganic'),
        ('biofertilizer', 'Bio Fertilizer')
    ], string="Actual Fertilizer Type")

    actual_fertilizer_qty = fields.Float(string="Actual Fertilizer Quantity (kg)")
    actual_fertilizer_sack = fields.Float(string="Actual Fertilizer Sacks Count", compute="_compute_actual_fertilizer_sacks", store=True)
    
    pest_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Pest Occurrence")
    pest_line_ids = fields.One2many('g2p.crop.pest.line', 'perennial_line_id', string="Pest Details")
    
    weed_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Weed Occurrence")
    weed_line_ids = fields.One2many('g2p.crop.weed.line', 'perennial_line_id', string="Weed Details")
    
    actual_yield = fields.Float(string="Actual Yield (quintal)")
    cultivated_by = fields.Selection([
        ('tractor', 'Tractor'),
        ('other', 'Other'),
    ], string="Cultivation Type")

    

    
    planned_labor = fields.Integer(string="Planned Labor")
    has_cluster_farming = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string="Have you done any cluster farming or related activities earlier?")
    cluster_plan = fields.Float(string="Cluster Plan")
    cluster_collected_land = fields.Float(string="Cluster Collected Land")
    cluster_collected_quintal = fields.Float(string="Cluster Collected Quintal")
    cluster_participant_farmers = fields.Integer(string="Cluster Participant Farmers")
    collected_land = fields.Float(string="Collected Land")
    collected_land_quintal = fields.Float(string="Collected Land Quintal")
    collected_by_combiner = fields.Float(string="Collected by Combiner")


    @api.depends('seed_planned_fertilizer_qty')
    def _compute_planned_fertilizer_sacks(self):
        for rec in self:
            if rec.seed_planned_fertilizer_qty:
                rec.seed_planned_fertilizer_sack = rec.seed_planned_fertilizer_qty / 50.0
            else:
                rec.seed_planned_fertilizer_sack = 0.0

    @api.onchange('seed_planned_fertilizer_qty')
    def _onchange_fertilizer_qty(self):
        for rec in self:
            if rec.seed_planned_fertilizer_qty:
                rec.seed_planned_fertilizer_sack = rec.seed_planned_fertilizer_qty / 50.0
            else:
                rec.seed_planned_fertilizer_sack = 0.0

    @api.depends('actual_fertilizer_qty')
    def _compute_actual_fertilizer_sacks(self):
        for rec in self:
            if rec.actual_fertilizer_qty:
                rec.actual_fertilizer_sack = rec.actual_fertilizer_qty / 50.0
            else:
                rec.actual_fertilizer_sack = 0.0

    @api.onchange('crop_planned_area')
    def _onchange_crop_planned_area(self):
        if self.crop_registry_id and self.crop_planned_area and self.land_info_id:
            same_land_lines = self.crop_registry_id.perennial_line_ids.filtered(lambda l: l.land_info_id == self.land_info_id)
            total_planned = sum(same_land_lines.mapped('crop_planned_area'))
            max_area = self.land_info_id.total_land_area
            if total_planned > max_area:
                attempted_area = self.crop_planned_area
                allocated_area = total_planned - attempted_area
                remaining_area = max_area - allocated_area
                
                # If they already messed up other lines, don't let it go negative in the message
                if remaining_area < 0:
                    remaining_area = 0.0
                    
                self.crop_planned_area = 0.0
                return {
                    'warning': {
                        'title': "Area Exceeded",
                        'message': "You entered %.2f ha, but only %.2f ha is remaining out of the total %.2f ha (%.2f ha is already allocated to other crops)." % (attempted_area, remaining_area, max_area, allocated_area)
                    }
                }


    @api.onchange('season_id')
    def _onchange_season_id(self):
        if self.season_id:
            self.start_gc = self.season_id.start_gc
            self.end_gc = self.season_id.end_gc

    @api.depends("start_gc")
    def _compute_start_date(self):
        for record in self:
            if record.start_gc:
                record.start_month = record.start_gc.month
                record.start_day = record.start_gc.day
            else:
                record.start_month = record.start_day = 0

    @api.depends("end_gc")
    def _compute_end_date(self):
        for record in self:
            if record.end_gc:
                record.end_month = record.end_gc.month
                record.end_day = record.end_gc.day
            else:
                record.end_month = record.end_day = 0

    @api.depends("crop_name_id")
    def _compute_crop_category(self):
        for rec in self:
            if rec.crop_name_id:
                rec.crop_category_id = rec.crop_name_id.category.id
            else:
                rec.crop_category_id = False

    @api.depends("actual_crop_name_id")
    def _compute_actual_crop_category(self):
        for rec in self:
            if rec.actual_crop_name_id:
                rec.actual_crop_category_id = rec.actual_crop_name_id.category.id
            else:
                rec.actual_crop_category_id = False

    @api.onchange("crop_name_id")
    def _onchange_crop(self):
        self.crop_variety_id = False
        return {
            "domain": {
                "crop_variety_id": [
                    ("crop_id", "=", self.crop_name_id.id)
                ]
            }
        }

    @api.onchange("collected_gc", "start_gc", "end_gc")
    def _onchange_collected_gc(self):
        if self.collected_gc:
            if self.start_gc and self.end_gc:
                # Check if the date is within the season's start and end months/dates
                if self.collected_gc < self.start_gc or self.collected_gc > self.end_gc:
                    self.collected_gc = False
                    self.collected_ec = False
                    return {
                        'warning': {
                            'title': 'Invalid Planned Date',
                            'message': 'Planned Date (GC) must be within the Season Details (Start GC and End GC).'
                        }
                    }

            cdate = date(
                self.collected_gc.year,
                self.collected_gc.month,
                self.collected_gc.day,
            )
            ethiopian_date = eth_date.to_ethiopian(
                cdate.year, cdate.month, cdate.day
            )
            self.collected_ec = eth_date.convert_tuple_to_string_with_separator(
                ethiopian_date
            )

    @api.onchange("collected_ec")
    def _onchange_collected_ec(self):
        if self.collected_ec:
            eth_date.check_ethipian_date_str(self.collected_ec, future_date=True)
            date_list = re.split("[-/,]", self.collected_ec)
            gc_date = eth_date.to_gregorian(
                int(date_list[2]), int(date_list[1]), int(date_list[0])
            )
            self.collected_gc = gc_date


class G2PLandPrepMethod(models.Model):
    _name = "g2p.land.prep.method"
    _description = "Land Preparation Method"

    name = fields.Char(string="Method Name", required=True)


class G2PPerennialActualLine(models.Model):
    _name = "g2p.perennial.actual.line"
    _description = "Perennial Crop Actual Line"
    @api.constrains('actual_yield')
    def _check_actual_yield(self):
        for rec in self:
            if rec.actual_yield > 0 and rec.crop_registry_id:
                planned_line = rec.crop_registry_id.perennial_line_ids.filtered(lambda l: l.sync_id == rec.sync_id)
                if planned_line and rec.actual_yield > planned_line[0].crop_expected:
                    raise ValidationError(f"Actual yield ({rec.actual_yield}) cannot be greater than expected yield ({planned_line[0].crop_expected}).")

    @api.onchange('actual_yield')
    def _onchange_actual_yield(self):
        if self.actual_yield > 0 and self.crop_registry_id:
            planned_line = self.crop_registry_id.perennial_line_ids.filtered(lambda l: l.sync_id == self.sync_id)
            if planned_line and self.actual_yield > planned_line[0].crop_expected:
                self.actual_yield = 0.0
                return {
                    'warning': {
                        'title': 'Invalid Yield',
                        'message': f"Actual Yield cannot be greater than Expected Yield ({planned_line[0].crop_expected})."
                    }
                }

    crop_registry_id = fields.Many2one("g2p.crop.registry", string="Crop Registry", ondelete="cascade")
    sync_id = fields.Char(string="Sync ID", default=lambda self: str(uuid.uuid4()))
    is_manual = fields.Boolean(string="Is Manual", default=True)
    is_planning = fields.Boolean(string="Is Planning", default=False)
    land_info_id = fields.Many2one('g2p.land.information', string="Land ID")
    region_name_id = fields.Many2one('g2p.region', string='Region')
    zone_name_id = fields.Many2one('g2p.zone', string='Zone')
    woreda_name_id = fields.Many2one('g2p.woreda', string='Woreda')
    kebele_id = fields.Many2one('g2p.kebele', string='Kebele')
    gps = fields.Char(string='GPS Coordinates')

    ownership_type = fields.Selection([('owner', 'Owner'), ('tenant', 'Tenant'), ('crop_share', 'Crop Sharing'), ('family_gift', 'Family Gift')], string="Ownership Type")
    land_area = fields.Float(string="Total Land Area (ha)")
    land_category = fields.Selection([('annual', 'Annual Crop'), ('perennial', 'Perennial Crop'), ('biennial', 'Biennial Crop')], string="Plot Category")
    soil_fertility = fields.Char(string="Soil Fertility")

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
                    self.woreda_name_id = self.land_info_id.land_kebele.woreda.id
                    if self.land_info_id.land_kebele.woreda.zone:
                        self.zone_name_id = self.land_info_id.land_kebele.woreda.zone.id
                        if self.land_info_id.land_kebele.woreda.zone.region:
                            self.region_name_id = self.land_info_id.land_kebele.woreda.zone.region.id
                        else:
                            self.region_name_id = False
                    else:
                        self.zone_name_id = False
                        self.region_name_id = False
                else:
                    self.woreda_name_id = False
                    self.zone_name_id = False
                    self.region_name_id = False
            else:
                self.kebele_id = False
                self.woreda_name_id = False
                self.zone_name_id = False
                self.region_name_id = False

            if hasattr(self.land_info_id, 'polygon_data') and self.land_info_id.polygon_data:
                self.gps = self.land_info_id.polygon_data
            else:
                self.gps = False
                
            if self.crop_registry_id:
                planned_line = self.crop_registry_id.perennial_line_ids.filtered(
                    lambda l: l.land_info_id.id == self.land_info_id.id
                )
                if planned_line:
                    planned_line = planned_line[0]
                    water_resources = []
                    for w in planned_line.water_resource_line_ids:
                        water_resources.append((0, 0, {
                            'water_resource_id': w.water_resource_id.id,
                            'method_id': w.method_id,
                            'frequency': w.frequency,
                            'crop_registry_id': self.crop_registry_id.id,
                        }))
                    if water_resources:
                        self.water_resource_line_ids = [(5, 0, 0)] + water_resources
    season_id = fields.Many2one('g2p.season', string="Season", required=True)
    crop_name_id = fields.Many2one("g2p.crop", string="Crop", required=True)
    crop_id_ref = fields.Char(related="crop_name_id.crop_id", string="Crop ID", readonly=True)
    collected_gc = fields.Date(string="Actual Planted Date (GC)")
    collected_ec = fields.Char(string="Actual Planted Date (EC)")
    crop_category_id = fields.Many2one("g2p.crop.category", string="Crop Category", compute="_compute_crop_category", store=True, readonly=True)
    crop_variety_id = fields.Many2one("g2p.crop.variety", string="Crop Variety")
    remark = fields.Char(string="Remark")
    actual_crop_area = fields.Float(string="Actual Crop Area (ha)")
    actual_growth_duration = fields.Float(string="Actual Growth Duration (days)")
    
    actual_seed_class = fields.Selection([('local', 'Local'), ('improved', 'Improved')], string="Seed Type")
    actual_seed_qty = fields.Float(string="Actual Seed Quantity (kg)")
    actual_fertilizer_type = fields.Selection([
        ('organic', 'Organic'),
        ('inorganic', 'Inorganic'),
        ('biofertilizer', 'Bio Fertilizer')
    ], string="Actual Fertilizer Type")

    actual_fertilizer_qty = fields.Float(string="Actual Fertilizer Quantity (kg)")
    actual_fertilizer_sack = fields.Float(string="Actual Fertilizer Sacks Count", compute="_compute_actual_fertilizer_sacks", store=True)

    has_cluster_farming = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string="Have you done any cluster farming or related activities earlier?")
    actual_cluster_plan = fields.Float(string="Actual Cluster Plan")
    actual_cluster_collected_land = fields.Float(string="Actual Cluster Collected Land")
    actual_cluster_collected_quintal = fields.Float(string="Actual Cluster Collected Quintal")
    actual_cluster_participant_farmers = fields.Integer(string="Actual Cluster Participant Farmers")
    actual_collected_land = fields.Float(string="Actual Collected Land")
    actual_collected_land_quintal = fields.Float(string="Actual Collected Land Quintal")
    actual_collected_by_combiner = fields.Float(string="Actual Collected by Combiner")
    
    pest_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Pest Occurrence")
    pest_line_ids = fields.One2many('g2p.crop.pest.line', 'actual_perennial_line_id', string="Pest Details")
    
    weed_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Weed Occurrence")
    weed_line_ids = fields.One2many('g2p.crop.weed.line', 'actual_perennial_line_id', string="Weed Details")
    
    actual_yield = fields.Float(string="Actual Yield (quintal)")
    cultivated_by = fields.Selection([
        ('tractor', 'Tractor'),
        ('other', 'Other'),
    ], string="Cultivation Type")
    land_prep_method_ids = fields.Many2many("g2p.land.prep.method", string="Land Prep Methods")
    
    water_resource_line_ids = fields.One2many(
        "g2p.actual.water.resource.line",
        "actual_perennial_line_id",
        string="Water Resources",
    )
    
    start_gc = fields.Date(string="Start GC")
    start_month = fields.Integer(string="Start Month", compute="_compute_start_date", store=True)
    start_day = fields.Integer(string="Start Day", compute="_compute_start_date", store=True)
    end_gc = fields.Date(string="End GC")
    end_month = fields.Integer(string="End Month", compute="_compute_end_date", store=True)
    end_day = fields.Integer(string="End Day", compute="_compute_end_date", store=True)
    
    is_mismatch = fields.Boolean(string="Mismatch", compute="_compute_is_mismatch", store=True)

    @api.onchange('actual_crop_area')
    def _onchange_actual_crop_area(self):
        if self.crop_registry_id and self.actual_crop_area and self.land_info_id:
            same_land_lines = self.crop_registry_id.actual_perennial_line_ids.filtered(lambda l: l.land_info_id == self.land_info_id)
            total_actual = sum(same_land_lines.mapped('actual_crop_area'))
            max_area = self.land_info_id.total_land_area
            if total_actual > max_area:
                attempted_area = self.actual_crop_area
                allocated_area = total_actual - attempted_area
                remaining_area = max_area - allocated_area
                
                if remaining_area < 0:
                    remaining_area = 0.0
                    
                self.actual_crop_area = 0.0
                return {
                    'warning': {
                        'title': "Area Exceeded",
                        'message': "You entered %.2f ha, but only %.2f ha is remaining out of the total %.2f ha (%.2f ha is already allocated to other actual crops)." % (attempted_area, remaining_area, max_area, allocated_area)
                    }
                }

    @api.depends('actual_fertilizer_qty')
    def _compute_actual_fertilizer_sacks(self):
        for rec in self:
            if rec.actual_fertilizer_qty:
                rec.actual_fertilizer_sack = rec.actual_fertilizer_qty / 50.0
            else:
                rec.actual_fertilizer_sack = 0.0

    @api.onchange('actual_fertilizer_qty')
    def _onchange_fertilizer_qty(self):
        for rec in self:
            if rec.actual_fertilizer_qty:
                rec.actual_fertilizer_sack = rec.actual_fertilizer_qty / 50.0
            else:
                rec.actual_fertilizer_sack = 0.0

    @api.onchange('season_id')
    def _onchange_season_id(self):
        if self.season_id:
            self.start_gc = self.season_id.start_gc
            self.end_gc = self.season_id.end_gc
            if self.season_id.start_gc:
                self.start_month = self.season_id.start_gc.month
                self.start_day = self.season_id.start_gc.day
            if self.season_id.end_gc:
                self.end_month = self.season_id.end_gc.month
                self.end_day = self.season_id.end_gc.day

    @api.depends("start_gc")
    def _compute_start_date(self):
        for record in self:
            if record.start_gc:
                record.start_month = record.start_gc.month
                record.start_day = record.start_gc.day
            else:
                record.start_month = record.start_day = 0

    @api.depends("end_gc")
    def _compute_end_date(self):
        for record in self:
            if record.end_gc:
                record.end_month = record.end_gc.month
                record.end_day = record.end_gc.day
            else:
                record.end_month = record.end_day = 0

    @api.depends("crop_name_id")
    def _compute_crop_category(self):
        for rec in self:
            if rec.crop_name_id:
                rec.crop_category_id = rec.crop_name_id.category.id
            else:
                rec.crop_category_id = False

    @api.depends("crop_name_id", "crop_variety_id", "collected_gc", "season_id",
                 "crop_registry_id.perennial_line_ids",
                 "crop_registry_id.perennial_line_ids.crop_name_id",
                 "crop_registry_id.perennial_line_ids.crop_variety_id",
                 "crop_registry_id.perennial_line_ids.collected_gc",
                 "crop_registry_id.perennial_line_ids.season_id")
    def _compute_is_mismatch(self):
        for rec in self:
            if not rec.crop_registry_id or not rec.crop_name_id:
                rec.is_mismatch = False
                continue
            planned_lines = rec.crop_registry_id.perennial_line_ids
            matched = False
            for planned in planned_lines:
                if (planned.crop_name_id.id == rec.crop_name_id.id
                        and planned.crop_variety_id.id == rec.crop_variety_id.id
                        and planned.season_id.id == rec.season_id.id
                        and planned.collected_gc == rec.collected_gc):
                    matched = True
                    break
            rec.is_mismatch = not matched

    @api.depends("crop_name_id")
    def _compute_crop_category(self):
        for rec in self:
            rec.crop_category_id = (
                rec.crop_name_id.category.id
                if rec.crop_name_id
                else False
            )

    @api.onchange("crop_name_id")
    def _onchange_crop(self):
        self.crop_variety_id = False
        return {
            "domain": {
                "crop_variety_id": [
                    ("crop_id", "=", self.crop_name_id.id)
                ]
            }
        }

    @api.onchange("collected_gc")
    def _onchange_collected_gc(self):
        if self.collected_gc:
            if self.collected_gc > fields.Date.today():
                self.collected_gc = False
                return {
                    'warning': {
                        'title': 'Invalid Date',
                        'message': 'Actual Planted Date (GC) cannot be a future date.'
                    }
                }
            cdate = date(
                self.collected_gc.year,
                self.collected_gc.month,
                self.collected_gc.day,
            )
            ethiopian_date = eth_date.to_ethiopian(
                cdate.year, cdate.month, cdate.day
            )
            self.collected_ec = eth_date.convert_tuple_to_string_with_separator(
                ethiopian_date
            )

    @api.onchange("collected_ec")
    def _onchange_collected_ec(self):
        if self.collected_ec:
            eth_date.check_ethipian_date_str(self.collected_ec, future_date=True)
            date_list = re.split("[-/,]", self.collected_ec)
            gc_date = eth_date.to_gregorian(
                int(date_list[2]), int(date_list[1]), int(date_list[0])
            )
            self.collected_gc = gc_date

class G2PWaterResourceLine(models.Model):
    _name = "g2p.water.resource.line"
    _description = "Water Resource Details"
    _rec_name = "water_resource_id"

    crop_registry_id = fields.Many2one('g2p.crop.registry', ondelete="cascade")
    annual_line_id = fields.Many2one('g2p.annual.line', ondelete="cascade")
    perennial_line_id = fields.Many2one('g2p.perennial.line', ondelete="cascade")
    biennial_line_id = fields.Many2one('g2p.biennial.line', ondelete="cascade")
    crop_information_id = fields.Many2one('g2p.crop.information', ondelete="cascade")
    water_resource_id = fields.Many2one('g2p.water.source', string="Water Resource", required=True)
    method_id = fields.Char(string="Method")
    frequency = fields.Char(string="Frequency")

class G2PActualWaterResourceLine(models.Model):
    _name = "g2p.actual.water.resource.line"
    _description = "Actual Water Resource Details"

    crop_registry_id = fields.Many2one('g2p.crop.registry', ondelete="cascade")
    actual_annual_line_id = fields.Many2one('g2p.annual.actual.line', ondelete="cascade")
    annual_line_id = fields.Many2one('g2p.annual.line', ondelete="cascade")
    actual_perennial_line_id = fields.Many2one('g2p.perennial.actual.line', ondelete="cascade")
    actual_biennial_line_id = fields.Many2one('g2p.biennial.actual.line', ondelete="cascade")
    perennial_line_id = fields.Many2one('g2p.perennial.line', ondelete="cascade")
    biennial_line_id = fields.Many2one('g2p.biennial.line', ondelete="cascade")
    water_resource_id = fields.Many2one('g2p.water.source', string="Water Resource", required=True)
    method_id = fields.Char(string="Method")
    frequency = fields.Char(string="Frequency")

class G2PAnnualLine(models.Model):
    _name = "g2p.annual.line"
    _description = "Annual Planned Line"

    crop_registry_id = fields.Many2one("g2p.crop.registry", string="Crop Registry", ondelete="cascade")
    sync_id = fields.Char(string="Sync ID", default=lambda self: str(uuid.uuid4()))
    land_info_id = fields.Many2one('g2p.land.information', string="Land ID")
    region_name_id = fields.Many2one('g2p.region', string='Region')
    zone_name_id = fields.Many2one('g2p.zone', string='Zone')
    woreda_name_id = fields.Many2one('g2p.woreda', string='Woreda')
    kebele_id = fields.Many2one('g2p.kebele', string='Kebele')
    gps = fields.Char(string='GPS Coordinates')

    ownership_type = fields.Selection([('owner', 'Owner'), ('tenant', 'Tenant'), ('crop_share', 'Crop Sharing'), ('family_gift', 'Family Gift')], string="Ownership Type")
    land_area = fields.Float(string="Total Land Area (ha)")
    land_category = fields.Selection([('annual', 'Annual Crop'), ('perennial', 'Perennial Crop'), ('biennial', 'Biennial Crop')], string="Plot Category")
    soil_fertility = fields.Char(string="Soil Fertility")
    season_id = fields.Many2one('g2p.season', string="Season", required=True)
    start_gc = fields.Date(string="Start GC")
    start_month = fields.Integer(string="Start Month", compute="_compute_start_date", store=True)
    start_day = fields.Integer(string="Start Day", compute="_compute_start_date", store=True)
    end_gc = fields.Date(string="End GC")
    end_month = fields.Integer(string="End Month", compute="_compute_end_date", store=True)
    end_day = fields.Integer(string="End Day", compute="_compute_end_date", store=True)
    
    crop_name_id = fields.Many2one("g2p.crop", string="Crop", required=True)
    crop_id_ref = fields.Char(related="crop_name_id.crop_id", string="Crop ID", readonly=True)
    collected_gc = fields.Date(string="Planned Date (GC)")
    collected_ec = fields.Char(string="Planned Date (EC)")
    crop_category_id = fields.Many2one("g2p.crop.category", string="Crop Category", compute="_compute_crop_category", store=True, readonly=True)
    crop_variety_id = fields.Many2one("g2p.crop.variety", string="Crop Variety")

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
                    self.woreda_name_id = self.land_info_id.land_kebele.woreda.id
                    if self.land_info_id.land_kebele.woreda.zone:
                        self.zone_name_id = self.land_info_id.land_kebele.woreda.zone.id
                        if self.land_info_id.land_kebele.woreda.zone.region:
                            self.region_name_id = self.land_info_id.land_kebele.woreda.zone.region.id
                        else:
                            self.region_name_id = False
                    else:
                        self.zone_name_id = False
                        self.region_name_id = False
                else:
                    self.woreda_name_id = False
                    self.zone_name_id = False
                    self.region_name_id = False
            else:
                self.kebele_id = False
                self.woreda_name_id = False
                self.zone_name_id = False
                self.region_name_id = False

            if hasattr(self.land_info_id, 'polygon_data') and self.land_info_id.polygon_data:
                self.gps = self.land_info_id.polygon_data
            else:
                self.gps = False
    
    crop_planned_area = fields.Float(string="Planned Crop Area (ha)")
    crop_growth_duration = fields.Float(string="Average Growth Duration (days)")
    crop_expected = fields.Float(string="Expected Yield (quintals)")
    
    seed_planned = fields.Selection([('local', 'Local'), ('improved', 'Improved')], string="Seed Type")
    seed_planned_qty = fields.Float(string="Planned Seed Quantity (kg)")
    seed_planned_fertilizer_type = fields.Selection([
        ('organic', 'Organic'),
        ('inorganic', 'Inorganic'),
        ('biofertilizer', 'Bio Fertilizer')
    ], string="Planned Fertilizer Type")

    seed_planned_fertilizer_qty = fields.Float(string="Planned Fertilizer Quantity (kg)")
    seed_planned_fertilizer_sack = fields.Float(string="Planned Fertilizer Sacks Count", compute="_compute_planned_fertilizer_sacks", store=True)
    water_resource_line_ids = fields.One2many('g2p.water.resource.line', 'annual_line_id', string="Water Resources")

    # Actual Inputs Fields
    actual_season_id = fields.Many2one('g2p.season', string="Actual Season")
    actual_start_gc = fields.Date(string="Actual Start GC")
    actual_start_month = fields.Integer(string="Actual Start Month")
    actual_start_day = fields.Integer(string="Actual Start Day")
    actual_end_gc = fields.Date(string="Actual End GC")
    actual_end_month = fields.Integer(string="Actual End Month")
    actual_end_day = fields.Integer(string="Actual End Day")
    
    actual_crop_name_id = fields.Many2one("g2p.crop", string="Actual Crop")
    actual_collected_gc = fields.Date(string="Actual Date (GC)")
    actual_collected_ec = fields.Char(string="Actual Date (EC)")
    actual_crop_category_id = fields.Many2one("g2p.crop.category", string="Actual Crop Category", compute="_compute_actual_crop_category", store=True)
    actual_crop_variety_id = fields.Many2one("g2p.crop.variety", string="Actual Crop Variety")

    actual_crop_area = fields.Float(string="Actual Crop Area (ha)")
    actual_growth_duration = fields.Float(string="Actual Growth Duration (days)")
    
    actual_seed_class = fields.Selection([('local', 'Local'), ('improved', 'Improved')], string="Seed Type")
    actual_seed_qty = fields.Float(string="Actual Seed Quantity (kg)")
    actual_fertilizer_type = fields.Selection([
        ('organic', 'Organic'),
        ('inorganic', 'Inorganic'),
        ('biofertilizer', 'Bio Fertilizer')
    ], string="Actual Fertilizer Type")

    actual_fertilizer_qty = fields.Float(string="Actual Fertilizer Quantity (kg)")
    actual_fertilizer_sack = fields.Float(string="Actual Fertilizer Sacks Count", compute="_compute_actual_fertilizer_sacks", store=True)
    
    pest_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Pest Occurrence")
    pest_line_ids = fields.One2many('g2p.crop.pest.line', 'annual_line_id', string="Pest Details")
    
    weed_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Weed Occurrence")
    weed_line_ids = fields.One2many('g2p.crop.weed.line', 'annual_line_id', string="Weed Details")
    
    actual_yield = fields.Float(string="Actual Yield (quintal)")
    cultivated_by = fields.Selection([
        ('tractor', 'Tractor'),
        ('other', 'Other'),
    ], string="Cultivation Type")

    


    planned_labor = fields.Integer(string="Planned Labor")
    has_cluster_farming = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string="Have you done any cluster farming or related activities earlier?")
    cluster_plan = fields.Float(string="Cluster Plan")
    cluster_collected_land = fields.Float(string="Cluster Collected Land")
    cluster_collected_quintal = fields.Float(string="Cluster Collected Quintal")
    cluster_participant_farmers = fields.Integer(string="Cluster Participant Farmers")
    collected_land = fields.Float(string="Collected Land")
    collected_land_quintal = fields.Float(string="Collected Land Quintal")
    collected_by_combiner = fields.Float(string="Collected by Combiner")


    @api.depends('seed_planned_fertilizer_qty')
    def _compute_planned_fertilizer_sacks(self):
        for rec in self:
            if rec.seed_planned_fertilizer_qty:
                rec.seed_planned_fertilizer_sack = rec.seed_planned_fertilizer_qty / 50.0
            else:
                rec.seed_planned_fertilizer_sack = 0.0

    @api.onchange('seed_planned_fertilizer_qty')
    def _onchange_fertilizer_qty(self):
        for rec in self:
            if rec.seed_planned_fertilizer_qty:
                rec.seed_planned_fertilizer_sack = rec.seed_planned_fertilizer_qty / 50.0
            else:
                rec.seed_planned_fertilizer_sack = 0.0

    @api.depends('actual_fertilizer_qty')
    def _compute_actual_fertilizer_sacks(self):
        for rec in self:
            if rec.actual_fertilizer_qty:
                rec.actual_fertilizer_sack = rec.actual_fertilizer_qty / 50.0
            else:
                rec.actual_fertilizer_sack = 0.0

    @api.onchange('crop_planned_area')
    def _onchange_crop_planned_area(self):
        if self.crop_registry_id and self.crop_planned_area and self.land_info_id:
            same_land_lines = self.crop_registry_id.annual_line_ids.filtered(lambda l: l.land_info_id == self.land_info_id)
            total_planned = sum(same_land_lines.mapped('crop_planned_area'))
            max_area = self.land_info_id.total_land_area
            if total_planned > max_area:
                attempted_area = self.crop_planned_area
                allocated_area = total_planned - attempted_area
                remaining_area = max_area - allocated_area
                
                # If they already messed up other lines, don't let it go negative in the message
                if remaining_area < 0:
                    remaining_area = 0.0
                    
                self.crop_planned_area = 0.0
                return {
                    'warning': {
                        'title': "Area Exceeded",
                        'message': "You entered %.2f ha, but only %.2f ha is remaining out of the total %.2f ha (%.2f ha is already allocated to other crops)." % (attempted_area, remaining_area, max_area, allocated_area)
                    }
                }


    @api.onchange('season_id')
    def _onchange_season_id(self):
        if self.season_id:
            self.start_gc = self.season_id.start_gc
            self.end_gc = self.season_id.end_gc
            if self.season_id.start_gc:
                self.start_month = self.season_id.start_gc.month
                self.start_day = self.season_id.start_gc.day
            if self.season_id.end_gc:
                self.end_month = self.season_id.end_gc.month
                self.end_day = self.season_id.end_gc.day

    @api.depends("start_gc")
    def _compute_start_date(self):
        for record in self:
            if record.start_gc:
                record.start_month = record.start_gc.month
                record.start_day = record.start_gc.day
            else:
                record.start_month = record.start_day = 0

    @api.depends("end_gc")
    def _compute_end_date(self):
        for record in self:
            if record.end_gc:
                record.end_month = record.end_gc.month
                record.end_day = record.end_gc.day
            else:
                record.end_month = record.end_day = 0

    @api.depends("crop_name_id")
    def _compute_crop_category(self):
        for rec in self:
            if rec.crop_name_id:
                rec.crop_category_id = rec.crop_name_id.category.id
            else:
                rec.crop_category_id = False

    @api.depends("actual_crop_name_id")
    def _compute_actual_crop_category(self):
        for rec in self:
            if rec.actual_crop_name_id:
                rec.actual_crop_category_id = rec.actual_crop_name_id.category.id
            else:
                rec.actual_crop_category_id = False

    @api.onchange("crop_name_id")
    def _onchange_crop(self):
        self.crop_variety_id = False
        return {
            "domain": {
                "crop_variety_id": [
                    ("crop_id", "=", self.crop_name_id.id)
                ]
            }
        }

    @api.onchange("collected_gc", "start_gc", "end_gc")
    def _onchange_collected_gc(self):
        if self.collected_gc:
            if self.start_gc and self.end_gc:
                # Check if the date is within the season's start and end months/dates
                if self.collected_gc < self.start_gc or self.collected_gc > self.end_gc:
                    self.collected_gc = False
                    self.collected_ec = False
                    return {
                        'warning': {
                            'title': 'Invalid Planned Date',
                            'message': 'Planned Date (GC) must be within the Season Details (Start GC and End GC).'
                        }
                    }

            cdate = date(
                self.collected_gc.year,
                self.collected_gc.month,
                self.collected_gc.day,
            )
            ethiopian_date = eth_date.to_ethiopian(
                cdate.year, cdate.month, cdate.day
            )
            self.collected_ec = eth_date.convert_tuple_to_string_with_separator(
                ethiopian_date
            )

    @api.onchange("collected_ec")
    def _onchange_collected_ec(self):
        if self.collected_ec:
            eth_date.check_ethipian_date_str(self.collected_ec, future_date=True)
            date_list = re.split("[-/,]", self.collected_ec)
            gc_date = eth_date.to_gregorian(
                int(date_list[2]), int(date_list[1]), int(date_list[0])
            )
            self.collected_gc = gc_date




class G2PAnnualActualLine(models.Model):
    _name = "g2p.annual.actual.line"
    _description = "Annual Actual Line"
    @api.constrains('actual_yield')
    def _check_actual_yield(self):
        for rec in self:
            if rec.actual_yield > 0 and rec.crop_registry_id:
                planned_line = rec.crop_registry_id.annual_line_ids.filtered(lambda l: l.sync_id == rec.sync_id)
                if planned_line and rec.actual_yield > planned_line[0].crop_expected:
                    raise ValidationError(f"Actual yield ({rec.actual_yield}) cannot be greater than expected yield ({planned_line[0].crop_expected}).")

    @api.onchange('actual_yield')
    def _onchange_actual_yield(self):
        if self.actual_yield > 0 and self.crop_registry_id:
            planned_line = self.crop_registry_id.annual_line_ids.filtered(lambda l: l.sync_id == self.sync_id)
            if planned_line and self.actual_yield > planned_line[0].crop_expected:
                self.actual_yield = 0.0
                return {
                    'warning': {
                        'title': 'Invalid Yield',
                        'message': f"Actual Yield cannot be greater than Expected Yield ({planned_line[0].crop_expected})."
                    }
                }
    crop_registry_id = fields.Many2one("g2p.crop.registry", string="Crop Registry", ondelete="cascade")
    sync_id = fields.Char(string="Sync ID", default=lambda self: str(uuid.uuid4()))
    is_manual = fields.Boolean(string="Is Manual", default=True)
    is_planning = fields.Boolean(string="Is Planning", default=False)
    land_info_id = fields.Many2one('g2p.land.information', string="Land ID")
    region_name_id = fields.Many2one('g2p.region', string='Region')
    zone_name_id = fields.Many2one('g2p.zone', string='Zone')
    woreda_name_id = fields.Many2one('g2p.woreda', string='Woreda')
    kebele_id = fields.Many2one('g2p.kebele', string='Kebele')
    gps = fields.Char(string='GPS Coordinates')

    ownership_type = fields.Selection([('owner', 'Owner'), ('tenant', 'Tenant'), ('crop_share', 'Crop Sharing'), ('family_gift', 'Family Gift')], string="Ownership Type")
    land_area = fields.Float(string="Total Land Area (ha)")
    land_category = fields.Selection([('annual', 'Annual Crop'), ('perennial', 'Perennial Crop'), ('biennial', 'Biennial Crop')], string="Plot Category")
    soil_fertility = fields.Char(string="Soil Fertility")
    season_id = fields.Many2one('g2p.season', string="Season", required=True)

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
                    self.woreda_name_id = self.land_info_id.land_kebele.woreda.id
                    if self.land_info_id.land_kebele.woreda.zone:
                        self.zone_name_id = self.land_info_id.land_kebele.woreda.zone.id
                        if self.land_info_id.land_kebele.woreda.zone.region:
                            self.region_name_id = self.land_info_id.land_kebele.woreda.zone.region.id
                        else:
                            self.region_name_id = False
                    else:
                        self.zone_name_id = False
                        self.region_name_id = False
                else:
                    self.woreda_name_id = False
                    self.zone_name_id = False
                    self.region_name_id = False
            else:
                self.kebele_id = False
                self.woreda_name_id = False
                self.zone_name_id = False
                self.region_name_id = False

            if hasattr(self.land_info_id, 'polygon_data') and self.land_info_id.polygon_data:
                self.gps = self.land_info_id.polygon_data
            else:
                self.gps = False
                
            if self.crop_registry_id:
                planned_line = self.crop_registry_id.annual_line_ids.filtered(
                    lambda l: l.land_info_id.id == self.land_info_id.id
                )
                if planned_line:
                    planned_line = planned_line[0]
                    water_resources = []
                    for w in planned_line.water_resource_line_ids:
                        water_resources.append((0, 0, {
                            'water_resource_id': w.water_resource_id.id,
                            'method_id': w.method_id,
                            'frequency': w.frequency,
                            'crop_registry_id': self.crop_registry_id.id,
                        }))
                    if water_resources:
                        self.water_resource_line_ids = [(5, 0, 0)] + water_resources
    crop_name_id = fields.Many2one("g2p.crop", string="Crop", required=True)
    crop_id_ref = fields.Char(related="crop_name_id.crop_id", string="Crop ID", readonly=True)
    collected_gc = fields.Date(string="Actual Planted Date (GC)")
    collected_ec = fields.Char(string="Actual Planted Date (EC)")
    crop_category_id = fields.Many2one("g2p.crop.category", string="Crop Category", compute="_compute_crop_category", store=True, readonly=True)
    crop_variety_id = fields.Many2one("g2p.crop.variety", string="Crop Variety")
    remark = fields.Char(string="Remark")
    actual_crop_area = fields.Float(string="Actual Crop Area (ha)")
    actual_growth_duration = fields.Float(string="Actual Growth Duration (days)")
    
    actual_seed_class = fields.Selection([('local', 'Local'), ('improved', 'Improved')], string="Seed Type")
    actual_seed_qty = fields.Float(string="Actual Seed Quantity (kg)")
    actual_fertilizer_type = fields.Selection([
        ('organic', 'Organic'),
        ('inorganic', 'Inorganic'),
        ('biofertilizer', 'Bio Fertilizer')
    ], string="Actual Fertilizer Type")

    actual_fertilizer_qty = fields.Float(string="Actual Fertilizer Quantity (kg)")
    actual_fertilizer_sack = fields.Float(string="Actual Fertilizer Sacks Count", compute="_compute_actual_fertilizer_sacks", store=True)

    has_cluster_farming = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string="Have you done any cluster farming or related activities earlier?")
    actual_cluster_plan = fields.Float(string="Actual Cluster Plan")
    actual_cluster_collected_land = fields.Float(string="Actual Cluster Collected Land")
    actual_cluster_collected_quintal = fields.Float(string="Actual Cluster Collected Quintal")
    actual_cluster_participant_farmers = fields.Integer(string="Actual Cluster Participant Farmers")
    actual_collected_land = fields.Float(string="Actual Collected Land")
    actual_collected_land_quintal = fields.Float(string="Actual Collected Land Quintal")
    actual_collected_by_combiner = fields.Float(string="Actual Collected by Combiner")
    
    pest_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Pest Occurrence")
    pest_line_ids = fields.One2many('g2p.crop.pest.line', 'actual_annual_line_id', string="Pest Details")
    
    weed_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Weed Occurrence")
    weed_line_ids = fields.One2many('g2p.crop.weed.line', 'actual_annual_line_id', string="Weed Details")
    
    actual_yield = fields.Float(string="Actual Yield (quintal)")
    cultivated_by = fields.Selection([
        ('tractor', 'Tractor'),
        ('other', 'Other'),
    ], string="Cultivation Type")
    land_prep_method_ids = fields.Many2many("g2p.land.prep.method", string="Land Prep Methods")
    
    water_resource_line_ids = fields.One2many(
        "g2p.actual.water.resource.line",
        "actual_annual_line_id",
        string="Water Resources",
    )
    
    start_gc = fields.Date(string="Start GC")
    start_month = fields.Integer(string="Start Month", compute="_compute_start_date", store=True)
    start_day = fields.Integer(string="Start Day", compute="_compute_start_date", store=True)
    end_gc = fields.Date(string="End GC")
    end_month = fields.Integer(string="End Month", compute="_compute_end_date", store=True)
    end_day = fields.Integer(string="End Day", compute="_compute_end_date", store=True)
    
    is_mismatch = fields.Boolean(string="Mismatch", compute="_compute_is_mismatch", store=True)

    @api.onchange('actual_crop_area')
    def _onchange_actual_crop_area(self):
        if self.crop_registry_id and self.actual_crop_area and self.land_info_id:
            same_land_lines = self.crop_registry_id.actual_annual_line_ids.filtered(lambda l: l.land_info_id == self.land_info_id)
            total_actual = sum(same_land_lines.mapped('actual_crop_area'))
            max_area = self.land_info_id.total_land_area
            if total_actual > max_area:
                attempted_area = self.actual_crop_area
                allocated_area = total_actual - attempted_area
                remaining_area = max_area - allocated_area
                
                if remaining_area < 0:
                    remaining_area = 0.0
                    
                self.actual_crop_area = 0.0
                return {
                    'warning': {
                        'title': "Area Exceeded",
                        'message': "You entered %.2f ha, but only %.2f ha is remaining out of the total %.2f ha (%.2f ha is already allocated to other actual crops)." % (attempted_area, remaining_area, max_area, allocated_area)
                    }
                }

    @api.depends('actual_fertilizer_qty')
    def _compute_actual_fertilizer_sacks(self):
        for rec in self:
            if rec.actual_fertilizer_qty:
                rec.actual_fertilizer_sack = rec.actual_fertilizer_qty / 50.0
            else:
                rec.actual_fertilizer_sack = 0.0

    @api.onchange('actual_fertilizer_qty')
    def _onchange_fertilizer_qty(self):
        for rec in self:
            if rec.actual_fertilizer_qty:
                rec.actual_fertilizer_sack = rec.actual_fertilizer_qty / 50.0
            else:
                rec.actual_fertilizer_sack = 0.0

    @api.onchange('season_id')
    def _onchange_season_id(self):
        if self.season_id:
            self.start_gc = self.season_id.start_gc
            self.end_gc = self.season_id.end_gc
            if self.season_id.start_gc:
                self.start_month = self.season_id.start_gc.month
                self.start_day = self.season_id.start_gc.day
            if self.season_id.end_gc:
                self.end_month = self.season_id.end_gc.month
                self.end_day = self.season_id.end_gc.day
            # Clear the actual planted date so user enters fresh date for new season
            self.collected_gc = False
            self.collected_ec = False

    @api.depends("start_gc")
    def _compute_start_date(self):
        for record in self:
            if record.start_gc:
                record.start_month = record.start_gc.month
                record.start_day = record.start_gc.day
            else:
                record.start_month = record.start_day = 0

    @api.depends("end_gc")
    def _compute_end_date(self):
        for record in self:
            if record.end_gc:
                record.end_month = record.end_gc.month
                record.end_day = record.end_gc.day
            else:
                record.end_month = record.end_day = 0

    @api.depends("crop_name_id")
    def _compute_crop_category(self):
        for rec in self:
            if rec.crop_name_id:
                rec.crop_category_id = rec.crop_name_id.category.id
            else:
                rec.crop_category_id = False

    @api.depends("crop_name_id", "crop_variety_id", "collected_gc", "season_id",
                 "crop_registry_id.annual_line_ids",
                 "crop_registry_id.annual_line_ids.crop_name_id",
                 "crop_registry_id.annual_line_ids.crop_variety_id",
                 "crop_registry_id.annual_line_ids.collected_gc",
                 "crop_registry_id.annual_line_ids.season_id")
    def _compute_is_mismatch(self):
        for rec in self:
            if not rec.crop_registry_id or not rec.crop_name_id:
                rec.is_mismatch = False
                continue
            planned_lines = rec.crop_registry_id.annual_line_ids
            matched = False
            for planned in planned_lines:
                if (planned.crop_name_id.id == rec.crop_name_id.id
                        and planned.crop_variety_id.id == rec.crop_variety_id.id
                        and planned.season_id.id == rec.season_id.id
                        and planned.collected_gc == rec.collected_gc):
                    matched = True
                    break
            rec.is_mismatch = not matched

    @api.depends("crop_name_id")
    def _compute_crop_category(self):
        for rec in self:
            rec.crop_category_id = (
                rec.crop_name_id.category.id
                if rec.crop_name_id
                else False
            )

    @api.onchange("crop_name_id")
    def _onchange_crop(self):
        self.crop_variety_id = False
        return {
            "domain": {
                "crop_variety_id": [
                    ("crop_id", "=", self.crop_name_id.id)
                ]
            }
        }

    @api.onchange("collected_gc")
    def _onchange_collected_gc(self):
        if self.collected_gc:
            if self.collected_gc > fields.Date.today():
                self.collected_gc = False
                return {
                    'warning': {
                        'title': 'Invalid Date',
                        'message': 'Actual Planted Date (GC) cannot be a future date.'
                    }
                }
            cdate = date(
                self.collected_gc.year,
                self.collected_gc.month,
                self.collected_gc.day,
            )
            ethiopian_date = eth_date.to_ethiopian(
                cdate.year, cdate.month, cdate.day
            )
            self.collected_ec = eth_date.convert_tuple_to_string_with_separator(
                ethiopian_date
            )

    @api.onchange("collected_ec")
    def _onchange_collected_ec(self):
        if self.collected_ec:
            eth_date.check_ethipian_date_str(self.collected_ec, future_date=True)
            date_list = re.split("[-/,]", self.collected_ec)
            gc_date = eth_date.to_gregorian(
                int(date_list[2]), int(date_list[1]), int(date_list[0])
            )
            self.collected_gc = gc_date

class G2PPest(models.Model):
    _name = "g2p.pest"
    _description = "Pest Name"
    name = fields.Char("Name", required=True)
    code = fields.Char("Code")
    pest_type = fields.Selection([
        ('insect_pests', 'Insect Pests'),
        ('rodent_pests', 'Rodent Pests'),
        ('molluscan_pests', 'Molluscan Pests'),
        ('disease_pests', 'Disease-causing Pests'),
    ], string="Pest Type")

class G2PPesticide(models.Model):
    _name = "g2p.pesticide"
    _description = "Pesticide Name"
    name = fields.Char("Name", required=True)
    code = fields.Char("Code")
    pesticide_type = fields.Selection([
        ('insecticide', 'Insecticide'),
        ('fungicide', 'Fungicide'),
        ('herbicide', 'Herbicide'),
        ('rodenticide', 'Rodenticide'),
        ('bactericide', 'Bactericide'),
        ('nematicide', 'Nematicide'),
        ('acaricide', 'Acaricide / Miticide'),
        ('molluscicide', 'Molluscicide'),
        ('termiticide', 'Termiticide'),
        ('avicide', 'Avicide'),
        ('piscicide', 'Piscicide'),
        ('algicide', 'Algicide'),
        ('virucide', 'Virucide'),
    ], string="Type")

class G2PCropPestLine(models.Model):
    _name = "g2p.crop.pest.line"
    _description = "Crop Pest Details"

    crop_registry_id = fields.Many2one('g2p.crop.registry', string="Crop Registry", ondelete="cascade")
    actual_annual_line_id = fields.Many2one("g2p.annual.actual.line", ondelete="cascade")
    annual_line_id = fields.Many2one('g2p.annual.line', ondelete="cascade")
    actual_perennial_line_id = fields.Many2one("g2p.perennial.actual.line", ondelete="cascade")
    actual_biennial_line_id = fields.Many2one("g2p.biennial.actual.line", ondelete="cascade")
    perennial_line_id = fields.Many2one('g2p.perennial.line', ondelete="cascade")
    biennial_line_id = fields.Many2one('g2p.biennial.line', ondelete="cascade")
    
    pest_type = fields.Selection([
        ('insect_pests', 'Insect Pests'),
        ('rodent_pests', 'Rodent Pests'),
        ('molluscan_pests', 'Molluscan Pests'),
        ('disease_pests', 'Disease-causing Pests'),
    ], string="Pest Type")
    pest_name_id = fields.Many2one('g2p.pest', string="Pest Name", domain="[('pest_type', '=', pest_type)]")
    
    pesticides_type = fields.Selection([
        ('insecticide', 'Insecticide'),
        ('fungicide', 'Fungicide'),
        ('herbicide', 'Herbicide'),
        ('rodenticide', 'Rodenticide'),
        ('bactericide', 'Bactericide'),
        ('nematicide', 'Nematicide'),
        ('acaricide', 'Acaricide / Miticide'),
        ('molluscicide', 'Molluscicide'),
        ('termiticide', 'Termiticide'),
        ('avicide', 'Avicide'),
        ('piscicide', 'Piscicide'),
        ('algicide', 'Algicide'),
        ('virucide', 'Virucide'),
    ], string="Pesticides Type")
    pesticide_name_id = fields.Many2one('g2p.pesticide', string="Pesticide Name", domain="[('pesticide_type', '=', pesticides_type)]")
    pesticide_method = fields.Char(string="Method of Control")
    pesticide_frequency = fields.Char(string="Frequency of Application")

class G2PWeed(models.Model):
    _name = "g2p.weed"
    _description = "Weed Name"
    name = fields.Char("Name", required=True)
    code = fields.Char("Code")
    weed_type = fields.Selection([
        ('by_life_cycle', 'By Life Cycle'),
        ('by_season', 'By Season'),
        ('by_botanical_nature', 'By Botanical Nature'),
        ('by_habitat', 'By Habitat'),
        ('by_harmfulness', 'By Harmfulness'),
        ('by_morphology', 'By Morphology'),
    ], string="Weed Type")

class G2PCropWeedLine(models.Model):
    _name = "g2p.crop.weed.line"
    _description = "Crop Weed Details"

    crop_registry_id = fields.Many2one('g2p.crop.registry', string="Crop Registry", ondelete="cascade")
    actual_annual_line_id = fields.Many2one("g2p.annual.actual.line", ondelete="cascade")
    annual_line_id = fields.Many2one('g2p.annual.line', ondelete="cascade")
    actual_perennial_line_id = fields.Many2one("g2p.perennial.actual.line", ondelete="cascade")
    actual_biennial_line_id = fields.Many2one("g2p.biennial.actual.line", ondelete="cascade")
    perennial_line_id = fields.Many2one('g2p.perennial.line', ondelete="cascade")
    biennial_line_id = fields.Many2one('g2p.biennial.line', ondelete="cascade")
    
    weed_type = fields.Selection([
        ('by_life_cycle', 'By Life Cycle'),
        ('by_season', 'By Season'),
        ('by_botanical_nature', 'By Botanical Nature'),
        ('by_habitat', 'By Habitat'),
        ('by_harmfulness', 'By Harmfulness'),
        ('by_morphology', 'By Morphology'),
    ], string="Weed Type")
    weed_name_id = fields.Many2one('g2p.weed', string="Weed Name", domain="[('weed_type', '=', weed_type)]")
    
    weedicide_type = fields.Selection([
        ('pre_emergent', 'Pre-emergent Herbicide'),
        ('post_emergent', 'Post-emergent Herbicide'),
        ('systemic', 'Systemic Herbicide'),
        ('contact', 'Contact Herbicide'),
        ('graminicide', 'Graminicide'),
        ('broadleaf', 'Broadleaf Herbicide'),
        ('sedge', 'Sedge Herbicide'),
        ('aquatic', 'Aquatic Herbicide'),
        ('foliar', 'Foliar Herbicide'),
        ('soil', 'Soil Herbicide'),
    ], string="Weedicides Type")
    weedicide_name_id = fields.Many2one('g2p.weedicide', string="Weedicides Name", domain="[('weedicide_type', '=', weedicide_type)]")
    pesticide_method = fields.Char(string="Method of Control")
    pesticide_frequency = fields.Char(string="Frequency of Application")

class G2PWeedicide(models.Model):
    _name = "g2p.weedicide"
    _description = "Weedicide Name"
    name = fields.Char("Name", required=True)
    code = fields.Char("Code")
    weedicide_type = fields.Selection([
        ('pre_emergent', 'Pre-emergent Herbicide'),
        ('post_emergent', 'Post-emergent Herbicide'),
        ('systemic', 'Systemic Herbicide'),
        ('contact', 'Contact Herbicide'),
        ('graminicide', 'Graminicide'),
        ('broadleaf', 'Broadleaf Herbicide'),
        ('sedge', 'Sedge Herbicide'),
        ('aquatic', 'Aquatic Herbicide'),
        ('foliar', 'Foliar Herbicide'),
        ('soil', 'Soil Herbicide'),
    ], string="Type")





class G2PBiennialLine(models.Model):
    _name = "g2p.biennial.line"
    _description = "Biennial Crop Planned Line"

    crop_registry_id = fields.Many2one("g2p.crop.registry", string="Crop Registry", ondelete="cascade")
    sync_id = fields.Char(string="Sync ID", default=lambda self: str(uuid.uuid4()))
    land_info_id = fields.Many2one('g2p.land.information', string="Land ID")
    region_name_id = fields.Many2one('g2p.region', string='Region')
    zone_name_id = fields.Many2one('g2p.zone', string='Zone')
    woreda_name_id = fields.Many2one('g2p.woreda', string='Woreda')
    kebele_id = fields.Many2one('g2p.kebele', string='Kebele')
    gps = fields.Char(string='GPS Coordinates')

    ownership_type = fields.Selection([('owner', 'Owner'), ('tenant', 'Tenant'), ('crop_share', 'Crop Sharing'), ('family_gift', 'Family Gift')], string="Ownership Type")
    land_area = fields.Float(string="Total Land Area (ha)")
    land_category = fields.Selection([('annual', 'Annual Crop'), ('biennial', 'Biennial Crop'), ('biennial', 'Biennial Crop')], string="Plot Category")
    soil_fertility = fields.Char(string="Soil Fertility")
    season_id = fields.Many2one('g2p.season', string="Season", required=True)
    start_gc = fields.Date(string="Start GC")
    start_month = fields.Integer(string="Start Month", compute="_compute_start_date", store=True)
    start_day = fields.Integer(string="Start Day", compute="_compute_start_date", store=True)
    end_gc = fields.Date(string="End GC")
    end_month = fields.Integer(string="End Month", compute="_compute_end_date", store=True)
    end_day = fields.Integer(string="End Day", compute="_compute_end_date", store=True)
    
    crop_name_id = fields.Many2one("g2p.crop", string="Crop", required=True)
    crop_id_ref = fields.Char(related="crop_name_id.crop_id", string="Crop ID", readonly=True)
    collected_gc = fields.Date(string="Planned Date (GC)")
    collected_ec = fields.Char(string="Planned Date (EC)")
    crop_category_id = fields.Many2one("g2p.crop.category", string="Crop Category", compute="_compute_crop_category", store=True, readonly=True)
    crop_variety_id = fields.Many2one("g2p.crop.variety", string="Crop Variety")
    
    crop_planned_area = fields.Float(string="Planned Crop Area (ha)")

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
                    self.woreda_name_id = self.land_info_id.land_kebele.woreda.id
                    if self.land_info_id.land_kebele.woreda.zone:
                        self.zone_name_id = self.land_info_id.land_kebele.woreda.zone.id
                        if self.land_info_id.land_kebele.woreda.zone.region:
                            self.region_name_id = self.land_info_id.land_kebele.woreda.zone.region.id
                        else:
                            self.region_name_id = False
                    else:
                        self.zone_name_id = False
                        self.region_name_id = False
                else:
                    self.woreda_name_id = False
                    self.zone_name_id = False
                    self.region_name_id = False
            else:
                self.kebele_id = False
                self.woreda_name_id = False
                self.zone_name_id = False
                self.region_name_id = False

            if hasattr(self.land_info_id, 'polygon_data') and self.land_info_id.polygon_data:
                self.gps = self.land_info_id.polygon_data
            else:
                self.gps = False
    crop_growth_duration = fields.Float(string="Average Growth Duration (days)")
    crop_expected = fields.Float(string="Expected Yield (quintals)")
    
    seed_planned = fields.Selection([('local', 'Local'), ('improved', 'Improved')], string="Seed Type")
    seed_planned_qty = fields.Float(string="Planned Seed Quantity (kg)")
    seed_planned_fertilizer_type = fields.Selection([
        ('organic', 'Organic'),
        ('inorganic', 'Inorganic'),
        ('biofertilizer', 'Bio Fertilizer')
    ], string="Planned Fertilizer Type")

    seed_planned_fertilizer_qty = fields.Float(string="Planned Fertilizer Quantity (kg)")
    seed_planned_fertilizer_sack = fields.Float(string="Planned Fertilizer Sacks Count", compute="_compute_planned_fertilizer_sacks", store=True)
    water_resource_line_ids = fields.One2many('g2p.water.resource.line', 'biennial_line_id', string="Water Resources")
    
    # Actual Inputs Fields
    actual_season_id = fields.Many2one('g2p.season', string="Actual Season")
    actual_start_gc = fields.Date(string="Actual Start GC")
    actual_start_month = fields.Integer(string="Actual Start Month")
    actual_start_day = fields.Integer(string="Actual Start Day")
    actual_end_gc = fields.Date(string="Actual End GC")
    actual_end_month = fields.Integer(string="Actual End Month")
    actual_end_day = fields.Integer(string="Actual End Day")
    
    actual_crop_name_id = fields.Many2one("g2p.crop", string="Actual Crop")
    actual_collected_gc = fields.Date(string="Actual Date (GC)")
    actual_collected_ec = fields.Char(string="Actual Date (EC)")
    actual_crop_category_id = fields.Many2one("g2p.crop.category", string="Actual Crop Category", compute="_compute_actual_crop_category", store=True)
    actual_crop_variety_id = fields.Many2one("g2p.crop.variety", string="Actual Crop Variety")

    actual_crop_area = fields.Float(string="Actual Crop Area (ha)")
    actual_growth_duration = fields.Float(string="Actual Growth Duration (days)")
    
    actual_seed_class = fields.Selection([('local', 'Local'), ('improved', 'Improved')], string="Seed Type")
    actual_seed_qty = fields.Float(string="Actual Seed Quantity (kg)")
    actual_fertilizer_type = fields.Selection([
        ('organic', 'Organic'),
        ('inorganic', 'Inorganic'),
        ('biofertilizer', 'Bio Fertilizer')
    ], string="Actual Fertilizer Type")

    actual_fertilizer_qty = fields.Float(string="Actual Fertilizer Quantity (kg)")
    actual_fertilizer_sack = fields.Float(string="Actual Fertilizer Sacks Count", compute="_compute_actual_fertilizer_sacks", store=True)
    
    pest_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Pest Occurrence")
    pest_line_ids = fields.One2many('g2p.crop.pest.line', 'biennial_line_id', string="Pest Details")
    
    weed_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Weed Occurrence")
    weed_line_ids = fields.One2many('g2p.crop.weed.line', 'biennial_line_id', string="Weed Details")
    
    actual_yield = fields.Float(string="Actual Yield (quintal)")
    cultivated_by = fields.Selection([
        ('tractor', 'Tractor'),
        ('other', 'Other'),
    ], string="Cultivation Type")

    

    
    planned_labor = fields.Integer(string="Planned Labor")
    has_cluster_farming = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string="Have you done any cluster farming or related activities earlier?")
    cluster_plan = fields.Float(string="Cluster Plan")
    cluster_collected_land = fields.Float(string="Cluster Collected Land")
    cluster_collected_quintal = fields.Float(string="Cluster Collected Quintal")
    cluster_participant_farmers = fields.Integer(string="Cluster Participant Farmers")
    collected_land = fields.Float(string="Collected Land")
    collected_land_quintal = fields.Float(string="Collected Land Quintal")
    collected_by_combiner = fields.Float(string="Collected by Combiner")


    @api.depends('seed_planned_fertilizer_qty')
    def _compute_planned_fertilizer_sacks(self):
        for rec in self:
            if rec.seed_planned_fertilizer_qty:
                rec.seed_planned_fertilizer_sack = rec.seed_planned_fertilizer_qty / 50.0
            else:
                rec.seed_planned_fertilizer_sack = 0.0

    @api.onchange('seed_planned_fertilizer_qty')
    def _onchange_fertilizer_qty(self):
        for rec in self:
            if rec.seed_planned_fertilizer_qty:
                rec.seed_planned_fertilizer_sack = rec.seed_planned_fertilizer_qty / 50.0
            else:
                rec.seed_planned_fertilizer_sack = 0.0

    @api.depends('actual_fertilizer_qty')
    def _compute_actual_fertilizer_sacks(self):
        for rec in self:
            if rec.actual_fertilizer_qty:
                rec.actual_fertilizer_sack = rec.actual_fertilizer_qty / 50.0
            else:
                rec.actual_fertilizer_sack = 0.0

    @api.onchange('crop_planned_area')
    def _onchange_crop_planned_area(self):
        if self.crop_registry_id and self.crop_planned_area and self.land_info_id:
            same_land_lines = self.crop_registry_id.biennial_line_ids.filtered(lambda l: l.land_info_id == self.land_info_id)
            total_planned = sum(same_land_lines.mapped('crop_planned_area'))
            max_area = self.land_info_id.total_land_area
            if total_planned > max_area:
                attempted_area = self.crop_planned_area
                allocated_area = total_planned - attempted_area
                remaining_area = max_area - allocated_area
                
                # If they already messed up other lines, don't let it go negative in the message
                if remaining_area < 0:
                    remaining_area = 0.0
                    
                self.crop_planned_area = 0.0
                return {
                    'warning': {
                        'title': "Area Exceeded",
                        'message': "You entered %.2f ha, but only %.2f ha is remaining out of the total %.2f ha (%.2f ha is already allocated to other crops)." % (attempted_area, remaining_area, max_area, allocated_area)
                    }
                }


    @api.onchange('season_id')
    def _onchange_season_id(self):
        if self.season_id:
            self.start_gc = self.season_id.start_gc
            self.end_gc = self.season_id.end_gc

    @api.depends("start_gc")
    def _compute_start_date(self):
        for record in self:
            if record.start_gc:
                record.start_month = record.start_gc.month
                record.start_day = record.start_gc.day
            else:
                record.start_month = record.start_day = 0

    @api.depends("end_gc")
    def _compute_end_date(self):
        for record in self:
            if record.end_gc:
                record.end_month = record.end_gc.month
                record.end_day = record.end_gc.day
            else:
                record.end_month = record.end_day = 0

    @api.depends("crop_name_id")
    def _compute_crop_category(self):
        for rec in self:
            if rec.crop_name_id:
                rec.crop_category_id = rec.crop_name_id.category.id
            else:
                rec.crop_category_id = False

    @api.depends("actual_crop_name_id")
    def _compute_actual_crop_category(self):
        for rec in self:
            if rec.actual_crop_name_id:
                rec.actual_crop_category_id = rec.actual_crop_name_id.category.id
            else:
                rec.actual_crop_category_id = False

    @api.onchange("crop_name_id")
    def _onchange_crop(self):
        self.crop_variety_id = False
        return {
            "domain": {
                "crop_variety_id": [
                    ("crop_id", "=", self.crop_name_id.id)
                ]
            }
        }

    @api.onchange("collected_gc", "start_gc", "end_gc")
    def _onchange_collected_gc(self):
        if self.collected_gc:
            if self.start_gc and self.end_gc:
                # Check if the date is within the season's start and end months/dates
                if self.collected_gc < self.start_gc or self.collected_gc > self.end_gc:
                    self.collected_gc = False
                    self.collected_ec = False
                    return {
                        'warning': {
                            'title': 'Invalid Planned Date',
                            'message': 'Planned Date (GC) must be within the Season Details (Start GC and End GC).'
                        }
                    }

            cdate = date(
                self.collected_gc.year,
                self.collected_gc.month,
                self.collected_gc.day,
            )
            ethiopian_date = eth_date.to_ethiopian(
                cdate.year, cdate.month, cdate.day
            )
            self.collected_ec = eth_date.convert_tuple_to_string_with_separator(
                ethiopian_date
            )

    @api.onchange("collected_ec")
    def _onchange_collected_ec(self):
        if self.collected_ec:
            eth_date.check_ethipian_date_str(self.collected_ec, future_date=True)
            date_list = re.split("[-/,]", self.collected_ec)
            gc_date = eth_date.to_gregorian(
                int(date_list[2]), int(date_list[1]), int(date_list[0])
            )
            self.collected_gc = gc_date




class G2PBiennialActualLine(models.Model):
    _name = "g2p.biennial.actual.line"
    _description = "Biennial Crop Actual Line"
    @api.constrains('actual_yield')
    def _check_actual_yield(self):
        for rec in self:
            if rec.actual_yield > 0 and rec.crop_registry_id:
                planned_line = rec.crop_registry_id.biennial_line_ids.filtered(lambda l: l.sync_id == rec.sync_id)
                if planned_line and rec.actual_yield > planned_line[0].crop_expected:
                    raise ValidationError(f"Actual yield ({rec.actual_yield}) cannot be greater than expected yield ({planned_line[0].crop_expected}).")

    @api.onchange('actual_yield')
    def _onchange_actual_yield(self):
        if self.actual_yield > 0 and self.crop_registry_id:
            planned_line = self.crop_registry_id.biennial_line_ids.filtered(lambda l: l.sync_id == self.sync_id)
            if planned_line and self.actual_yield > planned_line[0].crop_expected:
                self.actual_yield = 0.0
                return {
                    'warning': {
                        'title': 'Invalid Yield',
                        'message': f"Actual Yield cannot be greater than Expected Yield ({planned_line[0].crop_expected})."
                    }
                }

    crop_registry_id = fields.Many2one("g2p.crop.registry", string="Crop Registry", ondelete="cascade")
    sync_id = fields.Char(string="Sync ID", default=lambda self: str(uuid.uuid4()))
    is_manual = fields.Boolean(string="Is Manual", default=True)
    is_planning = fields.Boolean(string="Is Planning", default=False)
    land_info_id = fields.Many2one('g2p.land.information', string="Land ID")
    region_name_id = fields.Many2one('g2p.region', string='Region')
    zone_name_id = fields.Many2one('g2p.zone', string='Zone')
    woreda_name_id = fields.Many2one('g2p.woreda', string='Woreda')
    kebele_id = fields.Many2one('g2p.kebele', string='Kebele')
    gps = fields.Char(string='GPS Coordinates')

    ownership_type = fields.Selection([('owner', 'Owner'), ('tenant', 'Tenant'), ('crop_share', 'Crop Sharing'), ('family_gift', 'Family Gift')], string="Ownership Type")
    land_area = fields.Float(string="Total Land Area (ha)")
    land_category = fields.Selection([('annual', 'Annual Crop'), ('biennial', 'Biennial Crop'), ('biennial', 'Biennial Crop')], string="Plot Category")
    soil_fertility = fields.Char(string="Soil Fertility")

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
                    self.woreda_name_id = self.land_info_id.land_kebele.woreda.id
                    if self.land_info_id.land_kebele.woreda.zone:
                        self.zone_name_id = self.land_info_id.land_kebele.woreda.zone.id
                        if self.land_info_id.land_kebele.woreda.zone.region:
                            self.region_name_id = self.land_info_id.land_kebele.woreda.zone.region.id
                        else:
                            self.region_name_id = False
                    else:
                        self.zone_name_id = False
                        self.region_name_id = False
                else:
                    self.woreda_name_id = False
                    self.zone_name_id = False
                    self.region_name_id = False
            else:
                self.kebele_id = False
                self.woreda_name_id = False
                self.zone_name_id = False
                self.region_name_id = False

            if hasattr(self.land_info_id, 'polygon_data') and self.land_info_id.polygon_data:
                self.gps = self.land_info_id.polygon_data
            else:
                self.gps = False
                
            if self.crop_registry_id:
                planned_line = self.crop_registry_id.biennial_line_ids.filtered(
                    lambda l: l.land_info_id.id == self.land_info_id.id
                )
                if planned_line:
                    planned_line = planned_line[0]
                    water_resources = []
                    for w in planned_line.water_resource_line_ids:
                        water_resources.append((0, 0, {
                            'water_resource_id': w.water_resource_id.id,
                            'method_id': w.method_id,
                            'frequency': w.frequency,
                            'crop_registry_id': self.crop_registry_id.id,
                        }))
                    if water_resources:
                        self.water_resource_line_ids = [(5, 0, 0)] + water_resources
    season_id = fields.Many2one('g2p.season', string="Season", required=True)
    crop_name_id = fields.Many2one("g2p.crop", string="Crop", required=True)
    crop_id_ref = fields.Char(related="crop_name_id.crop_id", string="Crop ID", readonly=True)
    collected_gc = fields.Date(string="Actual Planted Date (GC)")
    collected_ec = fields.Char(string="Actual Planted Date (EC)")
    crop_category_id = fields.Many2one("g2p.crop.category", string="Crop Category", compute="_compute_crop_category", store=True, readonly=True)
    crop_variety_id = fields.Many2one("g2p.crop.variety", string="Crop Variety")
    remark = fields.Char(string="Remark")
    actual_crop_area = fields.Float(string="Actual Crop Area (ha)")
    actual_growth_duration = fields.Float(string="Actual Growth Duration (days)")
    
    actual_seed_class = fields.Selection([('local', 'Local'), ('improved', 'Improved')], string="Seed Type")
    actual_seed_qty = fields.Float(string="Actual Seed Quantity (kg)")
    actual_fertilizer_type = fields.Selection([
        ('organic', 'Organic'),
        ('inorganic', 'Inorganic'),
        ('biofertilizer', 'Bio Fertilizer')
    ], string="Actual Fertilizer Type")

    actual_fertilizer_qty = fields.Float(string="Actual Fertilizer Quantity (kg)")
    actual_fertilizer_sack = fields.Float(string="Actual Fertilizer Sacks Count", compute="_compute_actual_fertilizer_sacks", store=True)

    has_cluster_farming = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string="Have you done any cluster farming or related activities earlier?")
    actual_cluster_plan = fields.Float(string="Actual Cluster Plan")
    actual_cluster_collected_land = fields.Float(string="Actual Cluster Collected Land")
    actual_cluster_collected_quintal = fields.Float(string="Actual Cluster Collected Quintal")
    actual_cluster_participant_farmers = fields.Integer(string="Actual Cluster Participant Farmers")
    actual_collected_land = fields.Float(string="Actual Collected Land")
    actual_collected_land_quintal = fields.Float(string="Actual Collected Land Quintal")
    actual_collected_by_combiner = fields.Float(string="Actual Collected by Combiner")
    
    pest_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Pest Occurrence")
    pest_line_ids = fields.One2many('g2p.crop.pest.line', 'actual_biennial_line_id', string="Pest Details")
    
    weed_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Weed Occurrence")
    weed_line_ids = fields.One2many('g2p.crop.weed.line', 'actual_biennial_line_id', string="Weed Details")
    
    actual_yield = fields.Float(string="Actual Yield (quintal)")
    cultivated_by = fields.Selection([
        ('tractor', 'Tractor'),
        ('other', 'Other'),
    ], string="Cultivation Type")
    land_prep_method_ids = fields.Many2many("g2p.land.prep.method", string="Land Prep Methods")
    
    water_resource_line_ids = fields.One2many(
        "g2p.actual.water.resource.line",
        "actual_biennial_line_id",
        string="Water Resources",
    )
    
    start_gc = fields.Date(string="Start GC")
    start_month = fields.Integer(string="Start Month", compute="_compute_start_date", store=True)
    start_day = fields.Integer(string="Start Day", compute="_compute_start_date", store=True)
    end_gc = fields.Date(string="End GC")
    end_month = fields.Integer(string="End Month", compute="_compute_end_date", store=True)
    end_day = fields.Integer(string="End Day", compute="_compute_end_date", store=True)
    
    is_mismatch = fields.Boolean(string="Mismatch", compute="_compute_is_mismatch", store=True)

    @api.onchange('actual_crop_area')
    def _onchange_actual_crop_area(self):
        if self.crop_registry_id and self.actual_crop_area and self.land_info_id:
            same_land_lines = self.crop_registry_id.actual_biennial_line_ids.filtered(lambda l: l.land_info_id == self.land_info_id)
            total_actual = sum(same_land_lines.mapped('actual_crop_area'))
            max_area = self.land_info_id.total_land_area
            if total_actual > max_area:
                attempted_area = self.actual_crop_area
                allocated_area = total_actual - attempted_area
                remaining_area = max_area - allocated_area
                
                if remaining_area < 0:
                    remaining_area = 0.0
                    
                self.actual_crop_area = 0.0
                return {
                    'warning': {
                        'title': "Area Exceeded",
                        'message': "You entered %.2f ha, but only %.2f ha is remaining out of the total %.2f ha (%.2f ha is already allocated to other actual crops)." % (attempted_area, remaining_area, max_area, allocated_area)
                    }
                }

    @api.depends('actual_fertilizer_qty')
    def _compute_actual_fertilizer_sacks(self):
        for rec in self:
            if rec.actual_fertilizer_qty:
                rec.actual_fertilizer_sack = rec.actual_fertilizer_qty / 50.0
            else:
                rec.actual_fertilizer_sack = 0.0

    @api.onchange('actual_fertilizer_qty')
    def _onchange_fertilizer_qty(self):
        for rec in self:
            if rec.actual_fertilizer_qty:
                rec.actual_fertilizer_sack = rec.actual_fertilizer_qty / 50.0
            else:
                rec.actual_fertilizer_sack = 0.0

    @api.onchange('season_id')
    def _onchange_season_id(self):
        if self.season_id:
            self.start_gc = self.season_id.start_gc
            self.end_gc = self.season_id.end_gc
            if self.season_id.start_gc:
                self.start_month = self.season_id.start_gc.month
                self.start_day = self.season_id.start_gc.day
            if self.season_id.end_gc:
                self.end_month = self.season_id.end_gc.month
                self.end_day = self.season_id.end_gc.day

    @api.depends("start_gc")
    def _compute_start_date(self):
        for record in self:
            if record.start_gc:
                record.start_month = record.start_gc.month
                record.start_day = record.start_gc.day
            else:
                record.start_month = record.start_day = 0

    @api.depends("end_gc")
    def _compute_end_date(self):
        for record in self:
            if record.end_gc:
                record.end_month = record.end_gc.month
                record.end_day = record.end_gc.day
            else:
                record.end_month = record.end_day = 0

    @api.depends("crop_name_id")
    def _compute_crop_category(self):
        for rec in self:
            if rec.crop_name_id:
                rec.crop_category_id = rec.crop_name_id.category.id
            else:
                rec.crop_category_id = False

    @api.depends("crop_name_id", "crop_variety_id", "collected_gc", "season_id",
                 "crop_registry_id.biennial_line_ids",
                 "crop_registry_id.biennial_line_ids.crop_name_id",
                 "crop_registry_id.biennial_line_ids.crop_variety_id",
                 "crop_registry_id.biennial_line_ids.collected_gc",
                 "crop_registry_id.biennial_line_ids.season_id")
    def _compute_is_mismatch(self):
        for rec in self:
            if not rec.crop_registry_id or not rec.crop_name_id:
                rec.is_mismatch = False
                continue
            planned_lines = rec.crop_registry_id.biennial_line_ids
            matched = False
            for planned in planned_lines:
                if (planned.crop_name_id.id == rec.crop_name_id.id
                        and planned.crop_variety_id.id == rec.crop_variety_id.id
                        and planned.season_id.id == rec.season_id.id
                        and planned.collected_gc == rec.collected_gc):
                    matched = True
                    break
            rec.is_mismatch = not matched

    @api.depends("crop_name_id")
    def _compute_crop_category(self):
        for rec in self:
            rec.crop_category_id = (
                rec.crop_name_id.category.id
                if rec.crop_name_id
                else False
            )

    @api.onchange("crop_name_id")
    def _onchange_crop(self):
        self.crop_variety_id = False
        return {
            "domain": {
                "crop_variety_id": [
                    ("crop_id", "=", self.crop_name_id.id)
                ]
            }
        }

    @api.onchange("collected_gc")
    def _onchange_collected_gc(self):
        if self.collected_gc:
            if self.collected_gc > fields.Date.today():
                self.collected_gc = False
                return {
                    'warning': {
                        'title': 'Invalid Date',
                        'message': 'Actual Planted Date (GC) cannot be a future date.'
                    }
                }
            cdate = date(
                self.collected_gc.year,
                self.collected_gc.month,
                self.collected_gc.day,
            )
            ethiopian_date = eth_date.to_ethiopian(
                cdate.year, cdate.month, cdate.day
            )
            self.collected_ec = eth_date.convert_tuple_to_string_with_separator(
                ethiopian_date
            )

    @api.onchange("collected_ec")
    def _onchange_collected_ec(self):
        if self.collected_ec:
            eth_date.check_ethipian_date_str(self.collected_ec, future_date=True)
            date_list = re.split("[-/,]", self.collected_ec)
            gc_date = eth_date.to_gregorian(
                int(date_list[2]), int(date_list[1]), int(date_list[0])
            )
            self.collected_gc = gc_date


class G2PCropInformationInherit(models.Model):
    _inherit = 'g2p.crop.information'

    water_resource_line_ids = fields.One2many('g2p.water.resource.line', 'crop_information_id', string="Water Resources")
