from odoo import api, fields, models, api
import re
from odoo.exceptions import ValidationError


class G2PCrop(models.Model):
    _name = 'g2p.crop.registry'
    _description = 'G2p Crop Registry'

    # farmer_id = fields.Many2one(
    #     'res.partner',
    #     string='Farmer',required=True,
    #     domain=[('farmer_unique_id', '!=', False)],  # only show actual farmers
    #     context={'show_farmer_id': True}
    # )
    farmer_display_id = fields.Char(
        string='Farmer ID',
        store=True
    )
    zone_name_id = fields.Many2one('g2p.zone',
        string='Zone Name',
        store=True
    )
    woreda_name_id = fields.Many2one('g2p.woreda',
        string='Woreda Name',
        store=True
    )
    kebele_name = fields.Char(
        store=True
    )
    kebele_code = fields.Char(string="Kebele Code")
    land_id = fields.Char(string="Land ID")
    land_area = fields.Float(string="Land Area")
    owner_name = fields.Char(string="Owner Name")
    ownership_type = fields.Selection([
    ('private', 'Private'),
    ('leased', 'Leased'),
    ('government', 'Government')
    ])
    land_certificate = fields.Char(string="Land Certificate NO")
    soil_fertility = fields.Selection([
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High')
    ])
    current_land_use = fields.Selection([
    ('crop_farming', 'Crop Farming'),
    ('grazing', 'Grazing'),
    ('forest', 'Forest'),
    ('residential', 'Residential'),
    ('commercial', 'Commercial'),
    ('industrial', 'Industrial'),
    ('fallow', 'Fallow Land'),
    ('mixed_use', 'Mixed Use'),
    ('water_body', 'Water Body'),
    ('other', 'Other'),
    ], string="Current Land Use")
    crop_name_id = fields.Many2one('g2p.crop', string="Crop Name")
    crop_variety_id = fields.Many2one('g2p.crop.category', string="Crop Variety")
    crop_area = fields.Float(string="Crop Area")
    crop_season_id = fields.Many2one('g2p.season', string="Crop Season")
    crop_produce_min = fields.Float(string="Crop Produce Min")
    crop_produce_max = fields.Float(string="Crop Produce Max")
    crop_wholesale_min = fields.Float(string="Crop Wholesale Min")
    crop_wholesale_max = fields.Float(string="Crop Wholesale Max")
    crop_retail_min = fields.Float(string="Crop Retail Min")
    crop_retail_max = fields.Float(string="Crop Retail Max")
    crop_volume = fields.Float(string="Crop Volume")
    live_stock_type_id = fields.Many2one('g2p.livestock.type', string="Live Stock Type")
    live_stock_number = fields.Integer(string="Live Stock Number")
    live_stock_water_source = fields.Selection([
    ('river', 'River'),
    ('lake', 'Lake'),
    ('pond', 'Pond'),
    ('well', 'Well'),
    ('borewell', 'Borewell'),
    ('tap', 'Tap Water'),
    ('rainwater', 'Rain Water'),
    ('canal', 'Canal'),
    ('tank', 'Water Tank'),
    ('other', 'Other'),
    ], string="Livestock Water Source")
    cultivation_land = fields.Boolean(string="Cultivation Land")
    cultivation_area = fields.Float(string="Cultivation Area")
    cultivation_crop_name_id = fields.Many2one('g2p.crop', string="Cultivation Crop Name")
    sown_land = fields.Boolean(string="Sown Land")
    sown_area = fields.Float(string="Sown Area")
    sown_crop_name_id = fields.Many2one('g2p.crop', string="Sown Crop Name")
    harvested_land = fields.Boolean(string="Harvested Land")
    harvested_area = fields.Float(string="Harvested Area")
    harvested_crop_name_id = fields.Many2one('g2p.crop', string="Harvested Crop Name")
    irrigation_type = fields.Selection([
    ('rainfed', 'Rainfed'),
    ('drip', 'Drip'),
    ('sprinkler', 'Sprinkler'),
    ('flood', 'Flood'),
    ], string="Irrigation Type")
    surveyor_name = fields.Char(string="Surveyor Name")
    surveyor_fullname = fields.Char(string="Surveyor Full Name")
    surveyor_mobile_number = fields.Char(string="Surveyor Mobile Number")
    supervisor_name = fields.Char(string="Supervisor Name")
    supervisor_fullname = fields.Char(string="Supervisor Full Name")
    supervisor_mobile_number = fields.Char(string="Supervisor Mobile Number")
    first_approvel_status = fields.Selection([
    ('draft', 'Draft'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected')
    ], string="First approvel status")
    second_approvel_status = fields.Selection([
    ('draft', 'Draft'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected')
    ], string="Second approvel status")
    verifier_name = fields.Char(string="Verifier Name")
    verifier_mobile_number = fields.Char(string="Verifier Mobile Number")

    region_name_id = fields.Many2one('g2p.region', string="Region",
        store=True
    )
    land_plan = fields.Float(string="Land Plan")
    production_plan = fields.Float(string="Production Plan")
    productivity = fields.Float(string="Productivity")
    gps = fields.Char(string="GPS")
    total_cultivated_land = fields.Float(string="Total Cultivated Land")
    cultivated_land_by_tractor = fields.Float(string="Cultivated Land by Tractor")
    total_sown_land = fields.Float(string="Total Sown Land")
    sown_land_by_tractor = fields.Float(string="Sown Land by Tractor")
    male_farmers = fields.Integer(string="Male Farmers")
    female_farmers = fields.Integer(string="Female Farmers")
    total_farmers = fields.Integer(compute="_compute_total_farmers",string="Total Farmers")
    cluster_plan = fields.Float(string="Cluster Plan")
    cluster_collected_land = fields.Float(string="Cluster Collected Land")
    cluster_collected_quintal = fields.Float(string="Cluster Collected Quintal")
    cluster_participant_farmers = fields.Integer(string="Cluster Participant Farmers")
    collected_land = fields.Float(string="Collected Land")
    collected_land_quintal = fields.Float(string="Collected Land Quintal")
    collected_by_combiner = fields.Float(string="Collected by Combiner")
    production_in_quintal = fields.Float(string="Production in Quintal")
    total_plan = fields.Float(string="Total Plan")

    @api.depends('male_farmers', 'female_farmers')
    def _compute_total_farmers(self):
        for rec in self:
            rec.total_farmers = rec.male_farmers + rec.female_farmers

    @api.constrains('surveyor_mobile_number', 'supervisor_mobile_number', 'verifier_mobile_number')
    def _check_mobile_numbers(self):
        for rec in self:
            for field in ['surveyor_mobile_number', 'supervisor_mobile_number', 'verifier_mobile_number']:
                number = rec[field]
                if number:
                    if not re.match(r'^\d{10}$', number):
                        raise ValidationError("Please enter a valid mobile number")






