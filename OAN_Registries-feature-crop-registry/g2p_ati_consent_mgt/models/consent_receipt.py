import hashlib
import hmac

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class G2PConsentReceipt(models.Model):
    _name = "g2p.consent.receipt"
    _description = "Consent Receipt"
    _order = "create_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True, readonly=True, index=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Farmer",
        required=True,
        index=True,
        ondelete="cascade",
    )
    consent_partner_id = fields.Many2one(
        "res.partner",
        string="Consent Partner",
        required=True,
        index=True,
        ondelete="restrict",
    )
    consent_request_id = fields.Many2one(
        "g2p.consent.request",
        string="Consent Request",
        required=True,
        index=True,
        ondelete="cascade",
    )
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("revoked", "Revoked"),
            ("denied", "Denied"),
            ("expired", "Expired"),
        ],
        required=True,
        default="pending",
    )
    attribute_list = fields.Text(string="Attribute List", required=True)
    attribute_payload = fields.Text(string="Attribute Payload")
    signature_algorithm = fields.Selection(
        [("hmac_sha256", "HMAC-SHA256")],
        required=True,
        default="hmac_sha256",
    )
    signature = fields.Char(required=True, index=True)
    signed_at = fields.Datetime(required=True, default=fields.Datetime.now)

    _sql_constraints = [
        (
            "g2p_consent_receipt_request_uniq",
            "unique(consent_request_id)",
            "Each consent request can have only one receipt.",
        ),
    ]

    @api.depends("consent_request_id", "status", "partner_id")
    def _compute_name(self):
        for rec in self:
            base_name = rec.consent_request_id.consent_creation_request_id or rec.partner_id.display_name or _("Receipt")
            rec.name = f"{base_name} [{rec.status or 'pending'}]"

    @api.model
    def _get_signature_secret(self):
        params = self.env["ir.config_parameter"].sudo()
        return (
            params.get_param("g2p_ati_consent_mgt.signature_secret")
            or params.get_param("database.uuid")
            or self.env.cr.dbname
        )

    @api.model
    def sign_payload(self, payload, algorithm="hmac_sha256"):
        if algorithm != "hmac_sha256":
            raise ValidationError(_("Unsupported signature algorithm: %s") % algorithm)
        payload = payload if isinstance(payload, str) else str(payload or "")
        secret = self._get_signature_secret()
        return hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

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
