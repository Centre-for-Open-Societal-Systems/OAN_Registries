import logging
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.g2p_ati.models.utils import eth_date
import re

_logger = logging.getLogger(__name__)

class G2PClusterStatus(models.Model):
    _name = "g2p.cluster.status"
    _description = "Cluster Status"

    name = fields.Char(string="Status Name", required=True)

class G2PInfestationType(models.Model):
    _name = "g2p.infestation.type"
    _description = "Infestation Type"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", required=True)

class G2PCropInfestationIncident(models.Model):
    _name = "g2p.crop.infestation.incident"
    _description = "Crop Infestation Incident"
    _rec_name = "name"

    name = fields.Char(
        string="Incident Record ID",
        readonly=True,
        copy=False,
        default="New"
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('g2p.crop.infestation') or 'New'
        return super(G2PCropInfestationIncident, self).create(vals_list)

    production_id = fields.Many2one('g2p.crop.production', string="Production Record", ondelete="cascade")
    cluster_line_id = fields.Many2one('g2p.crop.production.cluster.line', string="Cluster Line Record", ondelete="cascade")

    crop_name_id = fields.Many2one(
        'g2p.crop',
        compute="_compute_crop_name_id",
        string="Crop Type Affected",
        store=True,
        readonly=True
    )

    @api.depends('production_id.crop_name_id', 'cluster_line_id.production_id.crop_name_id')
    def _compute_crop_name_id(self):
        for rec in self:
            if rec.production_id:
                rec.crop_name_id = rec.production_id.crop_name_id
            elif rec.cluster_line_id and rec.cluster_line_id.production_id:
                rec.crop_name_id = rec.cluster_line_id.production_id.crop_name_id
            else:
                rec.crop_name_id = False

    growth_stage = fields.Selection([
        ('emergence', 'Emergence / Seedling (ቡቃያ)'),
        ('vegetative', 'Vegetative (እድገት)'),
        ('flowering', 'Flowering / Booting (አበባ/ማንቀልጠር)'),
        ('maturity', 'Maturity / Harvesting (ምርት ስብሰባ)'),
    ], string="Growth Stage (የዕድገት ደረጃ)")

    infestation_type_ids = fields.Many2many('g2p.infestation.type', string="Type of Infestation")

    is_pest = fields.Boolean(compute="_compute_infestation_flags")
    is_weed = fields.Boolean(compute="_compute_infestation_flags")
    is_disease = fields.Boolean(compute="_compute_infestation_flags")
    is_nutrient = fields.Boolean(compute="_compute_infestation_flags")
    is_climate = fields.Boolean(compute="_compute_infestation_flags")

    @api.depends('infestation_type_ids', 'infestation_type_ids.code', 'infestation_type_ids.name')
    def _compute_infestation_flags(self):
        for rec in self:
            all_str = rec._get_infestation_type_strings(rec.infestation_type_ids)
            rec.is_pest = any('pest' in s or 'ተባይ' in s for s in all_str)
            rec.is_weed = any('weed' in s or 'አረም' in s for s in all_str)
            rec.is_disease = any('disease' in s or 'በሽታ' in s for s in all_str)
            rec.is_nutrient = any('nutrient' in s or 'deficiency' in s or 'ንጥረ' in s or 'nut' in s for s in all_str)
            rec.is_climate = any('climate' in s or 'shock' in s or 'አየር' in s or 'clim' in s for s in all_str)

    @api.onchange('infestation_type_ids')
    def _onchange_infestation_types(self):
        all_str = self._get_infestation_type_strings(self.infestation_type_ids)
        self.is_pest = any('pest' in s or 'ተባይ' in s for s in all_str)
        self.is_weed = any('weed' in s or 'አረም' in s for s in all_str)
        self.is_disease = any('disease' in s or 'በሽታ' in s for s in all_str)
        self.is_nutrient = any('nutrient' in s or 'deficiency' in s or 'ንጥረ' in s or 'nut' in s for s in all_str)
        self.is_climate = any('climate' in s or 'shock' in s or 'አየር' in s or 'clim' in s for s in all_str)

    def _get_infestation_type_strings(self, infestation_types):
        strings = []
        if not infestation_types:
            return strings

        for t in infestation_types:
            real_id = None
            if hasattr(t, '_origin') and t._origin and getattr(t._origin, 'id', None):
                orig_id = t._origin.id
                if isinstance(orig_id, int):
                    real_id = orig_id
                elif hasattr(orig_id, 'origin') and isinstance(orig_id.origin, int):
                    real_id = orig_id.origin

            if not real_id and getattr(t, 'id', None):
                if isinstance(t.id, int):
                    real_id = t.id
                elif hasattr(t.id, 'origin') and isinstance(t.id.origin, int):
                    real_id = t.id.origin
                elif isinstance(t.id, str) and t.id.isdigit():
                    real_id = int(t.id)

            if not real_id and isinstance(t, int):
                real_id = t

            if real_id:
                real_rec = self.env['g2p.infestation.type'].browse(real_id)
                if real_rec.exists():
                    if real_rec.code:
                        strings.append(str(real_rec.code).lower())
                    else:
                        _logger.warning("g2p.infestation.type ID %s has no 'code', falling back to name '%s'", real_id, real_rec.name)
                        if real_rec.name:
                            strings.append(str(real_rec.name).lower())
                        if real_rec.display_name:
                            strings.append(str(real_rec.display_name).lower())
                    continue

            if hasattr(t, 'code') and t.code:
                strings.append(str(t.code).lower())
            elif hasattr(t, 'name') and t.name:
                _logger.warning("g2p.infestation.type record has no 'code', falling back to name '%s'", t.name)
                strings.append(str(t.name).lower())
                if hasattr(t, 'display_name') and t.display_name:
                    strings.append(str(t.display_name).lower())

        return strings

    pest_line_ids = fields.One2many('g2p.crop.pest.line', 'infestation_id', string="Pest Details")
    weed_line_ids = fields.One2many('g2p.crop.weed.line', 'infestation_id', string="Weed Details")
    disease_line_ids = fields.One2many('g2p.crop.disease.line', 'infestation_id', string="Disease Details")
    nutrient_line_ids = fields.One2many('g2p.crop.nutrient.line', 'infestation_id', string="Nutrient Deficiency Details")
    climate_line_ids = fields.One2many('g2p.crop.climate.line', 'infestation_id', string="Climate Shock Details")

    severity_level = fields.Selection([
        ('low', 'Low (ቀላል)'),
        ('medium', 'Medium (መካከለኛ)'),
        ('high', 'High (ከፍተኛ)'),
    ], string="Severity Level")

    estimated_damage = fields.Char(string="Estimated Crop Damage (%) or (Hectares)")
    observation_date = fields.Date(string="Date of Observation (GC)")
    observation_date_ec = fields.Char(string="Date of Observation (E.C.)")
    geo_tagged_photo = fields.Binary(string="Geo-tagged Photo Upload")
    action_taken = fields.Text(string="Action Taken / Extension Advice")


    @api.onchange('observation_date')
    def _onchange_observation_date(self):
        if self.observation_date:
            ethiopian_date_str = eth_date.to_ethiopian(
                self.observation_date.year, self.observation_date.month, self.observation_date.day
            )
            self.observation_date_ec = eth_date.convert_tuple_to_string_with_separator(ethiopian_date_str)
        else:
            self.observation_date_ec = False

    @api.onchange('observation_date_ec')
    def _onchange_observation_date_ec(self):
        if self.observation_date_ec:
            # Format validation (allow -, /, or . as separators)
            date_list = re.split("[-/.]", self.observation_date_ec)
            if len(date_list) == 3:
                try:
                    # Expecting DD.MM.YYYY or YYYY.MM.DD?
                    # eth_date expects DD-MM-YYYY in its check usually, but let's try to convert:
                    # Let's just let it be Char, and if they typed it correctly we convert it back.
                    # Based on farmer.py:
                    d, m, y = int(date_list[0]), int(date_list[1]), int(date_list[2])
                    if y < 1000: # DD-MM-YYYY
                        greg_date = eth_date.to_gregorian(y, m, d)
                    else: # YYYY-MM-DD
                        greg_date = eth_date.to_gregorian(d, m, y)

                    self.observation_date = fields.Date.from_string(f"{greg_date[0]:04d}-{greg_date[1]:02d}-{greg_date[2]:02d}")
                except Exception:
                    pass # Ignore if they are still typing or typed an invalid date

    @api.constrains('estimated_damage', 'production_id', 'cluster_line_id')
    def _check_estimated_damage(self):
        for rec in self:
            if rec.estimated_damage:
                val_str = rec.estimated_damage.strip().lower()
                try:
                    if '%' in val_str:
                        val = float(val_str.replace('%', '').strip())
                        if val < 0 or val > 100:
                            raise ValidationError("Damage percentage must be between 0 and 100.")
                    else:
                        # Assume it's hectares or they wrote 'ha'
                        val = float(val_str.replace('ha', '').replace('hectares', '').strip())
                        max_area = rec.production_id.area_sown if rec.production_id else (rec.cluster_line_id.area_sown if rec.cluster_line_id else 0.0)
                        if val < 0 or val > max_area:
                            raise ValidationError(f"Damage area ({val} ha) cannot exceed the Sown Area ({max_area} ha).")
                except ValueError:
                    raise ValidationError("Invalid format for Estimated Crop Damage. Use a number, e.g., '50%' or '1.5 ha'.")


class G2PCropProduction(models.Model):
    _name = "g2p.crop.production"
    _description = "Crop Production Details"
    _rec_name = "name"

    name = fields.Char(
        string="Reference",
        readonly=True,
        copy=False,
        default="New",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('g2p.crop.production') or 'New'
        return super(G2PCropProduction, self).create(vals_list)

    crop_registry_id = fields.Many2one(
        "g2p.crop.registry",
        string="Crop Registry",
        ondelete="cascade",
        required=True,
    )

    season_id = fields.Many2one(
        "g2p.season",
        string="Season",
    )

    land_info_id = fields.Many2one('g2p.land.information', string="Land ID")

    # ── Land / Plot Detail relays ─────────────────────
    land_total_area = fields.Float(
        related="land_info_id.total_land_area",
        string="Total Land Area (ha)",
        readonly=True,
    )
    land_region_id = fields.Many2one(
        "g2p.region",
        string="Region",
        compute="_compute_land_region",
        store=True,
        readonly=True,
    )
    land_gps_coordinates = fields.Text(
        related="land_info_id.polygon_data",
        string="GPS Coordinates",
        readonly=True,
    )
    land_ownership_type = fields.Selection(
        related="land_info_id.ownership_type",
        string="Ownership Type",
        readonly=True,
    )

    @api.depends('land_info_id', 'land_info_id.land_kebele',
                 'land_info_id.land_kebele.woreda',
                 'land_info_id.land_kebele.woreda.zone',
                 'land_info_id.land_kebele.woreda.zone.region')
    def _compute_land_region(self):
        for rec in self:
            region = False
            if rec.land_info_id and rec.land_info_id.land_kebele:
                kebele = rec.land_info_id.land_kebele
                if kebele.woreda and kebele.woreda.zone and kebele.woreda.zone.region:
                    region = kebele.woreda.zone.region.id
            rec.land_region_id = region

    crop_name_id = fields.Many2one(
        "g2p.crop",
        string="Crop Name",
    )
    crop_category_id = fields.Many2one(
        "g2p.crop.category",
        related="crop_name_id.category_id",
        string="Crop Category",
        readonly=True,
    )

    sync_id = fields.Char(string="Sync ID")

    is_plot_not_registered = fields.Boolean(string="Plot not registered")
    temporary_land_id = fields.Char(string="Land ID (temporary)")


    # ── Farmer & Plot Identity relays ────────────────────
    reg_farmer_id = fields.Many2one('res.partner', related="crop_registry_id.partner_id", string="Farmer ID", readonly=True)
    reg_farmer_display_id = fields.Char(related="crop_registry_id.farmer_display_id", string="Farmer Name", readonly=True)
    reg_fyda_id = fields.Char(related="crop_registry_id.fyda_id", string="Fayda ID", readonly=True)
    reg_region_name_id = fields.Many2one("g2p.region", related="crop_registry_id.region_id", string="Region", readonly=True)
    reg_zone_name_id = fields.Many2one("g2p.zone", related="crop_registry_id.zone_id", string="Zone", readonly=True)
    reg_woreda_name_id = fields.Many2one("g2p.woreda", related="crop_registry_id.woreda_id", string="Woreda", readonly=True)
    reg_kebele_id = fields.Many2one('g2p.kebele', related="crop_registry_id.kebele_id", string="Kebele", readonly=True)

    # ── Cultivation Details relays ────────────────────────
    reg_crop_name_id = fields.Many2one("g2p.crop", related="crop_registry_id.crop_name_id", string="Crop Name", readonly=True)
    reg_crop_variety_id = fields.Many2one("g2p.crop.variety", related="crop_registry_id.crop_variety_id", string="Crop Variety", readonly=True)
    reg_crop_category_id = fields.Many2one("g2p.crop.category", related="crop_registry_id.crop_category_id", string="Crop Category", readonly=True)

    # ── Fertilizer relay fields ────────────────────────────

    actual_fertilizer_type = fields.Selection([
        ('inorganic', 'Inorganic'),
        ('organic', 'Organic'),
        ('biofertilizer', 'Bio Fertilizer')
    ], string="Actual Fertilizer Type")
    actual_fertilizer_qty = fields.Float(string="Actual Fertilizer Qty (kg)", default=0.0)
    actual_seed_class = fields.Selection([('local', 'Local'), ('improved', 'Improved')], string="Seed Type")
    cultivated_by = fields.Many2one("g2p.machinery", string="Cultivation Type")
    # ── Sowing ───────────────────────────────────────────────
    sowing_status = fields.Selection([
        ('sown', 'Sown'),
        ('not_sown', 'Not Sown'),
    ], string="Sowing Status")

    cluster_status_ids = fields.Many2many(
        "g2p.cluster.status",
        string="Cluster Status"
    )

    is_clustered = fields.Boolean(compute='_compute_cluster_status_flags', store=False)
    is_independent = fields.Boolean(compute='_compute_cluster_status_flags', store=False)

    @api.depends('cluster_status_ids', 'cluster_status_ids.name')
    def _compute_cluster_status_flags(self):
        for rec in self:
            names = rec.cluster_status_ids.mapped('name') if rec.cluster_status_ids else []
            rec.is_clustered = 'Clustered' in names
            rec.is_independent = 'Independent' in names


    @api.depends('sync_id', 'crop_registry_id', 'crop_registry_id.actual_annual_line_ids.cluster_info_ids')
    def _compute_cluster_info_ids(self):
        for rec in self:
            cluster_recs = self.env['g2p.cluster.information']
            if rec.crop_registry_id and rec.sync_id:
                annual = rec.crop_registry_id.actual_annual_line_ids.filtered(lambda l: l.sync_id == rec.sync_id)
                if annual:
                    cluster_recs |= annual.cluster_info_ids
            rec.cluster_info_ids = cluster_recs

    # For clustered sowing
    cluster_info_ids = fields.Many2many(
        'g2p.cluster.information',
        string="Cluster Information",
        compute='_compute_cluster_info_ids',
        store=True,
        readonly=False
    )

    production_cluster_line_ids = fields.One2many(
        'g2p.crop.production.cluster.line',
        'production_id',
        string="Cluster Details"
    )

    area_sown = fields.Float(string="Area Sown (ha)", default=0.0)

    actual_sowing_date = fields.Date(string="Actual Planted Date")

    infestation_incident_ids = fields.One2many(
        'g2p.crop.infestation.incident',
        'production_id',
        string="Infestation Incidents"
    )
    has_pest_disease = fields.Boolean(string="Pest / Disease Occurrence", default=False)

    # ── Harvest (visible when Sowing Status = Sown) ──────────
    crop_maturity_status = fields.Selection([
        ('green', 'Not Yet Ready'),
        ('yellow', 'Ready for Harvest'),
    ], string="Crop Maturity Status")

    harvest_date = fields.Date(string="Harvest Date")
    area_harvested = fields.Float(string="Area Harvested (ha)")
    qty_harvested = fields.Float(string="Quantity Harvested (quintal)")
    post_harvest_loss_pct = fields.Float(string="Post-harvest Loss (%)")
    qty_stored = fields.Float(string="Quantity Stored")
    qty_sold = fields.Float(string="Quantity Sold")


    expected_yield = fields.Float(string="Expected Yield", default=0.0)
    planned_area = fields.Float(string="Planned Area", default=0.0)
    actual_crop_area = fields.Float(string="Actual Crop Area", default=0.0)
    actual_seed_qty = fields.Float(string="Actual Seed Qty", default=0.0)
    actual_yield_cached = fields.Float(string="Actual Yield", default=0.0)

    # Survey Personnel
    surveyor_name = fields.Char(string="DA Name")
    surveyor_mobile_number = fields.Char(string="DA Mobile Number")
    supervisor_name = fields.Char(string="Supervisor Name")
    supervisor_mobile_number = fields.Char(string="Supervisor Mobile Number")
    first_approvel_status = fields.Selection([
        ('draft', 'Draft'),
    ], string="First approvel status")

    # ── Production Result (computed) ─────────────────────────
    yield_per_ha = fields.Float(
        string="Yield (kg/ha)",
        compute="_compute_production_results",
        store=True,
    )
    yield_performance_pct = fields.Float(
        string="Yield Performance (%)",
        compute="_compute_production_results",
        store=True,
    )
    land_utilization_rate = fields.Float(
        string="Land Utilization Rate",
        compute="_compute_production_results",
        store=True,
    )
    seed_productivity = fields.Float(
        string="Seed Productivity",
        compute="_compute_production_results",
        store=True,
    )
    fertilizer_efficiency = fields.Float(
        string="Fertilizer Efficiency",
        compute="_compute_production_results",
        store=True,
    )
    @api.constrains('harvest_date', 'actual_sowing_date')
    def _check_harvest_date(self):
        for rec in self:
            if rec.harvest_date and rec.actual_sowing_date:
                if rec.harvest_date < rec.actual_sowing_date:
                    raise ValidationError("Harvest date must be greater than or equal to the actual planted date.")

    @api.onchange('harvest_date', 'actual_sowing_date')
    def _onchange_harvest_date(self):
        actual_date = self.actual_sowing_date or (self._origin.actual_sowing_date if getattr(self, '_origin', False) else False)
        if self.harvest_date and actual_date:
            if self.harvest_date < actual_date:
                self.harvest_date = False
                return {
                    'warning': {
                        'title': 'Invalid Harvest Date',
                        'message': 'Harvest date must be greater than or equal to the actual planted date.'
                    }
                }

    @api.constrains('area_harvested', 'actual_crop_area')
    def _check_area_harvested(self):
        for rec in self:
            if rec.area_harvested > rec.actual_crop_area:
                raise ValidationError(
                    f"Area Harvested ({rec.area_harvested} ha) cannot exceed "
                    f"Actual Crop Area ({rec.actual_crop_area} ha) in Cultivation."
                )

    @api.onchange('area_harvested')
    def _onchange_area_harvested(self):
        if self.area_harvested > self.actual_crop_area:
            warning = {
                'title': "Invalid Area Harvested",
                'message': f"Area Harvested ({self.area_harvested} ha) cannot exceed "
                           f"Actual Crop Area ({self.actual_crop_area} ha) in Cultivation."
            }
            self.area_harvested = self.actual_crop_area
            return {'warning': warning}



    @api.depends(
        'qty_harvested', 'area_harvested',
        'expected_yield', 'planned_area',
        'actual_seed_qty', 'actual_fertilizer_qty',
        'actual_yield_cached'
    )
    def _compute_production_results(self):
        for rec in self:
            # Yield (kg/ha) = Qty Harvested (converted to kg) ÷ Area Harvested
            rec.yield_per_ha = (
                (rec.qty_harvested * 100) / rec.area_harvested
                if rec.area_harvested else 0.0
            )

            # Yield Performance % = (Actual Yield from Cultivation ÷ Expected Yield) × 100
            expected = rec.expected_yield
            actual = rec.actual_yield_cached
            rec.yield_performance_pct = (
                (actual / expected * 100)
                if expected else 0.0
            )

            # Land Utilization Rate = Actual Area ÷ Planned Area
            planned_area = rec.planned_area
            rec.land_utilization_rate = (
                rec.area_harvested / planned_area
                if planned_area else 0.0
            )

            # Seed Productivity = Total Yield ÷ Seed Used (kg)
            seed_used = rec.actual_seed_qty
            total_yield = rec.qty_harvested * 100  # convert quintal → kg
            rec.seed_productivity = (
                total_yield / seed_used
                if seed_used else 0.0
            )

            # Fertilizer Efficiency = Total Yield ÷ Fertilizer Applied (kg)
            fertilizer_applied = rec.actual_fertilizer_qty
            rec.fertilizer_efficiency = (
                total_yield / fertilizer_applied
                if fertilizer_applied else 0.0
            )


    # ── Approval Workflow fields ─────────────────────────────
    registry_lifecycle_stage = fields.Selection(related="crop_registry_id.lifecycle_stage", string="Lifecycle Stage", readonly=True)
    registry_sowing_state = fields.Selection(related="crop_registry_id.sowing_state", string="Sowing State", readonly=False)
    registry_harvesting_state = fields.Selection(related="crop_registry_id.harvesting_state", string="Harvesting State", readonly=False)

    can_approve = fields.Boolean(compute='_compute_can_approve')
    can_set_draft = fields.Boolean(compute='_compute_can_approve')
    menu_title = fields.Char(compute='_compute_menu_title')

    def _compute_menu_title(self):
        for rec in self:
            rec.menu_title = self.env.context.get('menu_title', 'Sowing Details')

    @api.depends('registry_harvesting_state', 'registry_sowing_state')
    @api.depends_context('uid')
    def _compute_can_approve(self):
        for rec in self:
            is_da = self.env.user.has_group('g2p_crop_registry.group_development_agent')
            is_sms = self.env.user.has_group('g2p_crop_registry.group_woreda_sms')
            is_wah = self.env.user.has_group('g2p_crop_registry.group_woreda_agri_office_head')

            # Determine which state to check based on context or lifecycle stage
            if self.env.context.get('is_harvesting'):
                state = rec.registry_harvesting_state
            else:
                state = rec.registry_sowing_state

            can_approve = False
            can_set_draft = False
            if state == 'draft' and is_sms:
                can_approve = True
            elif state == 'pending_wah' and is_wah:
                can_approve = True

            if state in ('draft', 'approved') and is_sms:
                can_set_draft = False
            elif state == 'draft' and is_wah:
                can_set_draft = False
            else:
                if is_sms or is_wah:
                    can_set_draft = True

            rec.can_approve = can_approve
            rec.can_set_draft = can_set_draft

    def action_approve_sms(self):
        registries = self.mapped('crop_registry_id')
        for reg in registries:
            reg.action_approve_sms()

    def action_approve_wah(self):
        registries = self.mapped('crop_registry_id')
        for reg in registries:
            reg.action_approve_wah()

    def action_reject(self):
        for rec in self:
            if rec.crop_registry_id:
                action = rec.crop_registry_id.action_reject()
                action['context'] = {
                    'active_model': 'g2p.crop.registry',
                    'active_id': rec.crop_registry_id.id,
                    'active_ids': [rec.crop_registry_id.id],
                }
                return action

    def action_set_draft(self):
        for rec in self:
            if rec.crop_registry_id:
                rec.crop_registry_id.action_set_draft()

    def action_suggest_edit(self):
        for rec in self:
            if rec.crop_registry_id:
                return {
                    'name': 'Suggest Edit',
                    'type': 'ir.actions.act_window',
                    'res_model': 'g2p.crop.request.wiz',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_crop_registry_ids': [rec.crop_registry_id.id],
                        'active_model': 'g2p.crop.registry',
                        'active_id': rec.crop_registry_id.id,
                        'active_ids': [rec.crop_registry_id.id],
                    },
                }


class CropProductionClusterLine(models.Model):
    _name = 'g2p.crop.production.cluster.line'
    _description = 'Crop Production Cluster Line'

    production_id = fields.Many2one('g2p.crop.production', string="Production Record", ondelete='cascade')
    cluster_info_id = fields.Many2one('g2p.cluster.information', string="Cluster ID", required=True)
    cluster_name = fields.Char(related='cluster_info_id.cluster_name', string="Cluster Name", readonly=True)

    sowing_status = fields.Selection([
        ('Not Sown', 'Not Sown'),
        ('Sown', 'Sown')
    ], string="Sowing Status", default='Not Sown')
    area_sown = fields.Float(string="Area Sown (ha)", default=0.0)
    has_pest_disease = fields.Boolean(string="Pest / Disease Occurrence", default=False)
    infestation_incident_ids = fields.One2many(
        'g2p.crop.infestation.incident',
        'cluster_line_id',
        string="Infestation Incidents"
    )

    # Related info for context
    season_id = fields.Many2one('g2p.season', related='cluster_info_id.season_id', string="Season", readonly=True)
    cluster_agro_ecological_zone = fields.Selection(related='cluster_info_id.cluster_agro_ecological_zone', string="Agro Ecological Zone", readonly=True)
    cluster_area_hectare = fields.Float(related='cluster_info_id.cluster_area_hectare', string="Total Cultivated Area (ha)", readonly=True)


    # Harvest fields
    crop_maturity_status = fields.Selection([
        ('green', 'Not Yet Ready'),
        ('yellow', 'Ready for Harvest'),
    ], string="Crop Maturity Status")
    harvest_date = fields.Date(string="Harvest Date")
    area_harvested = fields.Float(string="Area Harvested (ha)")
    qty_harvested = fields.Float(string="Quantity Harvested (quintal)")
    post_harvest_loss_pct = fields.Float(string="Post-harvest Loss (%)")
    qty_stored = fields.Float(string="Quantity Stored")
    qty_sold = fields.Float(string="Quantity Sold")
