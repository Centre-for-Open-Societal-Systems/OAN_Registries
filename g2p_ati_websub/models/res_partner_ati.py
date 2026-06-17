# Part of OpenG2P. See LICENSE file for full copyright and licensing details.
from odoo import api, models

import logging

_logger = logging.getLogger(__name__)


class ResPartnerATIWebsub(models.Model):
    _inherit = "res.partner"

    _ATI_WEBSUB_TRACKING_FIELDS = {"websub_last_shared_at"}

    def _internal_publisher_count(self, event_type):
        return self.env["g2p.datashare.config.websub"].search_count(
            [("event_type", "=", event_type), ("active", "=", True), ("publisher_type", "=", "internal")]
        )

    def _resolve_internal_event_type(self, create_event_type, update_event_type, prefer_create):
        preferred = create_event_type if prefer_create else update_event_type
        if self._internal_publisher_count(preferred):
            return preferred
        if prefer_create and self._internal_publisher_count(update_event_type):
            _logger.info(
                "ATI WebSub Debug - Falling back event type from %s to %s due to missing INTERNAL publisher",
                preferred,
                update_event_type,
            )
            return update_event_type
        return preferred

    def _enqueue_websub_publish(self, event_type, payload, partner_id, partner_state):
        config_model = self.env["g2p.datashare.config.websub"]
        publisher_count = self._internal_publisher_count(event_type)
        job = config_model.with_delay().publish_event_internal(event_type, payload)
        _logger.info(
            "ATI WebSub Debug - Enqueued INTERNAL queue job uuid=%s state=%s event=%s partner_id=%s "
            "partner_state=%s internal_publishers=%s payload_keys=%s",
            getattr(job, "uuid", None),
            getattr(job, "state", None),
            event_type,
            partner_id,
            partner_state,
            publisher_count,
            sorted(payload.keys()) if isinstance(payload, dict) else None,
        )
        return job

    @api.model_create_multi
    def create(self, vals_list):
        records = super(ResPartnerATIWebsub, self.with_context(ati_skip_base_websub_publish=True)).create(
            vals_list
        )
        for record, vals in zip(records, vals_list):
            if not record.is_registrant or record.state != "approved":
                _logger.info(
                    "ATI WebSub Debug - Skipped enqueue on create for partner_id=%s is_registrant=%s state=%s",
                    record.id,
                    record.is_registrant,
                    record.state,
                )
                continue
            new_vals = (vals or {}).copy()
            new_vals["id"] = record.id
            new_vals = record._sanitize_for_json(new_vals)
            create_event_type = "WEBSUB_GROUP_CREATED" if record.is_group else "WEBSUB_INDIVIDUAL_CREATED"
            update_event_type = "WEBSUB_GROUP_UPDATED" if record.is_group else "WEBSUB_INDIVIDUAL_UPDATED"
            event_type = self._resolve_internal_event_type(
                create_event_type,
                update_event_type,
                prefer_create=True,
            )
            _logger.info(
                "Approved partner created (ID: %s). Publishing WebSub event: %s",
                record.id,
                event_type,
            )
            self._enqueue_websub_publish(event_type, new_vals, record.id, record.state)
        return records

    def write(self, vals):
        res = super(ResPartnerATIWebsub, self.with_context(ati_skip_base_websub_publish=True)).write(vals)

        if self.env.context.get("ati_skip_websub_enqueue"):
            _logger.info(
                "ATI WebSub Debug - Skipped enqueue on write due to ati_skip_websub_enqueue context partner_ids=%s "
                "payload_keys=%s",
                self.ids,
                sorted(vals.keys()) if isinstance(vals, dict) else None,
            )
            return res

        changed_fields = set((vals or {}).keys())
        if changed_fields and changed_fields.issubset(self._ATI_WEBSUB_TRACKING_FIELDS):
            _logger.info(
                "ATI WebSub Debug - Skipped enqueue on tracking-only write partner_ids=%s payload_keys=%s",
                self.ids,
                sorted(changed_fields),
            )
            return res

        for rec in self:
            if not rec.is_registrant or rec.state != "approved":
                _logger.info(
                    "ATI WebSub Debug - Skipped enqueue on write for partner_id=%s is_registrant=%s state=%s",
                    rec.id,
                    rec.is_registrant,
                    rec.state,
                )
                continue

            new_vals = (vals or {}).copy()
            new_vals["id"] = rec.id
            new_vals = rec._sanitize_for_json(new_vals)

            update_event_type = "WEBSUB_GROUP_UPDATED" if rec.is_group else "WEBSUB_INDIVIDUAL_UPDATED"
            event_type = update_event_type

            _logger.info(
                "Approved partner (ID: %s) change detected. Publishing WebSub event: %s",
                rec.id,
                event_type,
            )
            self._enqueue_websub_publish(event_type, new_vals, rec.id, rec.state)

        return res

    def unlink(self):
        # Publish delete events only for approved registrants and prevent base module double-queueing.
        approved_registrants = self.filtered(lambda rec: rec.is_registrant and rec.state == "approved")
        delete_events = [
            (
                "WEBSUB_GROUP_DELETED" if rec.is_group else "WEBSUB_INDIVIDUAL_DELETED",
                {"id": rec.id},
                rec.id,
                rec.state,
            )
            for rec in approved_registrants
        ]

        res = super(ResPartnerATIWebsub, self.with_context(ati_skip_base_websub_publish=True)).unlink()

        for event_type, payload, partner_id, partner_state in delete_events:
            _logger.info(
                "Approved partner deleted (ID: %s). Publishing WebSub event: %s",
                payload.get("id"),
                event_type,
            )
            self._enqueue_websub_publish(event_type, payload, partner_id, partner_state)
        return res
