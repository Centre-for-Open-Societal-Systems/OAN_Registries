from odoo import api, fields, models

class G2PCropPestLine(models.Model):
    _name = "g2p.crop.pest.line"
    _description = "Crop Pest Details"

    infestation_id = fields.Many2one('g2p.crop.infestation.incident', string="Infestation Record", ondelete="cascade")

    pest_type = fields.Selection([
        ('insect_pests', 'Insect Pests'),
        ('rodent_pests', 'Rodent Pests'),
        ('molluscan_pests', 'Molluscan Pests'),
        ('disease_pests', 'Disease-causing Pests'),
    ], string="Pest Type")
    pest_name = fields.Char(string="Pest Name")

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
    ], string="Pesticide Type")
    pesticide_name = fields.Char(string="Pesticide Name")
    pesticide_method = fields.Selection([
        ('chemical_spray', 'Chemical Spray'),
        ('hand_picking', 'Hand Picking'),
        ('early_harvesting', 'Early Harvesting'),
    ], string="Method of Control")
    pesticide_frequency = fields.Char(string="Frequency of Application")

    @api.onchange('pesticide_method')
    def _onchange_pesticide_method(self):
        """Clear pesticide type, name, and frequency when method is not Chemical Spray."""
        if self.pesticide_method != 'chemical_spray':
            self.pesticide_type = False
            self.pesticide_name = False
            self.pesticide_frequency = False


class G2PCropWeedLine(models.Model):
    _name = "g2p.crop.weed.line"
    _description = "Crop Weed Details"

    infestation_id = fields.Many2one('g2p.crop.infestation.incident', string="Infestation Record", ondelete="cascade")

    weed_type = fields.Selection([
        ('by_life_cycle', 'By Life Cycle'),
        ('by_season', 'By Season'),
        ('by_botanical_nature', 'By Botanical Nature'),
        ('by_habitat', 'By Habitat'),
        ('by_harmfulness', 'By Harmfulness'),
        ('by_morphology', 'By Morphology'),
    ], string="Weed Type")
    weed_name = fields.Char(string="Weed Name")

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
    weedicide_name = fields.Char(string="Weedicides Name")
    pesticide_method = fields.Selection([
        ('chemical_spray', 'Chemical Spray'),
        ('hand_picking', 'Hand Picking'),
        ('early_harvesting', 'Early Harvesting'),
    ], string="Method of Control")
    pesticide_frequency = fields.Char(string="Frequency of Application")

    @api.onchange('pesticide_method')
    def _onchange_weedicide_method(self):
        """Clear weedicide type, name, and frequency when method is not Chemical Spray."""
        if self.pesticide_method != 'chemical_spray':
            self.weedicide_type = False
            self.weedicide_name = False
            self.pesticide_frequency = False


class G2PCropDiseaseLine(models.Model):
    _name = "g2p.crop.disease.line"
    _description = "Crop Disease Details"

    infestation_id = fields.Many2one('g2p.crop.infestation.incident', string="Infestation Record", ondelete="cascade")
    disease_type = fields.Selection([
        ('fungal', 'Fungal'),
        ('bacterial', 'Bacterial'),
        ('viral', 'Viral'),
        ('nematode', 'Nematode'),
        ('other', 'Other'),
    ], string="Disease Type")
    disease_name = fields.Char(string="Disease Name")
    method_of_control = fields.Selection([
        ('chemical_spray', 'Chemical Spray'),
        ('hand_picking', 'Hand Picking'),
        ('early_harvesting', 'Early Harvesting'),
    ], string="Method of Control")
    fungicide_type = fields.Selection([], string="Fungicide/Bactericide Type")
    fungicide_name = fields.Char(string="Fungicide/Bactericide Name")
    frequency_of_application = fields.Char(string="Frequency of Application")

    @api.onchange('method_of_control')
    def _onchange_method_of_control_disease(self):
        """Clear fungicide type, name, and frequency when method is not Chemical Spray."""
        if self.method_of_control != 'chemical_spray':
            self.fungicide_type = False
            self.fungicide_name = False
            self.frequency_of_application = False


class G2PCropNutrientLine(models.Model):
    _name = "g2p.crop.nutrient.line"
    _description = "Crop Nutrient Deficiency Details"

    infestation_id = fields.Many2one('g2p.crop.infestation.incident', string="Infestation Record", ondelete="cascade")
    nutrient_type = fields.Selection([
        ('macronutrient', 'Macronutrient'),
        ('secondary_nutrient', 'Secondary Nutrient'),
        ('micronutrient', 'Micronutrient'),
    ], string="Nutrient Type")
    nutrient_name = fields.Char(string="Nutrient Name")
    method_of_control = fields.Selection([
        ('soil_application', 'Soil Application'),
        ('foliar_spray', 'Foliar Spray'),
        ('organic_amendment', 'Organic Amendment'),
        ('cultural', 'Cultural (e.g. Liming, Crop Rotation)'),
    ], string="Method of Control")
    fertilizer_type = fields.Selection([
        ('organic', 'Organic'),
        ('inorganic', 'Inorganic'),
    ], string="Fertilizer/Amendment Type")
    fertilizer_name = fields.Char(string="Fertilizer/Amendment Name")
    frequency_of_application = fields.Char(string="Frequency of Application")

    @api.onchange('method_of_control')
    def _onchange_method_of_control_nutrient(self):
        """Clear fertilizer type, name, and frequency when method is not Foliar Spray."""
        if self.method_of_control != 'foliar_spray':
            self.fertilizer_type = False
            self.fertilizer_name = False
            self.frequency_of_application = False


class G2PCropClimateLine(models.Model):
    _name = "g2p.crop.climate.line"
    _description = "Crop Climate Shock Details"

    infestation_id = fields.Many2one('g2p.crop.infestation.incident', string="Infestation Record", ondelete="cascade")
    shock_type = fields.Selection([
        ('frost', 'Frost'),
        ('flood', 'Flood'),
        ('hail', 'Hail'),
        ('drought', 'Drought'),
    ], string="Shock Type")
    shock_event_name = fields.Char(string="Shock Event Name/Description")
    method_of_control = fields.Selection([
        ('drainage', 'Drainage'),
        ('irrigation', 'Irrigation'),
        ('shelter', 'Shelter/Covering'),
        ('replanting', 'Replanting'),
        ('windbreak', 'Windbreak'),
        ('none', 'None'),
    ], string="Method of Control")
    recovery_input_type = fields.Selection([
        ('soil_conditioner', 'Soil Conditioner'),
        ('replanting_material', 'Replanting Material'),
        ('irrigation_equipment', 'Irrigation Equipment'),
        ('none', 'None'),
    ], string="Recovery Input Type")
    recovery_input_name = fields.Char(string="Recovery Input Name")
    frequency_of_application = fields.Char(string="Frequency of Application")

    @api.onchange('method_of_control')
    def _onchange_method_of_control_climate(self):
        """Clear recovery input type, name, and frequency whenever the method changes."""
        self.recovery_input_type = False
        self.recovery_input_name = False
        self.frequency_of_application = False
