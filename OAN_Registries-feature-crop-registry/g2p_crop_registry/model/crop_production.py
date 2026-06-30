import logging
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)



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

    crop_name_id = fields.Many2one(
        "g2p.crop",
        string="Crop Name",
    )

    sync_id = fields.Char(string="Sync ID")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('g2p.crop.production') or 'New'
        return super().create(vals_list)


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
    actual_fertilizer_qty = fields.Float(string="Actual Fertilizer Qty (kg)")
    # ── Sowing ───────────────────────────────────────────────
    sowing_status = fields.Selection([
        ('sown', 'Sown'),
        ('not_sown', 'Not Sown'),
    ], string="Sowing Status")

    cluster_status = fields.Selection([
        ('clustered', 'Clustered'),
        ('independent', 'Independent'),
    ], string="Cluster Status")

    sown_area = fields.Float(string="Sown Area (ha)")
    sown_by_tractor = fields.Float(string="Sown by Tractor (ha)")
    actual_sowing_date = fields.Date(string="Actual Planted Date")



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


    expected_yield = fields.Float(string="Expected Yield (Cached)", default=0.0)
    planned_area = fields.Float(string="Planned Area (Cached)", default=0.0)
    actual_crop_area = fields.Float(string="Actual Crop Area (Cached)", default=0.0)
    actual_seed_qty = fields.Float(string="Actual Seed Qty (Cached)", default=0.0)
    actual_fertilizer_qty = fields.Float(string="Actual Fertilizer Qty (Cached)", default=0.0)

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

    @api.constrains('actual_sowing_date')
    def _check_actual_sowing_date(self):
        for rec in self:
            if rec.actual_sowing_date and rec.actual_sowing_date > fields.Date.today():
                raise ValidationError("Actual Planting Date cannot be a future date.")

    @api.onchange('actual_sowing_date')
    def _onchange_actual_sowing_date(self):
        if self.actual_sowing_date and self.actual_sowing_date > fields.Date.today():
            self.actual_sowing_date = False
            return {
                'warning': {
                    'title': 'Invalid Date',
                    'message': 'Actual Planting Date cannot be a future date. Please select today or a past date.'
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
        'actual_seed_qty', 'actual_fertilizer_qty'
    )
    def _compute_production_results(self):
        for rec in self:
            # Yield (kg/ha) = Qty Harvested (converted to kg) ÷ Area Harvested
            rec.yield_per_ha = (
                (rec.qty_harvested * 100) / rec.area_harvested
                if rec.area_harvested else 0.0
            )

            # Yield Performance % = (Actual Yield ÷ Expected Yield) × 100
            expected = rec.expected_yield
            actual = rec.qty_harvested
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
