from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class G2PImortSource(models.Model):
    _name = "g2p.import.source"
    _description = "G2P Import Source"
    _rec_name = "name"
    _order = "name ASC"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name:
                raise ValidationError(_("Name should not be empty."))

    @api.constrains("code")
    def _check_code(self):
        for record in self:
            if not record.code:
                raise ValidationError(_("Code should not be empty."))

            existing_source = self.search_count(
                [
                    ("id", "!=", record.id),
                    ("code", "=ilike", record.code),
                ]
            )
            if existing_source:
                raise ValidationError(_("The code must be unique!"))
