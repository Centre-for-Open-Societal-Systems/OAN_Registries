from odoo import api, fields, models
from odoo.exceptions import ValidationError
from datetime import date
import re
from odoo.addons.g2p_ati.models.utils import eth_date
import uuid

def is_date_in_season(test_date, start_date, end_date):
    if not test_date or not start_date or not end_date:
        return True
    start_m, start_d = start_date.month, start_date.day
    end_m, end_d = end_date.month, end_date.day
    test_m, test_d = test_date.month, test_date.day

    if start_m < end_m or (start_m == end_m and start_d <= end_d):
        if test_m < start_m or test_m > end_m:
            return False
        if test_m == start_m and test_d < start_d:
            return False
        if test_m == end_m and test_d > end_d:
            return False
        return True
    else:
        is_after_start = (test_m > start_m) or (test_m == start_m and test_d >= start_d)
        is_before_end = (test_m < end_m) or (test_m == end_m and test_d <= end_d)
        return is_after_start or is_before_end

class G2PBiennialLine(models.Model):
    _name = "g2p.biennial.line"
    _description = "Biennial Crop Planned Line"

    def write(self, vals):
        result = super().write(vals)
        if 'crop_expected' in vals:
            for rec in self:
                if not rec.sync_id or not rec.crop_registry_id:
                    continue
                actual_lines = rec.crop_registry_id.actual_biennial_line_ids.filtered(
                    lambda l: l.sync_id == rec.sync_id
                )
                for actual in actual_lines:
                    actual.write({'actual_yield': vals['crop_expected']})
        return result

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

    # Survey Personnel
    surveyor_name = fields.Char(string="Surveyor Name")
    surveyor_mobile_number = fields.Char(string="Surveyor Mobile Number")
    supervisor_name = fields.Char(string="Supervisor Name")
    supervisor_mobile_number = fields.Char(string="Supervisor Mobile Number")
    first_approvel_status = fields.Selection([
        ('draft', 'Draft'),
    ], string="First approvel status")


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
            if getattr(self, 'collected_gc', False):
                return self._onchange_collected_gc()

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
                rec.crop_category_id = rec.crop_name_id.category_id.id
            else:
                rec.crop_category_id = False


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

    @api.onchange("collected_gc", "start_gc", "end_gc", "season_id")
    def _onchange_collected_gc(self):
        if self.collected_gc:
            start_date = self.start_gc or (self.season_id.start_gc if self.season_id else False)
            end_date = self.end_gc or (self.season_id.end_gc if self.season_id else False)
            if start_date and end_date:
                # Check if the date is within the season's start and end months/dates
                if not is_date_in_season(self.collected_gc, start_date, end_date):
                    self.collected_gc = False
                    self.collected_ec = False
                    return {
                        'warning': {
                            'title': 'Invalid Actual Date',
                            'message': 'Actual Planted Date (GC) must be within the Season Details (Start GC and End GC).'
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

    @api.constrains("collected_gc", "start_gc", "end_gc")
    def _check_collected_gc(self):
        for rec in self:
            if rec.collected_gc:
                if rec.start_gc and rec.end_gc:
                    if not is_date_in_season(rec.collected_gc, rec.start_gc, rec.end_gc):
                        raise ValidationError("Actual Planted Date (GC) must be within the Season Details (Start GC and End GC).")

    @api.onchange("collected_ec")
    def _onchange_collected_ec(self):
        if self.collected_ec:
            eth_date.check_ethipian_date_str(self.collected_ec, future_date=True)
            date_list = re.split("[-/,]", self.collected_ec)
            gc_date = eth_date.to_gregorian(
                int(date_list[2]), int(date_list[1]), int(date_list[0])
            )
            self.collected_gc = gc_date
            return self._onchange_collected_gc()




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

    @api.constrains('actual_crop_area')
    def _check_actual_crop_area(self):
        for rec in self:
            if not rec.is_manual and rec.crop_registry_id:
                planned_line = rec.crop_registry_id.biennial_line_ids.filtered(lambda l: l.sync_id == rec.sync_id)
                if planned_line and rec.actual_crop_area > planned_line[0].crop_planned_area:
                    raise ValidationError(f"Actual Crop Area ({rec.actual_crop_area} ha) cannot be greater than Planned Crop Area ({planned_line[0].crop_planned_area} ha).")

    @api.onchange('actual_crop_area')
    def _onchange_actual_crop_area(self):
        if self.crop_registry_id and self.actual_crop_area and self.land_info_id:
            total_actual = 0.0

            same_land_annual = self.crop_registry_id.actual_annual_line_ids.filtered(lambda l: l.land_info_id == self.land_info_id)
            total_actual += sum(same_land_annual.mapped('actual_crop_area'))

            same_land_perennial = self.crop_registry_id.actual_perennial_line_ids.filtered(lambda l: l.land_info_id == self.land_info_id)
            total_actual += sum(same_land_perennial.mapped('actual_crop_area'))

            same_land_biennial = self.crop_registry_id.actual_biennial_line_ids.filtered(lambda l: l.land_info_id == self.land_info_id)
            total_actual += sum(same_land_biennial.mapped('actual_crop_area'))

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
                        'message': "You entered %.2f ha, but only %.2f ha is remaining out of the total %.2f ha (%.2f ha is already allocated to other crops)." % (attempted_area, remaining_area, max_area, allocated_area)
                    }
                }

    # Onchange validation for actual_crop_area removed to allow editing; validated on save

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


    season_id = fields.Many2one('g2p.season', string="Season", required=True)
    crop_name_id = fields.Many2one("g2p.crop", string="Crop", required=True)
    collected_gc = fields.Date(string="Actual Planted Date (GC)")
    collected_ec = fields.Char(string="Actual Planted Date (EC)")
    crop_category_id = fields.Many2one("g2p.crop.category", string="Crop Category", compute="_compute_crop_category", store=True, readonly=True)
    crop_variety_id = fields.Many2one("g2p.crop.variety", string="Crop Variety")
    remark = fields.Char(string="Remark")
    is_crop_changed = fields.Boolean(string="Crop Changed", compute="_compute_is_crop_changed")
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

    # Survey Personnel
    surveyor_name = fields.Char(string="Surveyor Name")
    surveyor_mobile_number = fields.Char(string="Surveyor Mobile Number")
    supervisor_name = fields.Char(string="Supervisor Name")
    supervisor_mobile_number = fields.Char(string="Supervisor Mobile Number")
    first_approvel_status = fields.Selection([
        ('draft', 'Draft'),
    ], string="First approvel status")

    pest_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Pest Occurrence")
    pest_line_ids = fields.One2many('g2p.crop.pest.line', 'actual_biennial_line_id', string="Pest Details")

    weed_occurrence = fields.Selection([('yes', 'Yes'), ('no', 'No')], string="Weed Occurrence")
    weed_line_ids = fields.One2many('g2p.crop.weed.line', 'actual_biennial_line_id', string="Weed Details")

    actual_yield = fields.Float(string="Actual Yield (quintal)")
    cultivated_by = fields.Many2one("g2p.machinery", string="Cultivation Type")
    land_prep_method_ids = fields.Many2many("g2p.land.prep.method", string="Land Preparation Method")

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

    @api.depends('crop_name_id', 'sync_id', 'crop_registry_id.biennial_line_ids.crop_name_id')
    def _compute_is_crop_changed(self):
        for rec in self:
            if not rec.crop_registry_id or not rec.sync_id or not rec.crop_name_id:
                rec.is_crop_changed = False
                continue
            planned = rec.crop_registry_id.biennial_line_ids.filtered(lambda l: l.sync_id == rec.sync_id)
            if planned and planned[0].crop_name_id != rec.crop_name_id:
                rec.is_crop_changed = True
            else:
                rec.is_crop_changed = False

    # Onchange validation for total actual crop area removed; validated on save

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
            if getattr(self, 'collected_gc', False):
                return self._onchange_collected_gc()

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
                rec.crop_category_id = rec.crop_name_id.category_id.id
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
            if not rec.crop_registry_id or not rec.crop_name_id or rec.is_manual:
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
                rec.crop_name_id.category_id.id
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

    @api.onchange("collected_gc", "start_gc", "end_gc", "season_id")
    def _onchange_collected_gc(self):
        if self.collected_gc:
            start_date = self.start_gc or (self.season_id.start_gc if self.season_id else False)
            end_date = self.end_gc or (self.season_id.end_gc if self.season_id else False)
            if start_date and end_date:
                # Check if the date is within the season's start and end months/dates
                if not is_date_in_season(self.collected_gc, start_date, end_date):
                    self.collected_gc = False
                    self.collected_ec = False
                    return {
                        'warning': {
                            'title': 'Invalid Actual Date',
                            'message': 'Actual Planted Date (GC) must be within the Season Details (Start GC and End GC).'
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

    @api.constrains("collected_gc", "start_gc", "end_gc")
    def _check_collected_gc(self):
        for rec in self:
            if rec.collected_gc:
                if rec.start_gc and rec.end_gc:
                    if not is_date_in_season(rec.collected_gc, rec.start_gc, rec.end_gc):
                        raise ValidationError("Actual Planted Date (GC) must be within the Season Details (Start GC and End GC).")

    @api.onchange("collected_ec")
    def _onchange_collected_ec(self):
        if self.collected_ec:
            eth_date.check_ethipian_date_str(self.collected_ec, future_date=True)
            date_list = re.split("[-/,]", self.collected_ec)
            gc_date = eth_date.to_gregorian(
                int(date_list[2]), int(date_list[1]), int(date_list[0])
            )
            self.collected_gc = gc_date
            return self._onchange_collected_gc()


