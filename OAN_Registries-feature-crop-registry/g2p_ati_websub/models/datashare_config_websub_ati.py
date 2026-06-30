import logging

# Part of OpenG2P. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class G2PDatashareConfigWebsubATI(models.Model):
    _inherit = "g2p.datashare.config.websub"

    publisher_type = fields.Selection(
        selection=[("internal", "Internal"), ("external", "External")],
        string="Publisher Type",
        required=True,
        default="internal",
        index=True,
        help=(
            "Internal: used for automatic real-time sharing from approved res.partner records. "
            "External: used for partner-specific/consent-driven sharing."
        ),
    )

    def with_delay(
        self,
        priority=None,
        eta=None,
        max_retries=None,
        description=None,
        channel=None,
        identity_key=None,
    ):
        # Prevent base WebSub hook from creating queue jobs; ATI module controls enqueueing.
        if self.env.context.get("ati_skip_base_websub_publish"):
            _logger.info("ATI WebSub Debug - with_delay bypassed for base hook context")
            return self
        if max_retries is None:
            max_retries = 1
        return super().with_delay(
            priority=priority,
            eta=eta,
            max_retries=max_retries,
            description=description,
            channel=channel,
            identity_key=identity_key,
        )

    def get_full_record_data(self, records):
        self.ensure_one()
        if not self.shared_data_field_ids:
            return super().get_full_record_data(records)

        payloads = []
        for record in records.sudo():
            payloads.append(self._build_data_field_payload(record, self.shared_data_field_ids))

        _logger.info(
            "ATI WebSub - Built record payload from configured data fields config_id=%s record_count=%s field_count=%s",
            self.id,
            len(records),
            len(self.shared_data_field_ids),
        )
        return payloads

    def _extract_partner_id_from_payload(self, data):
        if not isinstance(data, dict):
            return None
        farmer_data = data.get("farmer")
        if isinstance(farmer_data, dict) and farmer_data.get("id"):
            return farmer_data.get("id")
        partner_data = data.get("groupData", data)
        if not isinstance(partner_data, dict):
            return None
        nested_farmer = partner_data.get("farmer")
        if isinstance(nested_farmer, dict) and nested_farmer.get("id"):
            return nested_farmer.get("id")
        return partner_data.get("id")

    def _mark_successful_share(self, partner_id):
        self.ensure_one()
        if not partner_id:
            return
        partner = self.env["res.partner"].browse(partner_id).sudo().exists()
        if not partner:
            return
        partner._mark_websub_share_success(self)

    @api.model
    def publish_event(self, event_type, data: dict, condition_override=None):
        if self.env.context.get("ati_skip_base_websub_publish"):
            _logger.info(
                "ATI WebSub Debug - Skipping base hook publish_event event=%s partner_id=%s",
                event_type,
                self._extract_partner_id_from_payload(data),
            )
            return

        partner_id = self._extract_partner_id_from_payload(data)
        publishers = self.get_publishers(event_type)
        _logger.info(
            "ATI WebSub Debug - Executing publish_event event=%s partner_id=%s publisher_count=%s "
            "data_keys=%s condition_override=%s",
            event_type,
            partner_id,
            len(publishers),
            sorted(data.keys()) if isinstance(data, dict) else None,
            bool(condition_override),
        )
        if not publishers:
            _logger.warning(
                "ATI WebSub Debug - No active WebSub publishers found for event=%s partner_id=%s",
                event_type,
                partner_id,
            )
        result = super().publish_event(event_type, data, condition_override=condition_override)
        _logger.info(
            "ATI WebSub Debug - Finished publish_event event=%s partner_id=%s",
            event_type,
            partner_id,
        )
        return result

    def publish_by_publisher(self, data: dict, condition_override=None):
        self.ensure_one()
        partner_id = data.get("id") if isinstance(data, dict) else None
        if partner_id:
            partner = self.env["res.partner"].browse(partner_id).sudo()
            if not partner.exists():
                _logger.warning(
                    "ATI WebSub - Partner ID %s does not exist, skipping publish for config_id=%s",
                    partner_id,
                    self.id,
                )
                return
            if not partner.is_registrant or partner.state != "approved":
                _logger.info(
                    "ATI WebSub - Skipping publish for config_id=%s partner_id=%s is_registrant=%s state=%s",
                    self.id,
                    partner.id,
                    partner.is_registrant,
                    partner.state,
                )
                return
        return super(
            G2PDatashareConfigWebsubATI,
            self.with_context(g2p_websub_tracking_partner_id=partner_id),
        ).publish_by_publisher(data, condition_override=condition_override)

    @api.model
    def publish_event_internal(self, event_type, data: dict, condition_override=None):
        partner_id = self._extract_partner_id_from_payload(data)
        publishers = self.search(
            [
                ("event_type", "=", event_type),
                ("active", "=", True),
                ("publisher_type", "=", "internal"),
            ]
        )
        _logger.info(
            "ATI WebSub Debug - Executing publish_event_internal event=%s partner_id=%s publisher_count=%s",
            event_type,
            partner_id,
            len(publishers),
        )
        if not publishers:
            _logger.warning(
                "ATI WebSub Debug - No INTERNAL WebSub publishers found for event=%s partner_id=%s",
                event_type,
                partner_id,
            )
            return
        for publisher in publishers:
            publisher.publish_by_publisher(data, condition_override=condition_override)
        _logger.info(
            "ATI WebSub Debug - Finished publish_event_internal event=%s partner_id=%s",
            event_type,
            partner_id,
        )


    def publish_event_websub(self, data):
        self.ensure_one()
        is_consent_payload = isinstance(data, dict) and data.get("source") == "g2p_ati_consent_mgt"
        _logger.info(
            "ATI WebSub Debug - publish_event_websub start config_id=%s config_name=%s event_type=%s partner_id=%s source=%s",
            self.id,
            self.name,
            self.event_type,
            self._extract_partner_id_from_payload(data),
            data.get("source") if isinstance(data, dict) else None,
        )
        try:
            result = super().publish_event_websub(data)
            partner_id = self.env.context.get("g2p_websub_tracking_partner_id")
            if is_consent_payload and not partner_id:
                partner_id = self._extract_partner_id_from_payload(data)
            self._mark_successful_share(partner_id)
            _logger.info(
                "ATI WebSub Debug - publish_event_websub success config_id=%s event_type=%s partner_id=%s",
                self.id,
                self.event_type,
                self._extract_partner_id_from_payload(data),
            )
            return result
        except Exception:
            _logger.exception(
                "ATI WebSub Debug - publish_event_websub failure config_id=%s event_type=%s partner_id=%s",
                self.id,
                self.event_type,
                self._extract_partner_id_from_payload(data),
            )
            raise
