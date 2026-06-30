from odoo import api, fields, models
from odoo.exceptions import ValidationError


class G2PSeason(models.Model):
    _name = "g2p.season"
    _description = "Season"

    name = fields.Char(required=True)
    start_gc = fields.Date(index=True, string="Start GC", required=True)
    end_gc = fields.Date(required=True, string="End GC")
    start_month = fields.Integer(compute="_compute_start_date", store=True)
    start_day = fields.Integer(compute="_compute_start_date", store=True)
    end_month = fields.Integer(compute="_compute_end_date", store=True)
    end_day = fields.Integer(compute="_compute_end_date", store=True)

    @api.depends("start_gc")
    def _compute_start_date(self):
        """Computes start month and start day."""
        for record in self:
            if record.start_gc:
                record.start_month = record.start_gc.month
                record.start_day = record.start_gc.day
            else:
                record.start_month = record.start_day = 0

    @api.depends("end_gc")
    def _compute_end_date(self):
        """Computes end month and end day."""
        for record in self:
            if record.end_gc:
                record.end_month = record.end_gc.month
                record.end_day = record.end_gc.day
            else:
                record.end_month = record.end_day = 0

    @api.constrains("start_gc", "end_gc")
    def _check_valid_season_dates(self):
        """Ensure the start date is before the end date."""
        for record in self:
            if record.start_gc and record.end_gc and record.start_gc > record.end_gc:
                raise ValidationError(_("Start date must be before end date."))

    @api.constrains("start_gc", "end_gc")
    def _check_overlapping_seasons(self):
        """Ensure that no two seasons overlap, ignoring the year."""
        for record in self:
            overlapping_seasons = self.search(
                [
                    ("id", "!=", record.id),
                    "|",
                    "&",
                    ("start_month", "<=", record.end_month),
                    ("end_month", ">=", record.start_month),
                    "&",
                    ("start_month", "<=", record.end_month),
                    ("end_month", ">=", record.start_month),
                ]
            )

            if overlapping_seasons:
                raise ValidationError(
                    _(
                        f"Season '{record.name}' overlaps with '{', '.join(overlapping_seasons.mapped('name'))}' (ignoring year)."
                    )
                )
