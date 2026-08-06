from odoo import api, fields, models
from odoo.exceptions import ValidationError

class G2PClusterFarmerLine(models.Model):
    _name = "g2p.cluster.farmer.line"
    _description = "Cluster Farmer Details"

    cluster_annual_line_id = fields.Many2one('g2p.annual.line', ondelete="cascade")
    cluster_info_id = fields.Many2one('g2p.cluster.information', ondelete="cascade")
    farmer_id = fields.Many2one('res.partner', string="Farmer ID", domain="[('is_farmer', '=', 'yes')]")
    fayda_id = fields.Char(string="Fayda ID")
    farmer_name = fields.Char(string="Farmer Name")
    region_id = fields.Many2one('g2p.region', string="Region")
    zone_id = fields.Many2one('g2p.zone', string="Zone")
    woreda_id = fields.Many2one('g2p.woreda', string="Woreda")
    kebele_id = fields.Many2one('g2p.kebele', string="Kebele")

    @api.onchange('farmer_id')
    def _onchange_farmer_id(self):
        if self.farmer_id:
            farmer = self.farmer_id
            self.farmer_name = farmer.name
            uid_type = self.env['g2p.id.type'].search([('name', '=', 'UID')], limit=1)
            if uid_type:
                fayda = self.env['g2p.reg.id'].search([
                    ('partner_id', '=', farmer.id),
                    ('id_type', '=', uid_type.id)
                ], limit=1)
                self.fayda_id = fayda.value if fayda else False
            else:
                self.fayda_id = False
            self.region_id = farmer.region.id if hasattr(farmer, 'region') and farmer.region else False
            self.zone_id = farmer.zone.id if hasattr(farmer, 'zone') and farmer.zone else False
            self.woreda_id = farmer.woreda.id if hasattr(farmer, 'woreda') and farmer.woreda else False
            self.kebele_id = farmer.kebele.id if hasattr(farmer, 'kebele') and farmer.kebele else False
        else:
            self.farmer_name = False
            self.fayda_id = False
            self.region_id = False
            self.zone_id = False
            self.woreda_id = False
            self.kebele_id = False

class G2PClusterInformation(models.Model):
    _name = "g2p.cluster.information"
    _description = "Cluster Information"
    _rec_name = "cluster_id"

    annual_line_id = fields.Many2one('g2p.annual.line', ondelete="cascade")
    actual_annual_line_id = fields.Many2one('g2p.annual.actual.line', ondelete="cascade")

    production_id = fields.Many2one('g2p.crop.production', ondelete="cascade")

    cluster_id = fields.Char(
        string="Cluster ID",
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('g2p.cluster') or 'New',
    )
    cluster_name = fields.Char(string="Cluster Name")

    cluster_agro_ecological_zone = fields.Selection([
        ('kur', 'Kur'),
        ('dega', 'Dega'),
        ('woina_dega', 'Woina Dega'),
        ('kolla', 'Kolla'),
        ('bereha', 'Bereha'),
    ], string="Agro Ecological Zone")

    season_id = fields.Many2one('g2p.season', string="Season")

    start_gc = fields.Date(string="Start GC", compute="_compute_season_dates", store=True)
    end_gc = fields.Date(string="End GC", compute="_compute_season_dates", store=True)

    @api.depends("season_id")
    def _compute_season_dates(self):
        for rec in self:
            if rec.season_id:
                rec.start_gc = rec.season_id.start_gc
                rec.end_gc = rec.season_id.end_gc
            else:
                rec.start_gc = False
                rec.end_gc = False
    start_month = fields.Integer(string="Start Month", compute="_compute_start_date", store=True)
    start_day = fields.Integer(string="Start Day", compute="_compute_start_date", store=True)
    end_month = fields.Integer(string="End Month", compute="_compute_end_date", store=True)
    end_day = fields.Integer(string="End Day", compute="_compute_end_date", store=True)

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

    sub_kebele = fields.Char(string="Sub-Kebele")
    gps_location = fields.Char(string="GPS Location")

    region_name_id = fields.Many2one('g2p.region', string="Region", compute="_compute_land_details", store=True, readonly=False)
    zone_name_id = fields.Many2one('g2p.zone', string="Zone", compute="_compute_land_details", store=True, readonly=False)
    woreda_name_id = fields.Many2one('g2p.woreda', string="Woreda", compute="_compute_land_details", store=True, readonly=False)
    kebele_id = fields.Many2one('g2p.kebele', string="Kebele", compute="_compute_land_details", store=True, readonly=False)

    @api.depends('annual_line_id')
    def _compute_land_details(self):
        for rec in self:
            parent_line = rec.annual_line_id
            if parent_line and hasattr(parent_line, 'land_info_id') and parent_line.land_info_id:
                land = parent_line.land_info_id
                if land.land_kebele:
                    rec.kebele_id = land.land_kebele.id
                    if land.land_kebele.woreda:
                        rec.woreda_name_id = land.land_kebele.woreda.id
                        if land.land_kebele.woreda.zone:
                            rec.zone_name_id = land.land_kebele.woreda.zone.id
                            if land.land_kebele.woreda.zone.region:
                                rec.region_name_id = land.land_kebele.woreda.zone.region.id

    cluster_area_timad = fields.Float(string="Total Cultivated Area (Timad/Kada)")
    cluster_area_hectare = fields.Float(string="Total Cultivated Area (ha)", compute="_compute_cluster_area_hectare", store=True)

    cluster_smallholders = fields.Integer(string="Number of Smallholders")
    cluster_farmer_line_ids = fields.One2many('g2p.cluster.farmer.line', 'cluster_info_id', string="Farmer Details")
    cluster_water_resource_line_ids = fields.One2many('g2p.water.resource.line', 'cluster_info_id', string="Water Source")

    cluster_plan = fields.Float(string="Plan (ha)")
    cluster_collected_land = fields.Float(string="Collected Land (ha)")
    cluster_collected_quintal = fields.Float(string="Collected Quintal")
    cluster_participant_farmers = fields.Integer(string="Participant Farmers")

    collected_land = fields.Float(string="Collected Land (ha)")
    collected_land_quintal = fields.Float(string="Collected Land (Quintal)")
    collected_by_combiner = fields.Float(string="Collected by Combiner (ha)")

    actual_cluster_plan = fields.Float(string="Actual Plan (ha)", compute='_compute_actual_cluster_values', store=True, readonly=False)
    actual_cluster_collected_land = fields.Float(string="Actual Collected Land (ha)", compute='_compute_actual_cluster_values', store=True, readonly=False)
    actual_cluster_collected_quintal = fields.Float(string="Actual Collected Quintal", compute='_compute_actual_cluster_values', store=True, readonly=False)
    actual_cluster_participant_farmers = fields.Integer(string="Actual Participant Farmers", compute='_compute_actual_cluster_values', store=True, readonly=False)
    actual_collected_land = fields.Float(string="Actual Collected Land (ha)", compute='_compute_actual_cluster_values', store=True, readonly=False)
    actual_collected_land_quintal = fields.Float(string="Actual Collected Land (Quintal)", compute='_compute_actual_cluster_values', store=True, readonly=False)
    actual_collected_by_combiner = fields.Float(string="Actual Collected by Combiner (ha)", compute='_compute_actual_cluster_values', store=True, readonly=False)

    @api.depends('cluster_plan', 'cluster_collected_land', 'cluster_collected_quintal', 'cluster_participant_farmers', 'collected_land', 'collected_land_quintal', 'collected_by_combiner')
    def _compute_actual_cluster_values(self):
        for rec in self:
            if not rec.actual_cluster_plan and rec.cluster_plan:
                rec.actual_cluster_plan = rec.cluster_plan
            if not rec.actual_cluster_collected_land and rec.cluster_collected_land:
                rec.actual_cluster_collected_land = rec.cluster_collected_land
            if not rec.actual_cluster_collected_quintal and rec.cluster_collected_quintal:
                rec.actual_cluster_collected_quintal = rec.cluster_collected_quintal
            if not rec.actual_cluster_participant_farmers and rec.cluster_participant_farmers:
                rec.actual_cluster_participant_farmers = rec.cluster_participant_farmers
            if not rec.actual_collected_land and rec.collected_land:
                rec.actual_collected_land = rec.collected_land
            if not rec.actual_collected_land_quintal and rec.collected_land_quintal:
                rec.actual_collected_land_quintal = rec.collected_land_quintal
            if not rec.actual_collected_by_combiner and rec.collected_by_combiner:
                rec.actual_collected_by_combiner = rec.collected_by_combiner

    is_actual = fields.Boolean(compute='_compute_is_actual')

    def _compute_is_actual(self):
        for rec in self:
            rec.is_actual = bool(self.env.context.get('show_actual'))

    @api.depends('cluster_area_timad')
    def _compute_cluster_area_hectare(self):
        for rec in self:
            rec.cluster_area_hectare = rec.cluster_area_timad * 0.25

    @api.onchange('cluster_area_timad')
    def _onchange_cluster_area_timad(self):
        if self.cluster_area_timad:
            attempted_area = self.cluster_area_timad * 0.25
            parent_line = None
            max_area = 0.0
            allocated_area = 0.0

            if self.annual_line_id:
                parent_line = self.annual_line_id
                max_area = parent_line.crop_planned_area
            elif self.actual_annual_line_id:
                parent_line = self.actual_annual_line_id
                max_area = parent_line.actual_crop_area

            if parent_line:
                for l in parent_line.cluster_info_ids:
                    if l.id != self.id:
                        allocated_area += l.cluster_area_hectare

                if (allocated_area + attempted_area) > max_area:
                    remaining_area = max_area - allocated_area
                    if remaining_area < 0:
                        remaining_area = 0.0

                    self.cluster_area_timad = 0.0
                    return {
                        'warning': {
                            'title': "Area Exceeded",
                            'message': "You entered %.2f ha, but only %.2f ha is remaining out of the total %.2f ha allocated to this crop (%.2f ha is already allocated to other clusters)." % (attempted_area, remaining_area, max_area, allocated_area)
                        }
                    }
    @api.onchange('cluster_farmer_line_ids', 'cluster_smallholders')
    def _onchange_farmer_count(self):
        if self.cluster_smallholders > 0 and len(self.cluster_farmer_line_ids) > self.cluster_smallholders:
            self.cluster_farmer_line_ids = self.cluster_farmer_line_ids[:-1]
            return {
                'warning': {
                    'title': 'Limit Exceeded',
                    'message': f'You can only add {self.cluster_smallholders} farmers based on the Number of Smallholders field.'
                }
            }

    @api.constrains('cluster_smallholders', 'cluster_farmer_line_ids')
    def _check_farmer_count(self):
        for rec in self:
            if rec.cluster_smallholders > 0:
                if len(rec.cluster_farmer_line_ids) != rec.cluster_smallholders:
                    raise ValidationError("The number of farmers in the Farmer List must match the Number of Smallholders.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('cluster_id', 'New') == 'New':
                vals['cluster_id'] = self.env['ir.sequence'].next_by_code('g2p.cluster') or 'New'
        return super(G2PClusterInformation, self).create(vals_list)

    @api.constrains('cluster_plan', 'cluster_area_hectare')
    def _check_cluster_plan(self):
        for rec in self:
            if rec.cluster_plan and rec.cluster_area_hectare:
                if rec.cluster_plan > rec.cluster_area_hectare:
                    raise ValidationError(f"Plan (ha) ({rec.cluster_plan}) cannot be greater than Total Cultivated Area (ha) ({rec.cluster_area_hectare}).")
