from odoo import api, fields, models
from odoo.exceptions import ValidationError
from datetime import date
import re
from odoo.addons.g2p_ati.models.utils import eth_date
import uuid
from odoo.tools import float_compare


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

def _generate_unique_land_id(env, partner, region=None, zone=None, woreda=None, kebele=None):
    reg_code = (region.code if region and hasattr(region, 'code') and region.code else 'RU').upper()
    zone_code = (zone.code if zone and hasattr(zone, 'code') and zone.code else '01').zfill(2)
    woreda_code = (woreda.code if woreda and hasattr(woreda, 'code') and woreda.code else '01').zfill(2)
    kebele_code = (kebele.code if kebele and hasattr(kebele, 'code') and kebele.code else '001').zfill(3)

    base_prefix = f"{reg_code}/{zone_code}/{woreda_code}/{kebele_code}"

    # Query with database row lock to prevent concurrency collisions
    env.cr.execute(
        "SELECT land_id FROM g2p_land_information WHERE land_id LIKE %s FOR UPDATE",
        (f"{base_prefix}/%",)
    )
    existing_rows = env.cr.fetchall()
    existing_ids = [r[0] for r in existing_rows if r[0]]

    max_seq = 0
    for land_str in existing_ids:
        parts = land_str.split('/')
        if len(parts) == 5 and parts[-1].isdigit():
            max_seq = max(max_seq, int(parts[-1]))

    next_seq = max_seq + 1
    return f"{base_prefix}/{str(next_seq).zfill(5)}"


class G2PAnnualLine(models.Model):
    _name = "g2p.annual.line"
    _description = "Annual Planned Line"
    _rec_name = "crop_registry_id"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'crop_expected' in vals or 'cluster_info_ids' in vals:
            for rec in self:
                if not rec.sync_id or not rec.crop_registry_id:
                    continue
                actual_lines = rec.crop_registry_id.actual_annual_line_ids.filtered(
                    lambda l: l.sync_id == rec.sync_id
                )
                for actual in actual_lines:
                    updates = {}
                    if 'crop_expected' in vals:
                        updates['actual_yield'] = vals['crop_expected']
                    if 'cluster_info_ids' in vals:
                        updates['cluster_info_ids'] = [(6, 0, rec.cluster_info_ids.ids)]
                    if updates:
                        actual.write(updates)
        return result

    def unlink(self):
        from odoo.exceptions import AccessError
        for line in self:
            if line.crop_registry_id and line.crop_registry_id.planning_state == 'approved':
                if not self.env.user.has_group('g2p_crop_registry.group_woreda_agri_office_head'):
                    raise AccessError("Only the Woreda Agriculture Office Head (WAH) can delete an approved record.")
        return super().unlink()

    crop_registry_id = fields.Many2one("g2p.crop.registry", string="Crop Registry", ondelete="cascade")
    sync_id = fields.Char(string="Sync ID", default=lambda self: str(uuid.uuid4()))

    is_plot_not_registered = fields.Boolean(string="Plot not registered")
    temporary_land_id = fields.Char(string="Land ID (temporary)")
    land_info_id = fields.Many2one('g2p.land.information', string="Land ID")
    menu_title = fields.Char(compute='_compute_menu_title')

    def _compute_menu_title(self):
        for rec in self:
            rec.menu_title = self.env.context.get('menu_title', 'Planning Details')
    region_name_id = fields.Many2one('g2p.region', string='Region')
    zone_name_id = fields.Many2one('g2p.zone', string='Zone')
    woreda_name_id = fields.Many2one('g2p.woreda', string='Woreda')
    kebele_id = fields.Many2one('g2p.kebele', string='Kebele')
    gps = fields.Char(string='GPS Coordinates')

    ownership_type = fields.Selection([('owner', 'Owner'), ('tenant', 'Tenant'), ('crop_share', 'Crop Sharing'), ('family_gift', 'Family Gift')], string="Ownership Type")
    land_area = fields.Float(string="Total Land Area (ha)")
    land_category = fields.Selection([('annual', 'Annual Crop'), ('perennial', 'Perennial Crop'), ('biennial', 'Biennial Crop')], string="Plot Category")
    soil_fertility = fields.Char(string="Soil Fertility")
    season_id = fields.Many2one('g2p.season', string="Season")
    start_gc = fields.Date(string="Start GC")
    start_month = fields.Integer(string="Start Month", compute="_compute_start_date", store=True)
    start_day = fields.Integer(string="Start Day", compute="_compute_start_date", store=True)
    end_gc = fields.Date(string="End GC")
    end_month = fields.Integer(string="End Month", compute="_compute_end_date", store=True)
    end_day = fields.Integer(string="End Day", compute="_compute_end_date", store=True)

    crop_name_id = fields.Many2one("g2p.crop", string="Crop")
    local_name = fields.Char(string="Local Name")
    scientific_name = fields.Char(string="Scientific Name")
    collected_gc = fields.Date(string="Planned Date (GC)")
    collected_ec = fields.Char(string="Planned Date (EC)")
    crop_category_id = fields.Many2one("g2p.crop.category", string="Crop Category", compute="_compute_crop_category", store=True, readonly=True)
    crop_variety_id = fields.Many2one("g2p.crop.variety", string="Crop Variety")
    cropping_system = fields.Selection([
        ('mono_cropping', 'Mono-cropping'),
        ('inter_cropping', 'Inter-cropping'),
    ], string="Cropping System")

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
    seed_source = fields.Selection([
        ('govt_woreda', 'Government / Woreda Agriculture Office'),
        ('agri_coop', 'Agricultural Cooperative / Union'),
        ('private_enterprise', 'Private Seed Enterprise'),
        ('farmer_exchange', 'Farmer-to-Farmer Exchange / Saved Seed'),
    ], string="Seed Source")
    seed_planned_qty = fields.Float(string="Planned Seed Quantity (kg)")
    seed_planned_fertilizer_type = fields.Selection([
        ('organic', 'Organic'),
        ('inorganic', 'Inorganic'),
        ('biofertilizer', 'Bio Fertilizer')
    ], string="Planned Fertilizer Type")

    seed_planned_fertilizer_qty = fields.Float(string="Planned Fertilizer Quantity (kg)")
    seed_planned_fertilizer_sack = fields.Float(string="Planned Fertilizer Sacks Count", compute="_compute_planned_fertilizer_sacks", store=True)
    water_resource_line_ids = fields.One2many('g2p.water.resource.line', 'annual_line_id', string="Water Resources")


    planned_labor = fields.Integer(string="Planned Labor")
    cluster_info_ids = fields.One2many('g2p.cluster.information', 'annual_line_id', string='Cluster Information')
    has_cluster_farming = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string="Have you done any cluster farming or related activities earlier?")

    # Survey Personnel
    surveyor_name = fields.Char(string="DA Name")
    surveyor_mobile_number = fields.Char(string="DA Mobile Number")
    supervisor_name = fields.Char(string="Supervisor Name")
    supervisor_mobile_number = fields.Char(string="Supervisor Mobile Number")
    first_approvel_status = fields.Selection([
        ('draft', 'Draft'),
    ], string="First approvel status")

    # --- Proxy fields and methods for bypassing registry form ---
    registry_planning_state = fields.Selection(related="crop_registry_id.planning_state", string="Planning State", readonly=False)
    registry_cultivation_state = fields.Selection(related="crop_registry_id.cultivation_state", string="Cultivation State", readonly=False)
    registry_sowing_state = fields.Selection(related="crop_registry_id.sowing_state", string="Sowing State", readonly=False)
    registry_harvesting_state = fields.Selection(related="crop_registry_id.harvesting_state", string="Harvesting State", readonly=False)
    registry_lifecycle_stage = fields.Selection(related="crop_registry_id.lifecycle_stage", string="Lifecycle Stage", readonly=True)
    registry_state = fields.Selection(related="crop_registry_id.state", string="State", readonly=True)
    # -----------------------------------------------------------

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


    @api.onchange('crop_planned_area', 'land_info_id')
    def _onchange_crop_planned_area(self):
        if not self.land_info_id:
            return
        total_land = self.land_info_id.total_land_area
        land_id = self.land_info_id.id
        db_lines = self.env['g2p.annual.line'].search([('land_info_id', '=', land_id)]) if land_id else self.env['g2p.annual.line'].browse()
        if self.crop_registry_id:
            reg_lines = self.crop_registry_id.annual_line_ids
            all_annual_lines = db_lines | reg_lines
        else:
            all_annual_lines = db_lines
            if self.env.context.get('annual_line_ids'):
                all_annual_lines = all_annual_lines | self.env['g2p.annual.line'].browse(self.env.context.get('annual_line_ids'))

        self_origin = getattr(self, '_origin', self)

        # Deduplicate by origin to avoid counting same line twice (DB vs NewId)
        grouped = {}
        for l in all_annual_lines:
            origin = getattr(l, '_origin', l)
            origin_id = origin.id or l.id
            if origin_id not in grouped or not isinstance(l.id, int):
                grouped[origin_id] = l

        other_records = [
            l for l in grouped.values()
            if l.land_info_id == self.land_info_id and l != self and getattr(l, '_origin', l) != self_origin
        ]

        other_crop_used = sum(l.crop_planned_area for l in other_records)
        other_cluster_used = sum(sum(c.cluster_area_hectare for c in l.cluster_info_ids) for l in other_records)
        remaining_before_record = total_land - (other_crop_used + other_cluster_used)

        current_cluster_area = sum(self.cluster_info_ids.mapped('cluster_area_hectare'))

        # Check if total exceeds
        if float_compare(self.crop_planned_area + current_cluster_area, remaining_before_record, precision_digits=2) > 0:
            # Reset the crop area so it doesn't stay invalid
            attempted_crop = self.crop_planned_area
            self.crop_planned_area = 0.0

            return {
                'warning': {
                    'title': "Area Limit Exceeded",
                    'message': f"You entered {attempted_crop:.2f} ha for the crop, but only {remaining_before_record:.2f} ha is remaining on this land.\n\n"
                               f"Total Land: {total_land:.2f} ha\n"
                               f"Already Used: {other_crop_used + other_cluster_used:.2f} ha"
                }
            }

    @api.constrains('crop_planned_area', 'cluster_info_ids', 'land_info_id')
    def _check_land_area_allocation(self):
        for rec in self:
            if not rec.land_info_id or not getattr(rec, 'crop_registry_id', False):
                continue

            # 1. Total available land
            total_land = rec.land_info_id.total_land_area

            # 2. Get other records on this same land plot (excluding the current one)
            other_records = rec.crop_registry_id.annual_line_ids.filtered(
                lambda l: l.land_info_id == rec.land_info_id and l.id != rec.id
            )

            # 3. Sum used areas from other records
            other_crop_used = sum(other_records.mapped('crop_planned_area'))
            other_cluster_used = sum(sum(c.cluster_area_hectare for c in r.cluster_info_ids) for r in other_records)
            remaining_before_record = total_land - (other_crop_used + other_cluster_used)

            # Define current cluster area BEFORE the zero-check
            current_cluster_area = sum(rec.cluster_info_ids.mapped('cluster_area_hectare'))

            # Zero Remaining Check
            if float_compare(remaining_before_record, 0.0, precision_digits=2) <= 0:
                if float_compare(rec.crop_planned_area, 0.0, precision_digits=2) > 0 or float_compare(current_cluster_area, 0.0, precision_digits=2) > 0:
                    raise ValidationError("No remaining area available for this land.")

            # Step 1: Crop Area Check
            if float_compare(rec.crop_planned_area, remaining_before_record, precision_digits=2) > 0:
                raise ValidationError(f"Crop area exceeds remaining land available ({remaining_before_record:.2f} ha remaining).")

            # Step 2: Cluster Area Check
            remaining_after_crop = remaining_before_record - rec.crop_planned_area
            if float_compare(current_cluster_area, remaining_after_crop, precision_digits=2) > 0:
                raise ValidationError(f"Cluster area exceeds remaining land after crop allocation ({remaining_after_crop:.2f} ha remaining).")


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
                if not is_date_in_season(self.collected_gc, self.start_gc, self.end_gc):
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

    @api.constrains("collected_gc", "start_gc", "end_gc")
    def _check_collected_gc(self):
        for rec in self:
            if rec.collected_gc:
                if rec.start_gc and rec.end_gc:
                    if not is_date_in_season(rec.collected_gc, rec.start_gc, rec.end_gc):
                        raise ValidationError("Planned Date (GC) must be within the Season Details (Start GC and End GC).")

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




    @api.constrains('land_category', 'season_id', 'crop_name_id')
    def _check_season_crop_required(self):
        for rec in self:
            if rec.land_category:
                if not rec.season_id or not rec.crop_name_id:
                    raise ValidationError("Season and Crop are required when Plot Category is selected.")

class G2PAnnualActualLine(models.Model):
    _name = "g2p.annual.actual.line"
    _description = "Annual Actual Line"
    _rec_name = "crop_registry_id"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        return records

    def write(self, vals):
        result = super().write(vals)
        return result

    def unlink(self):
        from odoo.exceptions import AccessError
        for line in self:
            if line.crop_registry_id and (
                line.crop_registry_id.planning_state == 'approved' or
                line.crop_registry_id.cultivation_state == 'approved' or
                line.crop_registry_id.sowing_state == 'approved' or
                line.crop_registry_id.harvesting_state == 'approved' or
                line.crop_registry_id.state == 'approved'
            ):
                if not self.env.user.has_group('g2p_crop_registry.group_woreda_agri_office_head'):
                    raise AccessError("Only the Woreda Agriculture Office Head (WAH) can delete an approved record.")
        return super().unlink()
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

    @api.constrains('actual_crop_area')
    def _check_actual_crop_area(self):
        for rec in self:
            if not rec.is_manual and rec.crop_registry_id:
                planned_line = rec.crop_registry_id.annual_line_ids.filtered(lambda l: l.sync_id == rec.sync_id)
                if planned_line and rec.actual_crop_area > planned_line[0].crop_planned_area:
                    raise ValidationError(f"Actual Crop Area ({rec.actual_crop_area} ha) cannot be greater than Planned Crop Area ({planned_line[0].crop_planned_area} ha).")

    @api.onchange('actual_crop_area')
    def _onchange_actual_crop_area(self):
        if self.crop_registry_id and self.actual_crop_area and self.land_info_id:
            total_actual = 0.0

            same_land_annual = self.crop_registry_id.actual_annual_line_ids.filtered(lambda l: l.land_info_id == self.land_info_id)
            total_actual += sum(same_land_annual.mapped('actual_crop_area'))

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

    is_plot_not_registered = fields.Boolean(string="Plot not registered")
    temporary_land_id = fields.Char(string="Land ID (temporary)")
    is_manual = fields.Boolean(string="Is Manual", default=True)
    is_planning = fields.Boolean(string="Is Planning", default=False)
    land_info_id = fields.Many2one('g2p.land.information', string="Land ID")
    menu_title = fields.Char(compute='_compute_menu_title')

    def _compute_menu_title(self):
        for rec in self:
            rec.menu_title = self.env.context.get('menu_title', 'Actual Details')
    region_name_id = fields.Many2one('g2p.region', string='Region')
    zone_name_id = fields.Many2one('g2p.zone', string='Zone')
    woreda_name_id = fields.Many2one('g2p.woreda', string='Woreda')
    kebele_id = fields.Many2one('g2p.kebele', string='Kebele')
    gps = fields.Char(string='GPS Coordinates')

    ownership_type = fields.Selection([('owner', 'Owner'), ('tenant', 'Tenant'), ('crop_share', 'Crop Sharing'), ('family_gift', 'Family Gift')], string="Ownership Type")
    land_area = fields.Float(string="Total Land Area (ha)")
    land_category = fields.Selection([('annual', 'Annual Crop'), ('perennial', 'Perennial Crop'), ('biennial', 'Biennial Crop')], string="Plot Category")
    soil_fertility = fields.Char(string="Soil Fertility")
    season_id = fields.Many2one('g2p.season', string="Season")

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


    crop_name_id = fields.Many2one("g2p.crop", string="Crop")
    local_name = fields.Char(string="Local Name")
    scientific_name = fields.Char(string="Scientific Name")
    collected_gc = fields.Date(string="Actual Planted Date (GC)")
    collected_ec = fields.Char(string="Actual Planted Date (EC)")
    crop_category_id = fields.Many2one("g2p.crop.category", string="Crop Category", compute="_compute_crop_category", store=True, readonly=True)
    crop_variety_id = fields.Many2one("g2p.crop.variety", string="Crop Variety")
    cropping_system = fields.Selection([
        ('mono_cropping', 'Mono-cropping'),
        ('inter_cropping', 'Inter-cropping'),
    ], string="Cropping System")
    remark = fields.Char(string="Remark")
    is_crop_changed = fields.Boolean(string="Crop Changed", compute="_compute_is_crop_changed")
    actual_crop_area = fields.Float(string="Actual Crop Area (ha)")
    actual_growth_duration = fields.Float(string="Actual Growth Duration (days)")

    actual_seed_class = fields.Selection([('local', 'Local'), ('improved', 'Improved')], string="Seed Type")
    actual_seed_source = fields.Selection([
        ('govt_woreda', 'Government / Woreda Agriculture Office'),
        ('agri_coop', 'Agricultural Cooperative / Union'),
        ('private_enterprise', 'Private Seed Enterprise'),
        ('farmer_exchange', 'Farmer-to-Farmer Exchange / Saved Seed'),
    ], string="Seed Source")
    actual_seed_qty = fields.Float(string="Actual Seed Quantity (kg)")
    actual_fertilizer_type = fields.Selection([
        ('organic', 'Organic'),
        ('inorganic', 'Inorganic'),
        ('biofertilizer', 'Bio Fertilizer')
    ], string="Actual Fertilizer Type")

    actual_fertilizer_qty = fields.Float(string="Actual Fertilizer Quantity (kg)")
    actual_fertilizer_sack = fields.Float(string="Actual Fertilizer Sacks Count", compute="_compute_actual_fertilizer_sacks", store=True)

    # Removed duplicate cluster_info_ids
    has_cluster_farming = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string="Have you done any cluster farming or related activities earlier?")
    cluster_info_ids = fields.One2many('g2p.cluster.information', 'actual_annual_line_id', string='Actual Cluster Information')


    # Survey Personnel
    surveyor_name = fields.Char(string="DA Name")
    surveyor_mobile_number = fields.Char(string="DA Mobile Number")
    supervisor_name = fields.Char(string="Supervisor Name")
    supervisor_mobile_number = fields.Char(string="Supervisor Mobile Number")
    first_approvel_status = fields.Selection([
        ('draft', 'Draft'),
    ], string="First approvel status")
    # --- Proxy fields and methods for bypassing registry form ---
    registry_planning_state = fields.Selection(related="crop_registry_id.planning_state", string="Planning State", readonly=False)
    registry_cultivation_state = fields.Selection(related="crop_registry_id.cultivation_state", string="Cultivation State", readonly=False)
    registry_sowing_state = fields.Selection(related="crop_registry_id.sowing_state", string="Sowing State", readonly=False)
    registry_harvesting_state = fields.Selection(related="crop_registry_id.harvesting_state", string="Harvesting State", readonly=False)
    registry_lifecycle_stage = fields.Selection(related="crop_registry_id.lifecycle_stage", string="Lifecycle Stage", readonly=True)
    registry_state = fields.Selection(related="crop_registry_id.state", string="State", readonly=True)
    # -----------------------------------------------------------
    actual_yield = fields.Float(string="Actual Yield (quintal)")
    cultivated_by = fields.Many2one("g2p.machinery", string="Cultivation Type")
    land_prep_method_ids = fields.Many2many("g2p.land.prep.method", string="Land Preparation Method")

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

    @api.depends('crop_name_id', 'sync_id', 'crop_registry_id.annual_line_ids.crop_name_id')
    def _compute_is_crop_changed(self):
        for rec in self:
            if not rec.crop_registry_id or not rec.sync_id or not rec.crop_name_id:
                rec.is_crop_changed = False
                continue
            planned = rec.crop_registry_id.annual_line_ids.filtered(lambda l: l.sync_id == rec.sync_id)
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
                 "crop_registry_id.annual_line_ids",
                 "crop_registry_id.annual_line_ids.crop_name_id",
                 "crop_registry_id.annual_line_ids.crop_variety_id",
                 "crop_registry_id.annual_line_ids.collected_gc",
                 "crop_registry_id.annual_line_ids.season_id")
    def _compute_is_mismatch(self):
        for rec in self:
            if not rec.crop_registry_id or not rec.crop_name_id or rec.is_manual:
                rec.is_mismatch = False
                continue
            planned_lines = rec.crop_registry_id.annual_line_ids
            if not planned_lines:
                rec.is_mismatch = False
                continue
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

    @api.constrains("collected_gc", "start_gc", "end_gc", "season_id")
    def _check_collected_gc(self):
        for rec in self:
            if rec.collected_gc:
                start_date = rec.start_gc or (rec.season_id.start_gc if rec.season_id else False)
                end_date = rec.end_gc or (rec.season_id.end_gc if rec.season_id else False)
                if start_date and end_date:
                    if not is_date_in_season(rec.collected_gc, start_date, end_date):
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

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.crop_registry_id:
                rec.crop_registry_id._sync_production_cached_values()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.crop_registry_id:
                rec.crop_registry_id._sync_production_cached_values()
        return records

