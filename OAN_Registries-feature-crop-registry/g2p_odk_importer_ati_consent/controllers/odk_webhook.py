import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class OdkConsentWebhookController(http.Controller):
    @http.route(
        "/api/odk/import/<int:odk_import_id>/webhook",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def odk_import_webhook(self, odk_import_id, **kwargs):
        odk_import = request.env["odk.import"].sudo().browse(odk_import_id)
        if not odk_import.exists():
            return self._json_response({"success": False, "message": "ODK import not found."}, status=404)
        odk_import = odk_import.with_context(odk_webhook_headers=dict(request.httprequest.headers))

        payload = request.httprequest.get_json(silent=True)
        if not isinstance(payload, dict):
            payload = {}

        provided_secret = odk_import.extract_webhook_secret(payload=payload, params=request.params)
        if not odk_import.is_valid_webhook_secret(provided_secret):
            _logger.warning("Rejected ODK webhook for import_id=%s due to invalid secret.", odk_import.id)
            return self._json_response({"success": False, "message": "Invalid webhook secret."}, status=403)

        if not odk_import.enable_webhook_import:
            return self._json_response(
                {"success": False, "message": "Webhook import is disabled for this importer."},
                status=409,
            )

        instance_id = odk_import.extract_instance_id_from_webhook_payload(payload=payload, params=request.params)
        if not instance_id:
            return self._json_response(
                {"success": False, "message": "Webhook payload did not include an instance ID."},
                status=400,
            )

        try:
            imported = odk_import.process_records(instance_id=instance_id)
        except Exception as exc:
            _logger.exception(
                "ODK webhook import failed for import_id=%s instance_id=%s: %s",
                odk_import.id,
                instance_id,
                exc,
            )
            return self._json_response(
                {
                    "success": False,
                    "message": str(exc),
                    "instance_id": instance_id,
                },
                status=500,
            )

        return self._json_response(
            {
                "success": True,
                "message": "Webhook import processed.",
                "instance_id": instance_id,
                "result": imported,
            }
        )

    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[("Content-Type", "application/json")],
            status=status,
        )
