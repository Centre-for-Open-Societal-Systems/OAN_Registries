from odoo import api, fields, models
from odoo.exceptions import ValidationError


class G2PLandInformation(models.Model):
    _name = "g2p.land.information"
    _rec_name = "partner_id"

    partner_id = fields.Many2one("res.partner", string="Farmer", required=True, index=True)
    farmer_id = fields.Char(related="partner_id.farmer_id", string="Farmer ID", readonly=True)
    total_land_area = fields.Float(string="Area In Hectare",digits=(16, 6), required=True, default=0.0)
    land_certificate = fields.Many2one("storage.file")
    certficate_provided = fields.Boolean()
    land_id = fields.Char(string="Land ID", index=True)
    remark = fields.Char(string="Remark")
    ownership_type = fields.Selection(
        selection=[("owner", "Owner"), ("tenant", "Tenant"), ("crop_share", "Crop Sharing"), ("family_gift", "Family Gift")], required=True
    )
    document_slug = fields.Char(related="land_certificate.slug")
    document_mimetype = fields.Char(related="land_certificate.mimetype")
    document_url = fields.Char(related="land_certificate.url")
    document_name = fields.Char(related="land_certificate.name")
    document_id = fields.Integer(related="land_certificate.id")
    land_kebele = fields.Many2one('g2p.kebele', string="Land Kebele is in")


    @api.onchange("total_land_area")
    def _onchange_total_land_area(self):
        if self.total_land_area < 0.0:
            error_msg = "Area should not be negative"
            raise ValidationError(error_msg)
