from odoo import fields, models
from odoo.exceptions import ValidationError


class G2PValidationStatus(models.Model):
    _name = "g2p.validation.status"
    _fold_name = "fold"

    fold = fields.Boolean(string="Folded in Kanban", default=False)
    name = fields.Char()

    def create(self, vals):
        # Handle both single and bulk create
        if isinstance(vals, list):
            for val in vals:
                self._check_unique_name(val)
        else:
            self._check_unique_name(vals)
        return super().create(vals)

    def _check_unique_name(self, vals):
        if vals.get("name") and self.search([("name", "ilike", vals["name"])]):
            raise ValidationError("The name must be unique")

    def write(self, vals):
        if "name" in vals:
            existing_record = self.search([("name", "ilike", vals["name"])])
            if existing_record and existing_record.id != self.id:
                raise ValidationError("The name must be unique ")
        return super().write(vals)


class NarlisIntegration(models.Model):
    _name = "narlis.integration"

    end_point_url = fields.Char()
    api_key = fields.Char()
    host_url = fields.Char()
