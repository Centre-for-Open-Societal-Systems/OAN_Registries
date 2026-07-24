from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class G2PEcologicalZone(models.Model):
    _name = "g2p.ecological.zone"
    _description = "Preferred agro-ecological zones"

    name = fields.Char(required=True)
    description = fields.Text(string="Description")


class G2PCropCategory(models.Model):
    _name = "g2p.crop.category"

    name = fields.Char(required=True)
    description = fields.Text(string="Description")

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name:
                error_message = _("name should not empty.")
                raise ValidationError(error_message)



class G2PCrop(models.Model):
    _name = "g2p.crop"
    _description = "Crop Information Model"

    category_id = fields.Many2one("g2p.crop.category", index=True, string="Category")
    name = fields.Char(required=True)
    description = fields.Text(string="Description")
    known_for = fields.Text(string="Known For")
    num_field_inspection_needed = fields.Integer(string="Field Inspection Needed", default=0)
    isolation_distance = fields.Integer(string="Isolation Distance", default=0)
    preferred_ecological_zone_id = fields.Many2one("g2p.ecological.zone", string="Preferred Ecological Zone")

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name:
                error_message = _("name should not empty.")
                raise ValidationError(error_message)
