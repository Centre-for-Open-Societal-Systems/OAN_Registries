from odoo import fields, models


class PhoneNumber(models.Model):
    _inherit = "g2p.phone.number"

    phone_type = fields.Selection(
        required=True,
        string="Type",
        selection=[("primary", "Primary"), ("secondary", "Secondary"), ("other", "Other")],
    )
