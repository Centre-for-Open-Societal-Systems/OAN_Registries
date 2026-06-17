import json
import logging
from uuid import uuid4

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

FACE_MATCH_STATUS_SELECTION = [
    ("not_attempted", "Not Attempted"),
    ("matched", "Matched"),
    ("not_matched", "Not Matched"),
    ("no_reference", "No Reference Image"),
    ("no_face_detected", "No Face Detected"),
    ("error", "Error"),
]

FAYDA_OTP_STATUS_SELECTION = [
    ("not_requested", "Not Requested"),
    ("requested", "Requested"),
    ("verified", "Verified"),
    ("failed", "Failed"),
    ("error", "Error"),
]


class G2PConsentRequest(models.Model):
    _name = "g2p.consent.request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Consent Request"
    _order = "create_date desc"

    name = fields.Char(compute="_compute_name", store=True)
    consent_creation_request_id = fields.Char(required=True, default=lambda self: str(uuid4()), copy=False, index=True)
    consent_type = fields.Selection(
        [("baseline", "Baseline"), ("specific", "Specific")],
        required=True,
        default="specific",
    )
    partner_record_id = fields.Many2one(
        "res.partner",
        required=True,
        string="Partner",
        domain="[('is_consent_parent', '=', True)]",
    )
    partner_id = fields.Char(string="Partner ID", compute="_compute_partner_id", store=True, readonly=True)
    partner_code = fields.Char(related="partner_record_id.ref", string="Partner Code", store=True, readonly=True)
    farmer_id = fields.Many2one(
        "res.partner",
        string="Farmer",
        required=True,
        domain="[('is_registrant', '=', True), ('is_group', '=', False), ('state', '=', 'approved')]",
    )
    allowed_data_field_ids = fields.Many2many(
        "g2p.consent.data.field",
        "g2p_consent_request_data_field_rel",
        "consent_id",
        "field_id",
        string="Allowed Data Points",
        required=True,
        help="Requested fields for this consent.",
    )
    consent_provider_register = fields.Char()
    consent_provider_person_id = fields.Char()
    consent_target_object_ids = fields.Text(help='JSON list[dict], e.g. [{"register": ["<ids>"]}]')
    attribute_lists = fields.Text(help='JSON list[dict], e.g. [{"register": ["<fields>"]}]')
    consent_reason_id = fields.Many2one(
        "g2p.consent.reason",
        string="Consent Reason",
        ondelete="restrict",
    )
    purpose = fields.Text()
    validity_from = fields.Datetime(string="Valid From")
    validity_to = fields.Datetime(string="Valid Until")
    originated_from = fields.Selection(
        [
            ("beneficiary", "Beneficiary"),
            ("agent", "Agent"),
            ("staff", "Staff"),
            ("partner", "Partner"),
        ]
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
        default="pending",
        required=True,
    )
    created_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    approved_at = fields.Datetime(readonly=True)
    rejected_at = fields.Datetime(readonly=True)
    expired_at = fields.Datetime(readonly=True)
    rejection_reason = fields.Text()
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "g2p_consent_request_attachment_rel",
        "consent_id",
        "attachment_id",
        string="Consent Attachments",
    )
    receipt_ids = fields.One2many(
        "g2p.consent.receipt",
        "consent_request_id",
        string="Receipts",
        readonly=True,
    )
    receipt_count = fields.Integer(compute="_compute_receipt_count", string="Receipt Count")
    requester_user_id = fields.Many2one(
        "res.users",
        string="Requested By",
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    portal_capture_image = fields.Binary(string="Portal Capture Photo", attachment=True)
    portal_capture_image_filename = fields.Char(string="Portal Capture Filename")
    portal_capture_taken_at = fields.Datetime(string="Portal Capture Taken At")
    portal_capture_latitude = fields.Float(string="Portal Capture Latitude", digits=(10, 7))
    portal_capture_longitude = fields.Float(string="Portal Capture Longitude", digits=(10, 7))
    portal_capture_accuracy_m = fields.Float(string="Portal Capture Accuracy (m)")
    face_match_status = fields.Selection(
        FACE_MATCH_STATUS_SELECTION,
        string="Face Match Status",
        default="not_attempted",
        readonly=True,
        copy=False,
    )
    face_match_distance = fields.Float(string="Face Match Distance", digits=(16, 4), readonly=True, copy=False)
    face_match_threshold = fields.Float(string="Face Match Threshold", digits=(16, 4), readonly=True, copy=False)
    face_match_checked_at = fields.Datetime(string="Face Match Checked At", readonly=True, copy=False)
    face_match_message = fields.Text(string="Face Match Message", readonly=True, copy=False)
    auto_approved_via_face_match = fields.Boolean(
        string="Auto Approved via Face Match",
        readonly=True,
        copy=False,
    )
    fayda_otp_status = fields.Selection(
        FAYDA_OTP_STATUS_SELECTION,
        string="Fayda OTP Status",
        default="not_requested",
        readonly=True,
        copy=False,
    )
    fayda_otp_transaction_id = fields.Char(string="Fayda OTP Transaction ID", readonly=True, copy=False)
    fayda_otp_identifier = fields.Char(string="Fayda OTP Identifier", readonly=True, copy=False)
    fayda_otp_identifier_type = fields.Char(string="Fayda OTP Identifier Type", readonly=True, copy=False)
    fayda_otp_masked_mobile = fields.Char(string="Fayda OTP Masked Mobile", readonly=True, copy=False)
    fayda_otp_verified_at = fields.Datetime(string="Fayda OTP Verified At", readonly=True, copy=False)
    fayda_otp_message = fields.Text(string="Fayda OTP Message", readonly=True, copy=False)
    auto_approved_via_otp = fields.Boolean(
        string="Auto Approved via Fayda OTP",
        readonly=True,
        copy=False,
    )
    portal_capture_image_preview_html = fields.Html(
        string="Portal Capture Photo",
        compute="_compute_portal_capture_image_preview_html",
        sanitize=False,
    )

    _sql_constraints = [
        (
            "g2p_consent_creation_request_id_uniq",
            "unique(consent_creation_request_id)",
            "Consent creation request ID must be unique.",
        ),
    ]

    @api.depends("farmer_id", "partner_record_id")
    def _compute_name(self):
        for rec in self:
            farmer_label = rec.farmer_id.display_name or _("Unknown Farmer")
            partner_label = rec.partner_record_id.display_name or _("Unknown Partner")
            rec.name = f"{farmer_label} - {partner_label}"

    @api.depends("partner_record_id")
    def _compute_partner_id(self):
        for rec in self:
            rec.partner_id = str(rec.partner_record_id.id) if rec.partner_record_id else False

    @api.depends("receipt_ids")
    def _compute_receipt_count(self):
        grouped_data = self.env["g2p.consent.receipt"].sudo().read_group(
            [("consent_request_id", "in", self.ids)],
            ["consent_request_id"],
            ["consent_request_id"],
        )
        counts = {
            item["consent_request_id"][0]: item["consent_request_id_count"]
            for item in grouped_data
            if item.get("consent_request_id")
        }
        for rec in self:
            rec.receipt_count = counts.get(rec.id, 0)

    @api.depends("portal_capture_image")
    def _compute_portal_capture_image_preview_html(self):
        for rec in self:
            if rec.id and rec.portal_capture_image:
                image_url = f"/web/image/g2p.consent.request/{rec.id}/portal_capture_image"
                captured_at = fields.Datetime.to_string(rec.portal_capture_taken_at) if rec.portal_capture_taken_at else "-"
                rec.portal_capture_image_preview_html = (
                    f'<a href="{image_url}" target="_blank" rel="noopener" title="Open full image">'
                    f'<img src="{image_url}" '
                    f'style="max-width:120px;max-height:120px;border:1px solid #d9d9d9;'
                    f'border-radius:4px;cursor:zoom-in;"/>'
                    f"</a>"
                    f'<div style="margin-top:8px;white-space:nowrap;min-width:260px;">'
                    f"<strong>Captured At:</strong> {captured_at}"
                    f"</div>"
                )
            else:
                rec.portal_capture_image_preview_html = False

    @api.constrains("validity_from", "validity_to")
    def _check_validity_range(self):
        for rec in self:
            if rec.validity_from and rec.validity_to and rec.validity_from > rec.validity_to:
                raise ValidationError(_("Valid From must be earlier than or equal to Valid Until."))

    @api.constrains("consent_reason_id", "purpose", "allowed_data_field_ids", "attachment_ids")
    def _check_required_request_details(self):
        for rec in self:
            if not rec.consent_reason_id and not (rec.purpose or "").strip():
                raise ValidationError(_("Consent reason is required for consent requests."))
            if not rec.allowed_data_field_ids:
                raise ValidationError(_("At least one data field is required for consent requests."))
            if not rec.attachment_ids:
                raise ValidationError(_("An attachment is required for consent requests."))

    @api.constrains("partner_record_id", "allowed_data_field_ids")
    def _check_partner_allowed_data_fields(self):
        for rec in self:
            partner_allowed_fields = rec.partner_record_id.allowed_data_field_ids
            if not partner_allowed_fields:
                continue
            blocked_fields = rec.allowed_data_field_ids - partner_allowed_fields
            if blocked_fields:
                raise ValidationError(
                    _(
                        "These data fields are not allowed for partner '%(partner)s': %(fields)s"
                    )
                    % {
                        "partner": rec.partner_record_id.display_name,
                        "fields": ", ".join(blocked_fields.mapped("name")),
                    }
                )

    def _set_status(self, status, timestamp_field=None):
        vals = {"status": status}
        if timestamp_field:
            vals[timestamp_field] = fields.Datetime.now()
        self.write(vals)

    def _build_attribute_lists_payload(self) -> str:
        self.ensure_one()
        tokens = []
        for data_field in self.allowed_data_field_ids:
            token = (data_field.code or data_field.name or "").strip()
            if token:
                tokens.append(token)
        tokens = list(dict.fromkeys(tokens))
        if not tokens:
            return "[]"
        return json.dumps([{"register": tokens}], ensure_ascii=False)

    def _extract_attribute_tokens(self) -> list[str]:
        self.ensure_one()
        raw = (self.attribute_lists or "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return []
        if not isinstance(parsed, list):
            return []
        tokens: list[str] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            for value in item.values():
                if isinstance(value, list):
                    tokens.extend([str(v).strip() for v in value if str(v).strip()])
                elif value is not None and str(value).strip():
                    tokens.append(str(value).strip())
        return list(dict.fromkeys(tokens))

    def _sync_attribute_lists_from_allowed_fields(self):
        for rec in self:
            payload = rec._build_attribute_lists_payload()
            if rec.attribute_lists != payload:
                rec.with_context(_skip_attribute_lists_sync=True).write({"attribute_lists": payload})

    def _sync_allowed_fields_from_attribute_lists(self):
        data_field_model = self.env["g2p.consent.data.field"]
        for rec in self:
            tokens = rec._extract_attribute_tokens()
            current_ids = set(rec.allowed_data_field_ids.ids)
            if not tokens:
                if current_ids:
                    rec.with_context(_skip_attribute_lists_sync=True).write({"allowed_data_field_ids": [(5, 0, 0)]})
                continue
            by_code = data_field_model.search([("code", "in", tokens)])
            remaining = [t for t in tokens if t not in set(by_code.mapped("code"))]
            by_name = data_field_model.search([("name", "in", remaining)]) if remaining else data_field_model.browse()
            target_ids = set((by_code | by_name).ids)
            if current_ids != target_ids:
                rec.with_context(_skip_attribute_lists_sync=True).write({"allowed_data_field_ids": [(6, 0, list(target_ids))]})

    @api.onchange("allowed_data_field_ids")
    def _onchange_allowed_data_field_ids_sync_attribute_lists(self):
        self._sync_attribute_lists_from_allowed_fields()

    @api.onchange("attribute_lists")
    def _onchange_attribute_lists_sync_allowed_fields(self):
        self._sync_allowed_fields_from_attribute_lists()

    def _build_receipt_attribute_payload(self):
        self.ensure_one()
        if hasattr(self, "_build_consent_websub_payload"):
            payload = self._build_consent_websub_payload() or {}
            selected_data = payload.get("selected_data") or {}
            return json.dumps(selected_data, ensure_ascii=False, sort_keys=True, default=str)
        return "{}"

    def _prepare_consent_receipt_values(self):
        self.ensure_one()
        attribute_list = (self.attribute_lists or "").strip() or self._build_attribute_lists_payload()
        attribute_payload = self._build_receipt_attribute_payload()
        signature_algorithm = "hmac_sha256"
        signed_at = (
            self.approved_at
            or self.rejected_at
            or self.expired_at
            or self.created_at
            or fields.Datetime.now()
        )
        signature_source = json.dumps(
            {
                "consent_request_id": self.id,
                "consent_creation_request_id": self.consent_creation_request_id,
                "partner_id": self.farmer_id.id,
                "consent_partner_id": self.partner_record_id.id,
                "status": self.status,
                "attribute_list": attribute_list,
                "attribute_payload": attribute_payload,
                "signed_at": fields.Datetime.to_string(signed_at),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        signature = self.env["g2p.consent.receipt"].sudo().sign_payload(
            signature_source, signature_algorithm
        )
        return {
            "partner_id": self.farmer_id.id,
            "consent_partner_id": self.partner_record_id.id,
            "consent_request_id": self.id,
            "status": self.status,
            "attribute_list": attribute_list,
            "attribute_payload": attribute_payload,
            "signature_algorithm": signature_algorithm,
            "signature": signature,
            "signed_at": signed_at,
        }

    def _sync_consent_receipts(self):
        receipt_obj = self.env["g2p.consent.receipt"].sudo()
        for rec in self:
            existing = receipt_obj.search([("consent_request_id", "=", rec.id)], limit=1)
            if rec.status == "pending":
                if existing:
                    existing.unlink()
                continue

            if not rec.farmer_id or not rec.partner_record_id:
                continue
            vals = rec._prepare_consent_receipt_values()
            if existing:
                existing.write(vals)
            else:
                receipt_obj.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        reason_model = self.env["g2p.consent.reason"].sudo()
        for vals in vals_list:
            reason_id = vals.get("consent_reason_id")
            if reason_id and not (vals.get("purpose") or "").strip():
                reason = reason_model.browse(reason_id)
                if reason.exists():
                    vals["purpose"] = reason.name
        if self.env.context.get("_skip_attribute_lists_sync"):
            return super().create(vals_list)
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            if "allowed_data_field_ids" in vals and "attribute_lists" not in vals:
                rec._sync_attribute_lists_from_allowed_fields()
            elif "attribute_lists" in vals and "allowed_data_field_ids" not in vals:
                rec._sync_allowed_fields_from_attribute_lists()
            elif "allowed_data_field_ids" in vals and "attribute_lists" in vals:
                rec._sync_attribute_lists_from_allowed_fields()
        records._sync_consent_receipts()
        return records

    def write(self, vals):
        vals = dict(vals)
        reason_id = vals.get("consent_reason_id")
        if reason_id and "purpose" not in vals:
            reason = self.env["g2p.consent.reason"].sudo().browse(reason_id)
            if reason.exists():
                vals["purpose"] = reason.name
        if self.env.context.get("_skip_attribute_lists_sync"):
            return super().write(vals)
        result = super().write(vals)
        if "allowed_data_field_ids" in vals and "attribute_lists" not in vals:
            self._sync_attribute_lists_from_allowed_fields()
        elif "attribute_lists" in vals and "allowed_data_field_ids" not in vals:
            self._sync_allowed_fields_from_attribute_lists()
        elif "allowed_data_field_ids" in vals and "attribute_lists" in vals:
            self._sync_attribute_lists_from_allowed_fields()
        receipt_trigger_fields = {
            "status",
            "allowed_data_field_ids",
            "attribute_lists",
            "farmer_id",
            "partner_record_id",
            "approved_at",
            "rejected_at",
            "expired_at",
            "portal_capture_image",
            "portal_capture_taken_at",
            "portal_capture_latitude",
            "portal_capture_longitude",
            "portal_capture_accuracy_m",
        }
        if receipt_trigger_fields.intersection(vals) and not self.env.context.get("_skip_receipt_sync"):
            self._sync_consent_receipts()
        return result

    def action_approve(self):
        notify_records = self.filtered(lambda rec: rec.status != "approved")
        self._set_status("approved", "approved_at")
        notify_records._notify_requester_approved()

    def _notify_requester_approved(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
        for rec in self:
            requester_user = rec.requester_user_id
            requester_partner = requester_user.partner_id if requester_user else False
            if not requester_partner:
                continue

            review_path = f"/consent/management/review/{rec.id}?view=table#review_request"
            review_url = f"{base_url}{review_path}" if base_url else review_path
            subject = _("Consent Request Approved")
            body = _(
                "Your consent request %(request)s for farmer %(farmer)s has been approved. "
                "<a href=\"%(url)s\">View request</a>."
            ) % {
                "request": rec.consent_creation_request_id or rec.display_name,
                "farmer": rec.farmer_id.display_name or "",
                "url": review_url,
            }
            try:
                rec.sudo().message_notify(
                    partner_ids=[requester_partner.id],
                    subject=subject,
                    body=body,
                    email_layout_xmlid="mail.mail_notification_light",
                )
            except Exception:
                _logger.exception(
                    "Failed to notify requester for approved consent request id=%s user_id=%s",
                    rec.id,
                    requester_user.id if requester_user else None,
                )

    def action_reject(self):
        self._set_status("rejected", "rejected_at")

    def action_revoke(self):
        self._set_status("revoked", "expired_at")

    def action_expire(self):
        self._set_status("expired", "expired_at")

    def action_set_pending(self):
        self.with_context(_skip_receipt_sync=True).write(
            {
                "status": "pending",
                "approved_at": False,
                "rejected_at": False,
                "expired_at": False,
                "rejection_reason": False,
                "auto_approved_via_face_match": False,
                "auto_approved_via_otp": False,
            }
        )
        self.mapped("receipt_ids").sudo().unlink()

    def action_view_receipts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent Receipts"),
            "res_model": "g2p.consent.receipt",
            "view_mode": "tree,form",
            "domain": [("consent_request_id", "=", self.id)],
            "context": {"default_consent_request_id": self.id},
        }
