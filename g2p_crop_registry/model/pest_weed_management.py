from odoo import api, fields, models


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





