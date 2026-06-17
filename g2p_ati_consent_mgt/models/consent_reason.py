from odoo import fields, models


class G2PConsentReason(models.Model):
    _name = "g2p.consent.reason"
    _description = "Consent Reason"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    consent_request_ids = fields.One2many("g2p.consent.request", "consent_reason_id", string="Consent Requests")

    _sql_constraints = [
        ("g2p_consent_reason_name_uniq", "unique(name)", "Consent reason must be unique."),
    ]
