import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
CONSENT_WEBSUB_EVENT = "WEBSUB_INDIVIDUAL_UPDATED"


class G2PDatashareConfigWebsubConsent(models.Model):
    _inherit = "g2p.datashare.config.websub"

    @api.model
    def publish_consent_payload(self, payload, config):
        config = config.sudo() if config else self.browse()
        if not config:
            _logger.warning("Consent WebSub - Missing selected WebSub configuration. Skipping publish.")
            return
        if not config.active or config.event_type != CONSENT_WEBSUB_EVENT:
            _logger.warning(
                "Consent WebSub - Selected configuration '%s' is not active or event mismatch (%s).",
                config.display_name,
                CONSENT_WEBSUB_EVENT,
            )
            return
        if config.publisher_type != "external":
            _logger.warning(
                "Consent WebSub - Selected configuration '%s' is not EXTERNAL. Skipping publish.",
                config.display_name,
            )
            return
        if self.env.context.get("test_mode"):
            config.publish_event_websub(payload)
            return

        job = config.with_delay()._publish_consent_payload_job(payload)
        _logger.info(
            "Consent WebSub - Enqueued queue job uuid=%s state=%s config_id=%s event=%s",
            getattr(job, "uuid", None),
            getattr(job, "state", None),
            config.id,
            CONSENT_WEBSUB_EVENT,
        )

    def _publish_consent_payload_job(self, payload):
        self.ensure_one()
        self.publish_event_websub(payload)


class G2PConsentRequestWebsub(models.Model):
    _inherit = "g2p.consent.request"

    def _ensure_websub_configuration_before_approval(self):
        for record in self.filtered(lambda rec: rec.status != "approved"):
            partner = record.partner_record_id.sudo()
            partner_name = partner.display_name or _("Unknown Partner")
            config = partner.consent_websub_config_id.sudo()
            if not config:
                raise UserError(
                    _(
                        "WebSub configuration is not selected for partner '%s'. "
                        "Please select a WebSub configuration before approval."
                    )
                    % partner_name
                )
            if config.publisher_type != "external":
                raise UserError(
                    _(
                        "Selected WebSub configuration '%(config)s' for partner '%(partner)s' must use publisher type 'External'."
                    )
                    % {
                        "config": config.display_name,
                        "partner": partner_name,
                    }
                )
            if config.event_type != CONSENT_WEBSUB_EVENT or not config.active:
                raise UserError(
                    _(
                        "Selected WebSub configuration '%(config)s' is invalid for partner '%(partner)s'. "
                        "Expected an active configuration with event '%(event)s'."
                    )
                    % {
                        "config": config.display_name,
                        "partner": partner_name,
                        "event": CONSENT_WEBSUB_EVENT,
                    }
                )

    def action_approve(self):
        skip_websub_publish = bool(self.env.context.get("skip_consent_websub_publish"))
        if not skip_websub_publish:
            self._ensure_websub_configuration_before_approval()
        old_statuses = {record.id: record.status for record in self}
        result = super().action_approve()
        approved_now = self.filtered(
            lambda rec: old_statuses.get(rec.id) != "approved" and rec.status == "approved"
        )
        if not skip_websub_publish:
            approved_now._publish_consent_approved_websub()
        return result

    def _publish_consent_approved_websub(self):
        datashare_obj = self.env["g2p.datashare.config.websub"].sudo()
        for record in self:
            config = record.partner_record_id.sudo().consent_websub_config_id
            payload = record._build_consent_websub_payload()
            if not payload.get("selected_data"):
                _logger.info(
                    "Consent WebSub - Skipping consent %s because selected_data is empty.",
                    record.consent_creation_request_id,
                )
                continue
            try:
                datashare_obj.publish_consent_payload(payload, config)
            except Exception:
                _logger.exception(
                    "Consent WebSub - Failed publishing consent %s.",
                    record.consent_creation_request_id,
                )

    def _build_consent_websub_payload(self):
        self.ensure_one()
        farmer = self.farmer_id.sudo()
        partner = self.partner_record_id.sudo()
        config = partner.consent_websub_config_id.sudo()
        datashare_obj = self.env["g2p.datashare.config.websub"].sudo()

        published_fields = config._get_consent_shared_data_fields(self) if config else self.allowed_data_field_ids
        payload_builder = config if config else datashare_obj
        selected_data = payload_builder._build_data_field_payload(farmer, published_fields)

        now = fields.Datetime.now()
        return {
            "source": "g2p_ati_consent_mgt",
            "event_type": CONSENT_WEBSUB_EVENT,
            "published_at": fields.Datetime.to_string(now),
            "consent": {
                "id": self.id,
                "consent_creation_request_id": self.consent_creation_request_id,
                "consent_type": self.consent_type,
                "status": self.status,
                "approved_at": fields.Datetime.to_string(self.approved_at) if self.approved_at else None,
                "validity_from": fields.Datetime.to_string(self.validity_from) if self.validity_from else None,
                "validity_to": fields.Datetime.to_string(self.validity_to) if self.validity_to else None,
                "requested_field_codes": self.allowed_data_field_ids.mapped("code"),
                "published_field_codes": published_fields.mapped("code"),
                "data_field_mode": config.data_field_mode if config else "dynamic",
            },
            "consent_partner": {
                "id": partner.id,
                "name": partner.display_name,
                "ref": partner.ref,
                "websub_config_id": config.id if config else False,
                "websub_config_name": config.display_name if config else False,
            },
            "farmer": {
                "id": farmer.id,
                "farmer_id": farmer.farmer_id,
                "name": farmer.display_name,
            },
            "selected_data": selected_data,
        }
