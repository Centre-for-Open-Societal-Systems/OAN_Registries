from odoo import api, exceptions, fields, models


class Edit(models.Model):
    _name = "no.of.edits"
    _description = "Number of Edits"

    edit_amount = fields.Integer("Number of Edits", required=True)

    @api.model
    def create(self, vals):
        existing_record = self.search([], limit=1)
        if existing_record:
            raise exceptions.UserError_("Only one record allowed. Please edit the existing record.")
        else:
            return super().create(vals)
