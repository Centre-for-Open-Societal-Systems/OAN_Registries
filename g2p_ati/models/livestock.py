from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class G2PLivestockType(models.Model):
    _name = "g2p.livestock.type"

    name = fields.Char()
    species_code = fields.Char(required=True, index=True)
    description = fields.Text(string="Description")
    icon_url = fields.Char(string="Icon URL")
    dataset_id = fields.Integer(string="Dataset ID")

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name:
                error_message = _("name should not empty.")
                raise ValidationError(error_message)

    @api.constrains("species_code")
    def _check_species_code(self):
        records = self.search([])
        for record in self:
            if not record.species_code:
                error_message = _("Species code should not empty.")
                raise ValidationError(error_message)

        for rec in records:
            if self.species_code.lower() == rec.species_code.lower() and self.id != rec.id:
                raise ValidationError(_("The species code must be unique!"))


class G2PLivestockPopulation(models.Model):
    _name = "g2p.livestock.population"
    _description = "National livestock population totals by species and census year"

    species_code = fields.Many2one(
        "g2p.livestock.type", string="Species Code", required=True, index=True
    )
    census_year = fields.Integer(string="Census Year", required=True, index=True)
    population_total = fields.Integer(string="Population Total", required=True)
    source_record_count = fields.Integer(string="Source Record Count", default=0)

    _sql_constraints = [
        (
            "species_year_uidx",
            "unique(species_code, census_year)",
            "Population record for this species and year already exists!",
        )
    ]
