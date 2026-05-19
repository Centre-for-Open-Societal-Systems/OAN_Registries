from odoo import api, fields, models


class G2PCropVariety(models.Model):
    _name = "g2p.crop.variety"
    _description = "Crop Variety"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    crop_id = fields.Many2one("g2p.crop", string="Crop", required=True)
