from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class G2PCropCategory(models.Model):
    _name = "g2p.crop.category"

    name = fields.Char(required=True)
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


class G2PCrop(models.Model):
    _name = "g2p.crop"
    _description = "Crop Information Model"

    category = fields.Many2one("g2p.crop.category", required=True, index=True)
    crop_id = fields.Char(string="Crop ID", required=True, copy=False, readonly=True, default=lambda self: 'New')
    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('crop_id', 'New') == 'New':
                vals['crop_id'] = self.env['ir.sequence'].next_by_code('g2p.crop') or 'New'
        return super(G2PCrop, self).create(vals_list)

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
