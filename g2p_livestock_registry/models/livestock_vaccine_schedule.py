from odoo import api, fields, models, _


class G2PLivestockVaccineSchedule(models.Model):
    """LR-07: Configurable vaccination schedule reference data."""
    _name = 'g2p.livestock.vaccine.schedule'
    _description = 'Vaccine Schedule Configuration'
    _order = 'vaccine_name'

    vaccine_name = fields.Char(
        string='Vaccine Name',
        required=True,
        help="Must match the Vaccine Type/Name entered on a Vaccination "
             "record (case-insensitive) for auto-calculation to apply."
    )

    # ==================== CHANGED TO RELATIONAL FIELD ====================
    species_id = fields.Many2one(
        'g2p.livestock.type',
        string='Species',
        help="Leave blank if this schedule applies to ALL species.",
        ondelete='restrict'
    )
    # =====================================================================

    interval_days = fields.Integer(
        string='Repeat Every (Days)',
        required=True,
        default=365,
        help="Number of days after vaccination before it's due again."
    )

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('schedule_uniq', 'unique(vaccine_name, species_id)',
         'A schedule for this Vaccine + Species combination already exists.'),
    ]

    @api.depends('vaccine_name', 'species_id', 'interval_days')
    def _compute_display_name(self):
        for rec in self:
            species_label = rec.species_id.name if rec.species_id else 'All Species'
            rec.display_name = "%s (%s) — every %s days" % (
                rec.vaccine_name or _('New'),
                species_label,
                rec.interval_days
            )