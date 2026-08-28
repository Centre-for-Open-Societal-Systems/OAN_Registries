from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class G2PConsentFeedback(models.Model):
    _name = "g2p.consent.feedback"
    _description = "Bank Feedback on Consent Request"
    _order = "create_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True, readonly=True, index=True)

    consent_request_id = fields.Many2one(
        "g2p.consent.request",
        string="Consent Request",
        required=True,
        index=True,
        ondelete="cascade",
    )
    # The bank / consent partner giving feedback. Reuses the same
    # res.partner (is_consent_parent=True) concept already used by
    # g2p.consent.request.partner_record_id and g2p.consent.receipt.consent_partner_id.
    bank_partner_id = fields.Many2one(
        "res.partner",
        string="Bank",
        required=True,
        index=True,
        ondelete="restrict",
        domain="[('is_consent_parent', '=', True)]",
    )
    farmer_id = fields.Many2one(
        "res.partner",
        string="Farmer",
        related="consent_request_id.farmer_id",
        store=True,
        readonly=True,
    )
    feedback_type = fields.Selection(
        [
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
            ("used_for_loan", "Used For Loan"),
            ("data_incomplete", "Data Incomplete"),
            ("other", "Other"),
        ],
        required=True,
        default="accepted",
    )
    remarks = fields.Text(string="Remarks")
    submitted_by_user_id = fields.Many2one(
        "res.users",
        string="Submitted By",
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    submitted_at = fields.Datetime(default=fields.Datetime.now, readonly=True)

    @api.depends("consent_request_id", "bank_partner_id", "feedback_type")
    def _compute_name(self):
        for rec in self:
            base_name = (
                rec.consent_request_id.consent_creation_request_id
                or rec.consent_request_id.display_name
                or _("Consent Feedback")
            )
            rec.name = f"{base_name} [{rec.feedback_type or 'accepted'}]"

    @api.constrains("consent_request_id", "bank_partner_id")
    def _check_bank_matches_consent_partner(self):
        for rec in self:
            if (
                rec.consent_request_id
                and rec.bank_partner_id
                and rec.consent_request_id.partner_record_id
                and rec.consent_request_id.partner_record_id != rec.bank_partner_id
            ):
                raise ValidationError(
                    _("Feedback bank must match the consent request's partner.")
                )

    def action_open_consent_request(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent Request"),
            "res_model": "g2p.consent.request",
            "res_id": self.consent_request_id.id,
            "view_mode": "form",
            "target": "current",
        }
