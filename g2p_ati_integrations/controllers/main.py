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


    @http.route("/api/farmer", type="http", auth="public", methods=["GET"], csrf=False)
    def get_farmer(self, farmer_id=None, limit=50, offset=0):
        _logger.info("Received request for /api/farmer with farmer_id: %s", farmer_id)
        try:
            domain = [("is_farmer", "=", "yes")]
            if farmer_id:
                domain.append(("farmer_id", "=", farmer_id))

            partners = (
                request.env["res.partner"]
                .sudo()
                .search(domain, limit=int(limit), offset=int(offset))
            )
            _logger.info("Farmers found: %s", len(partners))

            data = []
            for p in partners:
                land_info = [
                    {
                        "land_id": land.land_id,
                        "ownership_type": land.ownership_type,
                        "total_land_area": land.total_land_area,
                        "land_kebele": land.land_kebele.name if land.land_kebele else None,
                    }
                    for land in p.land_information_ids
                ]
                crop_info = [
                    {
                        "crop_id": crop.id,
                        "crop_name": crop.crop.name if crop.crop else None,
                        "season": crop.season.name if crop.season else None,
                        "planted_date_gc": crop.collected_gc.isoformat() if crop.collected_gc else None,
                        "is_diseased": crop.is_diseased,
                    }
                    for crop in p.crop_information_ids
                ]
                livestock_info = [
                    {
                        "livestock_id": ls.id,
                        "livestock_type": ls.livestock_type.name if ls.livestock_type else None,
                        "number_of_livestock": ls.number_of_livestock,
                        "is_diseased": ls.is_diseased,
                    }
                    for ls in p.livestock_information_ids
                ]

                data.append({
                    "partner_id": p.id,
                    "farmer_id": p.farmer_id,
                    "name": p.name,
                    "phone": p.phone,
                    "state": p.state,
                    "region": p.region.name if p.region else None,
                    "zone": p.zone.name if p.zone else None,
                    "woreda": p.woreda.name if p.woreda else None,
                    "kebele": p.kebele.name if p.kebele else None,
                    "land_information": land_info,
                    "crop_information": crop_info,
                    "livestock_information": livestock_info,
                })

            response_data = {"count": len(data), "farmers": data}
            return request.make_response(
                json.dumps(response_data), headers=[("Content-Type", "application/json")]
            )
        except Exception as e:
            _logger.error("Error occurred: %s", e)
            return request.make_response(
                json.dumps({"error": str(e)}), headers=[("Content-Type", "application/json")]
            )
