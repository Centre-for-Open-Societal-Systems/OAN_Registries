from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class G2pLang(models.Model):
    _name = "g2p.lang"

    name = fields.Char(string="Language", required=True)
    code = fields.Char(required=True, index=True)

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name:
                error_message = _("name should not empty.")
                raise ValidationError(error_message)

    @api.constrains("code")
    def _check_code(self):
        records = self.search([])
        for record in self:
            if not record.code:
                error_message = _("Code should not empty.")
                raise ValidationError(error_message)

        for rec in records:
            if self.code.lower() == rec.code.lower() and self.id != rec.id:
                raise ValidationError(_("The code must be unique!"))
