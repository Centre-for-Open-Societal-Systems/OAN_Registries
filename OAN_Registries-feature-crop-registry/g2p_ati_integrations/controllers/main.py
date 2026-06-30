import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class LandAPIController(http.Controller):
    @http.route("/api/land_info", type="http", auth="public", methods=["GET"], csrf=False)
    def get_national_id_info(self, land_id=None):
        _logger.info("Received request for /api/land_info with land_id: %s", land_id)
        if not land_id:
            return request.make_response(
                json.dumps({"error": "Missing land_id"}), headers=[("Content-Type", "application/json")]
            )

        try:
            partner = (
                request.env["res.partner"]
                .sudo()
                .search([("land_information_ids.land_id", "=", land_id)], limit=1)
            )
            _logger.info("Partner found: %s", partner)

            if not partner:
                return request.make_response(
                    json.dumps({"error": "No partner found for this land_id"}),
                    headers=[("Content-Type", "application/json")],
                )
            national_id_info = [
                {"id_number": reg.value, "id_type": reg.id_type.name} for reg in partner.reg_ids
            ]

            response_data = {"partner_id": partner.id, "national_ids": national_id_info}

            return request.make_response(
                json.dumps(response_data), headers=[("Content-Type", "application/json")]
            )

        except Exception as e:
            _logger.error("Error occurred: %s", e)
            return request.make_response(
                json.dumps({"error": str(e)}), headers=[("Content-Type", "application/json")]
            )

    @http.route("/api", type="http", auth="none", methods=["GET"], csrf=False)
    def get_api(self):
        _logger.info("Received request for /api")
        return request.make_response(
            json.dumps({"message": "Welcome to the Land API"}), headers=[("Content-Type", "application/json")]
        )
