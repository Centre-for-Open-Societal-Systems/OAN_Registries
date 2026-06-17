import base64
import json
import logging
import re
from datetime import date

from odoo import http
from odoo.exceptions import MissingError
from odoo.http import request

# from odoo.addons.g2p_agent_portal_base.controllers.main import (
#     G2PServiceProviderBeneficiaryManagement,
# )
# from odoo.addons.g2p_agent_portal_base.controllers.main import ServiceProviderBaseContorller
from odoo.addons.g2p_registration_portal_base.controllers.main import G2PregistrationPortalBase

# from odoo.addons.g2p_agent_portal_base.controllers.main import ServiceProviderBaseContorller


# from odoo.addons.g2p_agent_portal_base.controllers.main import AgentPortalBase

_logger = logging.getLogger(__name__)


class AtiServiceProviderContorller(G2PregistrationPortalBase):
    def _get_update_request_model(self):
        try:
            return request.env["request"].sudo()
        except KeyError:
            return None

    @http.route(["/serviceprovider/home"], type="http", auth="user", website=True)
    def portal_home(self, **kwargs):
        # domain = []
        # domain.append(("is_group", "=", True))
        user_id = request.env.user.id
        partner = request.env.user.partner_id

        households = (
            request.env["res.partner"]
            .sudo()
            .search(
                [
                    ("is_group", "=", True),
                    # "|",  # Logical OR operator
                    ("enumerator_user_id", "=", user_id),
                    # ("enumerator_user_id", "=", partner.odk_app_user.odk_user_id),
                ]
            )
        )
        individuals = (
            request.env["res.partner"]
            .sudo()
            .search(
                [
                    ("is_group", "=", False),
                    ("is_farmer", "=", "yes"),
                    # "|",  # Logical OR operator
                    ("enumerator_user_id", "=", user_id),
                    # ("enumerator_user_id", "=", partner.odk_app_user.odk_user_id),
                ]
            )
        )

        return request.render(
            "g2p_ati_service_provider_portal.ati_dashboard_template",
            {"households": households, "individuals": individuals},
        )

    @http.route(["/portal/myprofile", "/serviceprovider/myprofile"], type="http", auth="user", website=True)
    def portal_profile(self, **kwargs):
        current_user = request.env.user
        current_partner = request.env.user.partner_id
        role_name = "Portal User"
        partner_name = False

        if "consent_portal_role_ids" in current_user._fields:
            role_names = current_user.consent_portal_role_ids.mapped("name")
            if role_names:
                role_name = ", ".join(role_names)

        if "consent_parent_partner_id" in current_user._fields and current_user.consent_parent_partner_id:
            partner_name = current_user.consent_parent_partner_id.name

        qcontext = {
            "current_partner": current_partner,
            "profile_role_name": role_name,
            "profile_partner_name": partner_name,
        }
        try:
            request.env.ref("g2p_ati_service_provider_portal.ati_profile_page_service_provider")
            template = "g2p_ati_service_provider_portal.ati_profile_page_service_provider"
        except (ValueError, MissingError):
            template = "g2p_agent_portal_base.profile_page"
        return request.render(template, qcontext)

    @http.route(["/serviceprovider/update/suggests"], type="http", auth="user", website=True)
    def portal_update_suggests(self, **kwargs):
        user_id = request.env.user.id
        request_model = self._get_update_request_model()
        updte_suggests = (
            request_model.search([("enumerator_id", "=", user_id)], order="create_date desc")
            if request_model
            else []
        )
        return request.render(
            "g2p_ati_service_provider_portal.ati_update_suggests_template",
            {
                "updte_suggests": updte_suggests,
            },
        )

    @http.route(["/get_notifications"], type="http", auth="user", website=True)
    def get_notifications(self, **kwargs):
        request_model = self._get_update_request_model()
        if not request_model:
            return json.dumps([])
        user_id = request.env.user.id
        notifications = request_model.search([("seen", "=", False), ("enumerator_id", "=", user_id)])

        notifications_data = []
        for notif in notifications:
            suggester_name = notif.requester_id.name if notif.requester_id else "Unknown"
            notifications_data.append(
                {
                    "id": notif.id,
                    "message": f"{suggester_name} has suggested an update",
                    "url": "/serviceprovider/update/suggests",
                }
            )

        return json.dumps(notifications_data)

    @http.route(["/get_notification_count"], type="http", auth="user", website=True, csrf=False)
    def get_notification_count(self, **kwargs):
        request_model = self._get_update_request_model()
        if not request_model:
            return json.dumps([{"count": 0}])
        user_id = request.env.user.id
        notification_count = request_model.search_count(
            [("seen", "=", False), ("status", "=", "newSuggestion"), ("enumerator_id", "=", user_id)]
        )
        return json.dumps([{"count": notification_count}])

    @http.route("/mark_notification_seen", type="json", auth="user", csrf=False)
    def mark_notification_seen(self):
        request_model = self._get_update_request_model()
        if not request_model:
            return {"status": "success"}
        json_data = request.httprequest.get_json()
        notification_id = json_data.get("notification_id")

        if not notification_id:
            return {"status": "error", "message": "Notification ID is missing"}

        try:
            notification = request_model.browse(int(notification_id))

        except ValueError:
            return {"status": "error", "message": "Invalid Notification ID"}

        if notification and not notification.seen:
            notification.seen = True
            return {"status": "success"}

        return {"status": "error", "message": "Notification not found or already seen"}

    @http.route(["/set_all_notifications_seen"], type="http", auth="user", website=True, csrf=False)
    def set_all_notifications_seen(self, **kwargs):
        request_model = self._get_update_request_model()
        if not request_model:
            return json.dumps({"status": "success"})
        user_id = request.env.user.id
        notifications = request_model.search([("seen", "=", False), ("enumerator_id", "=", user_id)])

        for notif in notifications:
            notif.seen = True

        return json.dumps({"status": "success"})

    @http.route(["/view_all_notifications"], type="http", auth="user", website=True)
    def view_all_notifications(self, **kwargs):
        request_model = self._get_update_request_model()
        if not request_model:
            return json.dumps({"status": "success"})
        user_id = request.env.user.id
        notifications = request_model.search([("seen", "=", False), ("enumerator_id", "=", user_id)])

        for notif in notifications:
            notif.seen = True

        return json.dumps({"status": "success"})


class AtiserviceProviderBeneficiaryManagement(G2PregistrationPortalBase):
    @http.route(
        ["/get_selection_name"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def get_selection(self, selectedValue=None, **kwargs):
        name = request.env["ir.model.fields.selection"].sudo().search([("id", "=", selectedValue)]).name
        return json.dumps([{"name": name}])

    @http.route(
        ["/update_zone_options"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def update_zone_options(self, region_id=None, **kwargs):
        if region_id and region_id.strip():
            zones = request.env["g2p.zone"].sudo().search([("region", "=", int(region_id))])
            zone_options = [{"id": zone.id, "name": zone.name} for zone in zones]
            return json.dumps(zone_options)
        else:
            return json.dumps([])

    @http.route(
        ["/update_woreda_options"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def update_woreda_options(self, zone_id=None, **kwargs):
        if zone_id and zone_id.strip():
            woredas = request.env["g2p.woreda"].sudo().search([("zone", "=", int(zone_id))])
            woredas_options = [{"id": woreda.id, "name": woreda.name} for woreda in woredas]
            return json.dumps(woredas_options)
        else:
            return json.dumps([])

    @http.route(
        ["/update_kebele_options"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def update_kebele_options(self, woreda_id=None, **kwargs):
        if woreda_id and woreda_id.strip():
            kebeles = request.env["g2p.kebele"].sudo().search([("woreda", "=", int(woreda_id))])
            kebeles_options = [{"id": kebele.id, "name": kebele.name} for kebele in kebeles]
            return json.dumps(kebeles_options)
        else:
            return json.dumps([])

    @http.route(
        ["/serviceprovider/group/create/"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def group_create(self, **kw):
        gender = request.env["gender.type"].sudo().search([])
        region = request.env["g2p.region"].sudo().search([])
        zone = request.env["g2p.zone"].sudo().search([])
        woreda = request.env["g2p.woreda"].sudo().search([])
        kebele = request.env["g2p.kebele"].sudo().search([])
        primary_language = request.env["g2p.lang"].sudo().search([])
        primary_cooperatives = request.env["g2p.primary.cooperative"].sudo().search([])
        cooperative_unions = request.env["g2p.cooperative.union"].sudo().search([])
        primary_commodities = request.env["g2p.primary.commodity"].sudo().search([])
        crops = request.env["g2p.crop"].sudo().search([])
        crop_illness_type = request.env["g2p.illness.type"].sudo().search([("illness_type", "=", "crop")])
        crop_water_source = request.env["g2p.water.source"].sudo().search([])
        livestock_types = request.env["g2p.livestock.type"].sudo().search([])
        livestock_illness_type = (
            request.env["g2p.illness.type"].sudo().search([("illness_type", "=", "animal")])
        )
        water_source = request.env["g2p.water.source"].sudo().search([])
        machinary_types = request.env["g2p.machinery"].sudo().search([])
        financial_access = request.env["g2p.finance.access"].sudo().search([])
        source_of_income = request.env["g2p.hh.income"].sudo().search([])
        relationship_with_hhh = request.env["g2p.group.membership.kind"].sudo().search([])

        model_id = request.env["ir.model"].sudo().search([("model", "=", "res.partner")])
        land_model_id = request.env["ir.model"].sudo().search([("model", "=", "g2p.land.information")])
        crop_model_id = request.env["ir.model"].sudo().search([("model", "=", "g2p.crop.information")])
        livestock_model_id = (
            request.env["ir.model"].sudo().search([("model", "=", "g2p.livestock.information")])
        )

        ownership_type_selections = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", land_model_id.id), ("name", "=", "ownership_type")])
            .selection_ids
        )

        crop_is_diseased_selections = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", crop_model_id.id), ("name", "=", "is_diseased")])
            .selection_ids
        )

        livestock_is_diseased_selections = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", livestock_model_id.id), ("name", "=", "is_diseased")])
            .selection_ids
        )

        serialized_crop_info_data = []
        serialized_livestock_info_data = []

        has_national_id = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "has_national_id")])
            .selection_ids
        )

        is_member_of_primary_cooperative = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "is_member_of_primary_cooperative")])
            .selection_ids
        )

        is_member_of_cooperative_union = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "is_member_of_primary_cooperative")])
            .selection_ids
        )

        is_member_in_farmer_cluster = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "is_member_in_farmer_cluster")])
            .selection_ids
        )

        role_in_cluster = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "role_in_farmer_cluster")])
            .selection_ids
        )

        access_to_machinery = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "access_to_machinery")])
            .selection_ids
        )

        has_finance_access = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "has_finance_access")])
            .selection_ids
        )

        marital_status = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "martial_status")])
            .selection_ids
        )

        education_level = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "education")])
            .selection_ids
        )

        farming_type = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "farming_type")])
            .selection_ids
        )

        disability_status = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "is_disabled")])
            .selection_ids
        )

        has_personal_phone = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "has_personal_phone")])
            .selection_ids
        )
        hh_is_household_head = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "hh_is_household_head")])
            .selection_ids
        )

        do_you_use_fertilizer = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "do_you_use_fertilizer")])
            .selection_ids
        )
        do_you_use_insecticide = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "do_you_use_insecticide")])
            .selection_ids
        )

        do_you_use_pesticide = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "do_you_use_pesticide")])
            .selection_ids
        )

        do_you_use_improved_seed = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "do_you_use_improved_seed")])
            .selection_ids
        )

        return request.render(
            "g2p_ati_service_provider_portal.ati_create_group_form_template",
            {
                "has_national_id": has_national_id,
                "gender": gender,
                "region": region,
                "zone": zone,
                "woreda": woreda,
                "kebele": kebele,
                "hh_is_household_head": hh_is_household_head,
                "primary_language": primary_language,
                "has_personal_phone": has_personal_phone,
                "farming_type": farming_type,
                "source_of_income": source_of_income,
                "is_member_of_primary_cooperative": is_member_of_primary_cooperative,
                "is_member_of_cooperative_union": is_member_of_cooperative_union,
                "is_member_in_farmer_cluster": is_member_in_farmer_cluster,
                "primary_cooperatives": primary_cooperatives,
                "cooperative_unions": cooperative_unions,
                "primary_commodities": primary_commodities,
                "role_in_cluster": role_in_cluster,
                "serialized_crop_info_data": serialized_crop_info_data,
                "serialized_livestock_info_data": serialized_livestock_info_data,
                "crops": crops,
                "crop_illness_type": crop_illness_type,
                "crop_water_source": crop_water_source,
                "livestock_types": livestock_types,
                "livestock_illness_type": livestock_illness_type,
                "water_source": water_source,
                "do_you_use_fertilizer": do_you_use_fertilizer,
                "do_you_use_pesticide": do_you_use_pesticide,
                "do_you_use_insecticide": do_you_use_insecticide,
                "do_you_use_improved_seed": do_you_use_improved_seed,
                "access_to_machinery": access_to_machinery,
                "machinary_types": machinary_types,
                "marital_status": marital_status,
                "education_level": education_level,
                "disability_status": disability_status,
                "has_finance_access": has_finance_access,
                "financial_access": financial_access,
                "ownership_type_selections": ownership_type_selections,
                "crop_is_diseased_selections": crop_is_diseased_selections,
                "livestock_is_diseased_selections": livestock_is_diseased_selections,
                "relationship_with_hhh": relationship_with_hhh,
            },
        )

    @http.route(
        ["/serviceprovider/group/create/submit"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def group_create_submit(self, **kw):
        try:
            # beneficiary_id = int(kw.get("group_id"))

            # beneficiary = request.env["res.partner"].sudo().browse(beneficiary_id)

            # # individuals_data = request.params.get("individuals", [])

            # if not beneficiary:
            #     return request.render(
            #         "g2p_agent_portal_base.error_template",
            #         {"error_message": "Beneficiary not found."},
            #     )

            # for key, value in kw.items():
            #     if key in beneficiary:
            #         beneficiary.write({key: value})
            #     else:
            #         pass

            response = request.redirect("/serviceprovider/group")

            response.set_cookie("popup_status", "successful", max_age=10)
            response.set_cookie("popup_msg", "Record Created Successfully!", max_age=10)

            return response
        except Exception:
            return request.render(
                "g2p_registration_portal_base.error_template",
                {"error_message": "An error occurred. Please try again later."},
            )

    @http.route(
        ["/serviceprovider/group/update/<int:_id>"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def group_update(self, _id, **kw):
        try:
            group = request.env["res.partner"].sudo().browse(_id)
            if not group:
                return request.render(
                    "g2p_registration_portal_base.error_template",
                    {"error_message": "Household not found."},
                )

            gender = request.env["gender.type"].sudo().search([])
            region = request.env["g2p.region"].sudo().search([])
            zone = request.env["g2p.zone"].sudo().search([])
            woreda = request.env["g2p.woreda"].sudo().search([])
            kebele = request.env["g2p.kebele"].sudo().search([])
            primary_language = request.env["g2p.lang"].sudo().search([])
            primary_cooperatives = request.env["g2p.primary.cooperative"].sudo().search([])
            cooperative_unions = request.env["g2p.cooperative.union"].sudo().search([])
            primary_commodities = request.env["g2p.primary.commodity"].sudo().search([])
            crops = request.env["g2p.crop"].sudo().search([])
            crop_illness_type = request.env["g2p.illness.type"].sudo().search([("illness_type", "=", "crop")])
            crop_water_source = request.env["g2p.water.source"].sudo().search([])
            livestock_types = request.env["g2p.livestock.type"].sudo().search([])
            livestock_illness_type = (
                request.env["g2p.illness.type"].sudo().search([("illness_type", "=", "animal")])
            )
            water_source = request.env["g2p.water.source"].sudo().search([])
            machinary_types = request.env["g2p.machinery"].sudo().search([])
            financial_access = request.env["g2p.finance.access"].sudo().search([])
            source_of_income = request.env["g2p.hh.income"].sudo().search([])
            relationship_with_hhh = request.env["g2p.group.membership.kind"].sudo().search([])

            model_id = request.env["ir.model"].sudo().search([("model", "=", "res.partner")])

            land_model_id = request.env["ir.model"].sudo().search([("model", "=", "g2p.land.information")])
            crop_model_id = request.env["ir.model"].sudo().search([("model", "=", "g2p.crop.information")])
            livestock_model_id = (
                request.env["ir.model"].sudo().search([("model", "=", "g2p.livestock.information")])
            )

            ownership_type_selections = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", land_model_id.id), ("name", "=", "ownership_type")])
                .selection_ids
            )

            crop_is_diseased_selections = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", crop_model_id.id), ("name", "=", "is_diseased")])
                .selection_ids
            )

            livestock_is_diseased_selections = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", livestock_model_id.id), ("name", "=", "is_diseased")])
                .selection_ids
            )

            serialized_crop_info_data = []
            serialized_livestock_info_data = []

            has_national_id = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "has_national_id")])
                .selection_ids
            )

            is_member_of_primary_cooperative = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "is_member_of_primary_cooperative")])
                .selection_ids
            )

            is_member_of_cooperative_union = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "is_member_of_primary_cooperative")])
                .selection_ids
            )

            is_member_in_farmer_cluster = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "is_member_in_farmer_cluster")])
                .selection_ids
            )

            role_in_cluster = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "role_in_farmer_cluster")])
                .selection_ids
            )

            access_to_machinery = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "access_to_machinery")])
                .selection_ids
            )

            has_finance_access = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "has_finance_access")])
                .selection_ids
            )

            marital_status = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "martial_status")])
                .selection_ids
            )

            education_level = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "education")])
                .selection_ids
            )

            farming_type = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "farming_type")])
                .selection_ids
            )

            disability_status = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "is_disabled")])
                .selection_ids
            )

            has_personal_phone = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "has_personal_phone")])
                .selection_ids
            )

            do_you_use_fertilizer = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "do_you_use_fertilizer")])
                .selection_ids
            )

            do_you_use_insecticide = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "do_you_use_insecticide")])
                .selection_ids
            )

            do_you_use_pesticide = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "do_you_use_pesticide")])
                .selection_ids
            )

            do_you_use_improved_seed = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", model_id.id), ("name", "=", "do_you_use_improved_seed")])
                .selection_ids
            )

            members = group.group_membership_ids
            farmer_member_ids = []
            member_ids = []
            other_kebele = ""
            other_woreda = ""
            other_primary_coop = ""
            other_coop_union = ""
            other_income = ""
            if members:
                for ind in members.individual:
                    if ind.is_farmer == "yes":
                        farmer_member_ids.append(ind)
                    else:
                        member_ids.append(ind)
                additional_info = " "
                household_head_id = ""
                for indiv in members.individual:
                    if indiv.hh_is_household_head == "yes" and indiv.is_farmer == "yes":
                        household_head_id = indiv
                if household_head_id:
                    head_individual = request.env["res.partner"].sudo().browse(int(household_head_id))
                    additional_info = head_individual.additional_g2p_info

                if isinstance(additional_info, str):
                    try:
                        additional_info = json.loads(additional_info)
                    except json.JSONDecodeError:
                        # Handle JSON decoding error if the string is not valid JSON
                        additional_info = {}

                # Initialize variables

                # Check if additional_info is a dictionary and populate variables accordingly
                if isinstance(additional_info, dict):
                    if "Kebele" in additional_info:
                        other_kebele = additional_info.get("Kebele", "")

                    if "Woreda" in additional_info:
                        other_woreda = additional_info.get("Woreda", "")

                    if "Primary Cooperative" in additional_info:
                        other_primary_coop = additional_info.get("Primary Cooperative", "")

                    if "Cooperative Union" in additional_info:
                        other_coop_union = additional_info.get("Cooperative Union", "")

                    if "Household Income" in additional_info:
                        other_income = additional_info.get("Household Income", "")
            return request.render(
                "g2p_ati_service_provider_portal.ati_update_group_form_template",
                {
                    "relationship_with_hhh": relationship_with_hhh,
                    "group": group,
                    "farmer_member_ids": farmer_member_ids,
                    "member_ids": member_ids,
                    "has_national_id": has_national_id,
                    "gender": gender,
                    "region": region,
                    "zone": zone,
                    "woreda": woreda,
                    "kebele": kebele,
                    "primary_language": primary_language,
                    "has_personal_phone": has_personal_phone,
                    "farming_type": farming_type,
                    "is_member_of_primary_cooperative": is_member_of_primary_cooperative,
                    "is_member_of_cooperative_union": is_member_of_cooperative_union,
                    "is_member_in_farmer_cluster": is_member_in_farmer_cluster,
                    "primary_cooperatives": primary_cooperatives,
                    "cooperative_unions": cooperative_unions,
                    "primary_commodities": primary_commodities,
                    "role_in_cluster": role_in_cluster,
                    "serialized_crop_info_data": serialized_crop_info_data,
                    "serialized_livestock_info_data": serialized_livestock_info_data,
                    "crops": crops,
                    "crop_illness_type": crop_illness_type,
                    "crop_water_source": crop_water_source,
                    "livestock_types": livestock_types,
                    "livestock_illness_type": livestock_illness_type,
                    "water_source": water_source,
                    "do_you_use_fertilizer": do_you_use_fertilizer,
                    "do_you_use_pesticide": do_you_use_pesticide,
                    "do_you_use_insecticide": do_you_use_insecticide,
                    "do_you_use_improved_seed": do_you_use_improved_seed,
                    "access_to_machinery": access_to_machinery,
                    "machinary_types": machinary_types,
                    "marital_status": marital_status,
                    "education_level": education_level,
                    "disability_status": disability_status,
                    "has_finance_access": has_finance_access,
                    "financial_access": financial_access,
                    "source_of_income": source_of_income,
                    "ownership_type_selections": ownership_type_selections,
                    "crop_is_diseased_selections": crop_is_diseased_selections,
                    "livestock_is_diseased_selections": livestock_is_diseased_selections,
                    "other_kebele": other_kebele,
                    "other_woreda": other_woreda,
                    "other_primary_coop": other_primary_coop,
                    "other_coop_union": other_coop_union,
                    "other_income": other_income,
                },
            )
        except Exception as e:
            return request.render(
                "g2p_registration_portal_base.error_template",
                {"error_message": e},
            )

    @http.route(
        ["/serviceprovider/group/update/submit"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def group_update_submit(self, **kw):
        try:
            # group_id = int(kw.get("group_id"))

            # group = request.env["res.partner"].sudo().browse(group_id)

            # if not group:
            #     return request.render(
            #         "g2p_agent_portal_base.error_template",
            #         {"error_message": "Household not found."},
            #     )

            # for key, value in kw.items():
            #     if key in group:
            #         group.write({key: value})
            #     else:
            #         pass
            return request.redirect("/serviceprovider/group")

        except Exception:
            return request.render(
                "g2p_registration_portal_base.error_template",
                {"error_message": "An error occurred. Please try again later."},
            )

    @http.route(
        ["/serviceprovider/individual/registrar/create/"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def individual_registrar_create(self, **kw):
        gender = request.env["gender.type"].sudo().search([])
        region = request.env["g2p.region"].sudo().search([])
        # zone = request.env["g2p.zone"].sudo().search([])
        # woreda = request.env["g2p.woreda"].sudo().search([])
        # kebele = request.env["g2p.kebele"].sudo().search([])
        primary_language = request.env["g2p.lang"].sudo().search([])
        primary_cooperatives = request.env["g2p.primary.cooperative"].sudo().search([])
        cooperative_unions = request.env["g2p.cooperative.union"].sudo().search([])
        primary_commodities = request.env["g2p.primary.commodity"].sudo().search([])
        crops = request.env["g2p.crop"].sudo().search([])
        crop_illness_type = request.env["g2p.illness.type"].sudo().search([("illness_type", "=", "crop")])
        crop_water_source = request.env["g2p.water.source"].sudo().search([])
        livestock_types = request.env["g2p.livestock.type"].sudo().search([])
        livestock_illness_type = (
            request.env["g2p.illness.type"].sudo().search([("illness_type", "=", "animal")])
        )
        water_source = request.env["g2p.water.source"].sudo().search([])
        machinary_types = request.env["g2p.machinery"].sudo().search([])
        financial_access = request.env["g2p.finance.access"].sudo().search([])
        source_of_income = request.env["g2p.hh.income"].sudo().search([])

        model_id = request.env["ir.model"].sudo().search([("model", "=", "res.partner")])
        land_model_id = request.env["ir.model"].sudo().search([("model", "=", "g2p.land.information")])
        crop_model_id = request.env["ir.model"].sudo().search([("model", "=", "g2p.crop.information")])
        livestock_model_id = (
            request.env["ir.model"].sudo().search([("model", "=", "g2p.livestock.information")])
        )

        ownership_type_selections = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", land_model_id.id), ("name", "=", "ownership_type")])
            .selection_ids
        )

        crop_is_diseased_selections = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", crop_model_id.id), ("name", "=", "is_diseased")])
            .selection_ids
        )

        livestock_is_diseased_selections = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", livestock_model_id.id), ("name", "=", "is_diseased")])
            .selection_ids
        )

        serialized_crop_info_data = []
        serialized_livestock_info_data = []

        has_national_id = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "has_national_id")])
            .selection_ids
        )

        is_member_of_primary_cooperative = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "is_member_of_primary_cooperative")])
            .selection_ids
        )

        is_member_of_cooperative_union = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "is_member_of_primary_cooperative")])
            .selection_ids
        )

        is_member_in_farmer_cluster = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "is_member_in_farmer_cluster")])
            .selection_ids
        )

        role_in_cluster = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "role_in_farmer_cluster")])
            .selection_ids
        )

        do_you_use_fertilizer = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "do_you_use_fertilizer")])
            .selection_ids
        )

        do_you_use_insecticide = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "do_you_use_insecticide")])
            .selection_ids
        )

        do_you_use_pesticide = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "do_you_use_pesticide")])
            .selection_ids
        )
        do_you_use_improved_seed = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "do_you_use_improved_seed")])
            .selection_ids
        )

        access_to_machinery = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "access_to_machinery")])
            .selection_ids
        )

        has_finance_access = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "has_finance_access")])
            .selection_ids
        )

        marital_status = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "martial_status")])
            .selection_ids
        )

        education_level = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "education")])
            .selection_ids
        )

        farming_type = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "farming_type")])
            .selection_ids
        )

        disability_status = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "is_disabled")])
            .selection_ids
        )

        has_personal_phone = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "has_personal_phone")])
            .selection_ids
        )

        hh_is_household_head = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model_id.id), ("name", "=", "hh_is_household_head")])
            .selection_ids
        )

        return request.render(
            "g2p_ati_service_provider_portal.ati_individual_registrant_form_template",
            {
                "has_national_id": has_national_id,
                "gender": gender,
                "region": region,
                "zone": [],
                "woreda": [],
                "kebele": [],
                "primary_language": primary_language,
                "has_personal_phone": has_personal_phone,
                "hh_is_household_head": hh_is_household_head,
                "farming_type": farming_type,
                "is_member_of_primary_cooperative": is_member_of_primary_cooperative,
                "is_member_of_cooperative_union": is_member_of_cooperative_union,
                "is_member_in_farmer_cluster": is_member_in_farmer_cluster,
                "primary_cooperatives": primary_cooperatives,
                "cooperative_unions": cooperative_unions,
                "primary_commodities": primary_commodities,
                "role_in_cluster": role_in_cluster,
                "serialized_crop_info_data": serialized_crop_info_data,
                "serialized_livestock_info_data": serialized_livestock_info_data,
                "crops": crops,
                "crop_illness_type": crop_illness_type,
                "crop_water_source": crop_water_source,
                "livestock_types": livestock_types,
                "livestock_illness_type": livestock_illness_type,
                "water_source": water_source,
                "do_you_use_fertilizer": do_you_use_fertilizer,
                "do_you_use_pesticide": do_you_use_pesticide,
                "do_you_use_insecticide": do_you_use_insecticide,
                "do_you_use_improved_seed": do_you_use_improved_seed,
                "access_to_machinery": access_to_machinery,
                "machinary_types": machinary_types,
                "marital_status": marital_status,
                "education_level": education_level,
                "disability_status": disability_status,
                "has_finance_access": has_finance_access,
                "financial_access": financial_access,
                "source_of_income": source_of_income,
                "ownership_type_selections": ownership_type_selections,
                "crop_is_diseased_selections": crop_is_diseased_selections,
                "livestock_is_diseased_selections": livestock_is_diseased_selections,
            },
        )

    @http.route(
        ["/serviceprovider/individual/beneficiary/create/submit"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def individual_create_submit(self, **kw):
        try:
            vals = self._prepare_individual_vals(kw)
            self._process_land_information(vals, kw)
            self._process_crop_information(vals, kw)
            self._process_livestock_information(vals, kw)
            self._process_access_to_resource(vals, kw)
            self._process_financial_service(vals, kw)
            self._set_default_values(vals)

            request.env["res.partner"].sudo().create(vals)
            return request.redirect("/serviceprovider/individual")

        except Exception as e:
            return request.render(
                "g2p_registration_portal_base.error_template",
                {"error_message": f"Error while creating individual, {e}"},
            )

    def _prepare_individual_vals(self, kw):
        vals = {
            "is_registrant": True,
            "is_group": False,
        }
        name = self._compose_name(kw)
        if name:
            vals["name"] = name

        # Handle national ID
        self._process_national_id(vals, kw)

        # Handle individual details
        self._process_individual_details(vals, kw)

        # Handle socio-economic data
        self._process_socio_economic_data(vals, kw)

        # Handle membership details
        self._process_membership_details(vals, kw)

        return vals

    def _compose_name(self, kw):
        name = ""
        if kw.get("given_name"):
            name += kw.get("given_name") + " "
        if kw.get("family_name"):
            name += kw.get("family_name") + " "
        if kw.get("gf_name_eng"):
            name += kw.get("gf_name_eng")
        return name

    def _process_national_id(self, vals, kw):
        if kw.get("has_national_id"):
            has_national_id = (
                request.env["ir.model.fields.selection"]
                .sudo()
                .search([("id", "=", kw.get("has_national_id"))])
                .value
            )
            vals["has_national_id"] = has_national_id
            if has_national_id == "yes":
                id_type = request.env["g2p.id.type"].sudo().search([("name", "=", "UID")], limit=1)
                vals["reg_ids"] = [(0, 0, {"id_type": id_type.id, "value": kw.get("uid"), "status": "valid"})]
            elif has_national_id == "no" and kw.get("rid") and kw.get("rid").strip():
                id_type = request.env["g2p.id.type"].sudo().search([("name", "=", "RID")], limit=1)
                vals["reg_ids"] = [(0, 0, {"id_type": id_type.id, "value": kw.get("rid"), "status": "valid"})]

    def _process_individual_details(self, vals, kw):
        self._process_household_head(vals, kw)
        # self._process_names(vals, kw)
        # self._process_location(vals, kw)
        self._process_additional_details(vals, kw)
        # self._process_phone_numbers(vals, kw)

    def _process_household_head(self, vals, kw):
        if kw.get("isHouseholdHead"):
            hh_is_household_head = (
                request.env["ir.model.fields.selection"]
                .sudo()
                .search([("id", "=", kw.get("isHouseholdHead"))])
                .value
            )
            vals["hh_is_household_head"] = hh_is_household_head

    def _process_names(self, vals, kw):
        if kw.get("first_name_amh").strip():
            vals["first_name_amh"] = kw.get("first_name_amh")
        if kw.get("family_name_amh").strip():
            vals["family_name_amh"] = kw.get("family_name_amh")
        if kw.get("gf_name_amh").strip():
            vals["gf_name_amh"] = kw.get("gf_name_amh")
        if kw.get("first_name_other") and kw.get("first_name_other").strip():
            vals["first_name_other"] = kw.get("first_name_other")
        if kw.get("family_name_other") and kw.get("family_name_other").strip():
            vals["family_name_other"] = kw.get("family_name_other")
        if kw.get("gf_name_other") and kw.get("gf_name_other").strip():
            vals["gf_name_other"] = kw.get("gf_name_other")

    def _process_location(self, vals, kw):
        if kw.get("region"):
            vals["region"] = int(kw.get("region"))
        if kw.get("zone"):
            vals["zone"] = int(kw.get("zone"))
        if kw.get("woreda"):
            vals["woreda"] = int(kw.get("woreda"))
        if kw.get("kebele"):
            vals["kebele"] = int(kw.get("kebele"))

    def _process_additional_details(self, vals, kw):
        # if kw.get("birthdate"):
        #     vals["birthdate"] = kw.get("birthdate")
        # if kw.get("gender"):
        #     vals["gender"] = kw.get("gender")
        if kw.get("email") and kw.get("email").strip():
            vals["email"] = kw.get("email")
        if kw.get("isDisabled"):
            vals["is_disabled"] = (
                request.env["ir.model.fields.selection"]
                .sudo()
                .search([("id", "=", kw.get("isDisabled"))])
                .value
            )

        if kw.get("primaryLanguage"):
            vals["primary_Language"] = int(kw.get("primaryLanguage"))
        if kw.get("farmingType"):
            vals["farming_type"] = (
                request.env["ir.model.fields.selection"]
                .sudo()
                .search([("id", "=", kw.get("farmingType"))])
                .value
            )

    def _process_phone_numbers(self, vals, kw):
        has_personal_phone = None
        if kw.get("has_personal_phone"):
            has_personal_phone = (
                request.env["ir.model.fields.selection"]
                .sudo()
                .search([("id", "=", kw.get("has_personal_phone"))])
                .value
            )
            vals["has_personal_phone"] = has_personal_phone
        ethiopia_country_id = (
            request.env["res.country"].sudo().search([("name", "=", "Ethiopia")], limit=1).id
        )
        phone_no = []
        if has_personal_phone == "yes":
            phone_no.append(
                (
                    0,
                    0,
                    {
                        "phone_no": kw.get("primary_phone"),
                        "phone_type": "primary",
                        "country": ethiopia_country_id,
                    },
                )
            )
            if kw.get("secondary_phone") and kw.get("secondary_phone").strip():
                phone_no.append(
                    (
                        0,
                        0,
                        {
                            "phone_no": kw.get("secondary_phone"),
                            "phone_type": "secondary",
                            "country": ethiopia_country_id,
                        },
                    )
                )
        elif has_personal_phone == "no":
            phone_no.append(
                (
                    0,
                    0,
                    {
                        "phone_no": kw.get("other_phone"),
                        "phone_type": "other",
                        "country": ethiopia_country_id,
                    },
                )
            )
            if kw.get("secondary_phone") and kw.get("secondary_phone").strip():
                phone_no.append(
                    (
                        0,
                        0,
                        {
                            "phone_no": kw.get("secondary_phone"),
                            "phone_type": "secondary",
                            "country": ethiopia_country_id,
                        },
                    )
                )
        # vals["phone_number_ids"] = phone_no

    def _process_socio_economic_data(self, vals, kw):
        if kw.get("marital_status"):
            vals["martial_status"] = (
                request.env["ir.model.fields.selection"]
                .sudo()
                .search([("id", "=", kw.get("marital_status"))])
                .value
            )
        if kw.get("education_level"):
            vals["education"] = (
                request.env["ir.model.fields.selection"]
                .sudo()
                .search([("id", "=", kw.get("education_level"))])
                .value
            )
        income_source = request.httprequest.form.getlist("hh_income_type")
        if income_source:
            income_source_ids = [int(id) for id in income_source]
            vals["hh_income_type"] = [(6, 0, income_source_ids)]

    def _process_membership_details(self, vals, kw):
        is_member_of_primary_cooperative = False
        is_member_of_cooperative_union = False
        is_member_in_farmer_cluster = False
        if kw.get("is_member_of_primary_coop") and kw.get("is_member_of_primary_coop").strip():
            is_member_of_primary_cooperative = (
                request.env["ir.model.fields.selection"]
                .sudo()
                .search([("id", "=", kw.get("is_member_of_primary_coop"))])
                .value
            )
            vals["is_member_of_primary_cooperative"] = is_member_of_primary_cooperative
        if is_member_of_primary_cooperative == "yes":
            if kw.get("name_of_primary_coop") and kw.get("name_of_primary_coop").strip():
                vals["primary_cooperatives"] = int(kw.get("name_of_primary_coop"))
        if kw.get("is_member_of_coop_union") and kw.get("is_member_of_coop_union").strip():
            is_member_of_cooperative_union = (
                request.env["ir.model.fields.selection"]
                .sudo()
                .search([("id", "=", kw.get("is_member_of_coop_union"))])
                .value
            )
            vals["is_member_of_cooperative_union"] = is_member_of_cooperative_union
        if is_member_of_cooperative_union == "yes":
            if kw.get("name_of_coop_union") and kw.get("name_of_coop_union").strip():
                vals["cooperative_union"] = int(kw.get("name_of_coop_union"))
        if kw.get("is_member_in_farmer_cluster") and kw.get("is_member_in_farmer_cluster").strip():
            is_member_in_farmer_cluster = (
                request.env["ir.model.fields.selection"]
                .sudo()
                .search([("id", "=", kw.get("is_member_in_farmer_cluster"))])
                .value
            )
            vals["is_member_in_farmer_cluster"] = is_member_in_farmer_cluster
        if is_member_in_farmer_cluster == "yes":
            if kw.get("name_of_farmer_cluster") and kw.get("name_of_farmer_cluster").strip():
                vals["farmer_cluster"] = int(kw.get("name_of_farmer_cluster"))

    def _process_land_information(self, vals, kw):
        land = []
        land_info_form_count = int(kw.get("land_info_form_count"))
        for i in range(land_info_form_count):
            index = i + 1
            land.append(
                (
                    0,
                    0,
                    {
                        "region": int(kw.get(f"land_region_{index}")),
                        "zone": int(kw.get(f"land_zone_{index}")),
                        "woreda": int(kw.get(f"land_woreda_{index}")),
                        "kebele": int(kw.get(f"land_kebele_{index}")),
                        "land_size": kw.get(f"land_size_{index}"),
                        "ownership_type": kw.get(f"ownership_type_{index}"),
                        "land_uses": kw.get(f"land_uses_{index}"),
                    },
                )
            )
        vals["land_information"] = [(5, 0, 0)] + land

    def _process_crop_information(self, vals, kw):
        crops = []
        crop_info_form_count = int(kw.get("crop_info_form_count"))
        for i in range(crop_info_form_count):
            index = i + 1
            crops.append(
                (
                    0,
                    0,
                    {
                        "crop_type": kw.get(f"crop_type_{index}"),
                        "crop_name": kw.get(f"crop_name_{index}"),
                        "cultivated_land_size": kw.get(f"cultivated_land_size_{index}"),
                        "unit_of_measure": kw.get(f"unit_of_measure_{index}"),
                        "production_quantity": kw.get(f"production_quantity_{index}"),
                    },
                )
            )
        vals["crop_information"] = [(5, 0, 0)] + crops

    def _process_livestock_information(self, vals, kw):
        livestock = []
        livestock_info_form_count = int(kw.get("livestock_info_form_count"))
        for i in range(livestock_info_form_count):
            index = i + 1
            livestock.append(
                (
                    0,
                    0,
                    {
                        "livestock_type": kw.get(f"livestock_type_{index}"),
                        "breed_name": kw.get(f"breed_name_{index}"),
                        "livestock_count": kw.get(f"livestock_count_{index}"),
                    },
                )
            )
        vals["livestock_information"] = [(5, 0, 0)] + livestock

    def _process_access_to_resource(self, vals, kw):
        access_to_resource_ids = kw.get("access_to_resource")
        if access_to_resource_ids:
            vals["access_to_resource"] = [(6, 0, [int(x) for x in access_to_resource_ids])]

    def _process_financial_service(self, vals, kw):
        financial_service_ids = kw.get("financial_services")
        if financial_service_ids:
            vals["financial_services"] = [(6, 0, [int(x) for x in financial_service_ids])]

    def _set_default_values(self, vals):
        vals["active"] = True
        vals["is_natural_person"] = True

    @http.route(
        ["/serviceprovider/individual/update/<int:_id>"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def indvidual_update(self, _id):
        try:
            beneficiary = request.env["res.partner"].sudo().browse(_id)
            if not beneficiary:
                return request.render(
                    "g2p_registration_portal_base.error_template",
                    {"error_message": "Individual not found."},
                )
            land_model_id = request.env["ir.model"].sudo().search([("model", "=", "g2p.land.information")])

            # Fetching selections and other data
            ownership_type_selections = (
                request.env["ir.model.fields"]
                .sudo()
                .search([("model_id", "=", land_model_id.id), ("name", "=", "ownership_type")])
                .selection_ids
            )

            # Preparing data for rendering
            land_info_data = self._prepare_land_info_data(beneficiary, ownership_type_selections)
            crop_info_data, serialized_crop_info_data = self._prepare_crop_info_data(beneficiary)
            livestock_info_data, serialized_livestock_info_data = self._prepare_livestock_info_data(
                beneficiary
            )

            # Other data retrieval
            gender = request.env["gender.type"].sudo().search([])
            region = request.env["g2p.region"].sudo().search([])
            zone = request.env["g2p.zone"].sudo().search([("region", "=", beneficiary.region.id)])
            woreda = request.env["g2p.woreda"].sudo().search([("zone", "=", beneficiary.zone.id)])
            kebele = request.env["g2p.kebele"].sudo().search([("woreda", "=", beneficiary.woreda.id)])
            primary_language = request.env["g2p.lang"].sudo().search([])
            primary_cooperatives = request.env["g2p.primary.cooperative"].sudo().search([])
            cooperative_unions = request.env["g2p.cooperative.union"].sudo().search([])
            primary_commodities = request.env["g2p.primary.commodity"].sudo().search([])
            crops = request.env["g2p.crop"].sudo().search([])
            crop_illness_type = request.env["g2p.illness.type"].sudo().search([("illness_type", "=", "crop")])
            crop_water_source = request.env["g2p.water.source"].sudo().search([])
            livestock_types = request.env["g2p.livestock.type"].sudo().search([])
            livestock_illness_type = (
                request.env["g2p.illness.type"].sudo().search([("illness_type", "=", "animal")])
            )
            water_source = request.env["g2p.water.source"].sudo().search([])
            machinary_types = request.env["g2p.machinery"].sudo().search([])
            financial_access = request.env["g2p.finance.access"].sudo().search([])
            source_of_income = request.env["g2p.hh.income"].sudo().search([])
            model_id = request.env["ir.model"].sudo().search([("model", "=", "res.partner")])
            additional_info_data = self.get_additional_info(beneficiary)

            # additional_info = beneficiary.additional_g2p_info

            # # Check if additional_info is a string and needs to be converted to a dictionary
            # if isinstance(additional_info, str):
            #     try:
            #         additional_info = json.loads(additional_info)
            #     except json.JSONDecodeError:
            #         # Handle JSON decoding error if the string is not valid JSON
            #         additional_info = {}

            # # Initialize variables
            # other_kebele = ""
            # other_woreda = ""
            # other_primary_coop = ""
            # other_coop_union = ""
            # other_income = ""

            # # Check if additional_info is a dictionary and populate variables accordingly
            # if isinstance(additional_info, dict):
            #     if "Kebele" in additional_info:
            #         other_kebele = additional_info.get("Kebele", "")

            #     if "Woreda" in additional_info:
            #         other_woreda = additional_info.get("Woreda", "")

            #     if "Primary Cooperative" in additional_info:
            #         other_primary_coop = additional_info.get("Primary Cooperative", "")

            #     if "Cooperative Union" in additional_info:
            #         other_coop_union = additional_info.get("Cooperative Union", "")

            #     if "Household Income" in additional_info:
            #         other_income = additional_info.get("Household Income", "")

            # Handling phone numbers
            primary_phone, secondary_phone, other_phone = "", "", ""
            for phone in beneficiary.phone_number_ids:
                if phone.phone_type == "primary":
                    primary_phone = phone.phone_no
                elif phone.phone_type == "secondary":
                    secondary_phone = phone.phone_no
                elif phone.phone_type == "other":
                    other_phone = phone.phone_no

            # Handling UID and RID

            # uid, rid = "", ""
            # for reg_id in beneficiary.reg_ids:
            #     if beneficiary.has_national_id == "yes" and reg_id.id_type.name == "UID":
            #         uid = reg_id.value
            #     elif beneficiary.has_national_id == "no" and reg_id.id_type.name == "RID":
            #         rid = reg_id.value

            uid, rid = "", ""
            for reg_id in beneficiary.reg_ids:
                if reg_id.id_type.name == "UID":
                    uid = reg_id.value
                elif beneficiary.has_national_id == "no" and reg_id.id_type.name == "RID":
                    rid = reg_id.value

            has_uid = bool(uid)

            hh_is_household_head, household_head_selection_id = self._get_selection_id(
                model_id, "hh_is_household_head", beneficiary.hh_is_household_head
            )
            has_national_id, have_national_id_selection_id = self._get_selection_id(
                model_id, "has_national_id", beneficiary.has_national_id
            )
            farming_type, farming_type_selection_id = self._get_selection_id(
                model_id, "farming_type", beneficiary.farming_type
            )
            is_member_of_primary_cooperative, is_member_of_primary_id = self._get_selection_id(
                model_id, "is_member_of_primary_cooperative", beneficiary.is_member_of_primary_cooperative
            )
            is_member_of_cooperative_union, is_member_of_coop_id = self._get_selection_id(
                model_id, "is_member_of_cooperative_union", beneficiary.is_member_of_cooperative_union
            )
            is_member_in_farmer_cluster, is_member_in_farmer_cluster_selection_id = self._get_selection_id(
                model_id, "is_member_in_farmer_cluster", beneficiary.is_member_in_farmer_cluster
            )
            role_in_cluster, role_in_cluster_selection_id = self._get_selection_id(
                model_id, "role_in_farmer_cluster", beneficiary.role_in_farmer_cluster
            )
            access_to_machinery, access_to_machinery_selection_id = self._get_selection_id(
                model_id, "access_to_machinery", beneficiary.access_to_machinery
            )
            marital_status, marital_status_selection_id = self._get_selection_id(
                model_id, "martial_status", beneficiary.martial_status
            )
            education_level, education_level_selection_id = self._get_selection_id(
                model_id, "education", beneficiary.education
            )
            disability_status, disability_status_selection_id = self._get_selection_id(
                model_id, "is_disabled", beneficiary.is_disabled
            )
            do_you_use_fertilizer, do_you_use_fertilizer_selection_id = self._get_selection_id(
                model_id, "do_you_use_fertilizer", beneficiary.do_you_use_fertilizer
            )
            do_you_use_pesticide, do_you_use_pesticide_selection_id = self._get_selection_id(
                model_id, "do_you_use_pesticide", beneficiary.do_you_use_pesticide
            )
            do_you_use_insecticide, do_you_use_insecticide_selection_id = self._get_selection_id(
                model_id, "do_you_use_insecticide", beneficiary.do_you_use_insecticide
            )
            do_you_use_improved_seed, do_you_use_improved_seed_selection_id = self._get_selection_id(
                model_id, "do_you_use_improved_seed", beneficiary.do_you_use_improved_seed
            )
            has_finance_access, has_finance_access_selection_id = self._get_selection_id(
                model_id, "has_finance_access", beneficiary.has_finance_access
            )
            has_personal_phone, has_personal_phone_selection_id = self._get_selection_id(
                model_id, "has_personal_phone", beneficiary.has_personal_phone
            )

            # Rendering the template with the prepared data
            return request.render(
                "g2p_ati_service_provider_portal.ati_individual_registrant_update_form_template",
                {
                    "beneficiary": beneficiary,
                    "has_national_id": has_national_id,
                    "has_uid": has_uid,
                    "uid": uid,
                    "rid": rid,
                    "hh_is_household_head": hh_is_household_head,
                    "gender": gender,
                    "region": region,
                    "zone": zone,
                    "woreda": woreda,
                    "kebele": kebele,
                    "primary_language": primary_language,
                    "has_personal_phone": has_personal_phone,
                    "primary_phone": primary_phone,
                    "secondary_phone": secondary_phone,
                    "other_phone": other_phone,
                    "farming_type": farming_type,
                    "is_member_of_primary_cooperative": is_member_of_primary_cooperative,
                    "is_member_of_cooperative_union": is_member_of_cooperative_union,
                    "is_member_in_farmer_cluster": is_member_in_farmer_cluster,
                    "primary_cooperatives": primary_cooperatives,
                    "cooperative_unions": cooperative_unions,
                    "primary_commodities": primary_commodities,
                    "role_in_cluster": role_in_cluster,
                    "ownership_type_selections": ownership_type_selections,
                    "land_info_data": land_info_data,
                    "crop_info_data": crop_info_data,
                    "serialized_crop_info_data": serialized_crop_info_data,
                    "livestock_info_data": livestock_info_data,
                    "serialized_livestock_info_data": serialized_livestock_info_data,
                    "crops": crops,
                    "crop_illness_type": crop_illness_type,
                    "crop_water_source": crop_water_source,
                    "livestock_types": livestock_types,
                    "livestock_illness_type": livestock_illness_type,
                    "water_source": water_source,
                    "access_to_machinery": access_to_machinery,
                    "machinary_types": machinary_types,
                    "marital_status": marital_status,
                    "education_level": education_level,
                    "disability_status": disability_status,
                    "do_you_use_fertilizer": do_you_use_fertilizer,
                    "do_you_use_pesticide": do_you_use_pesticide,
                    "do_you_use_insecticide": do_you_use_insecticide,
                    "do_you_use_improved_seed": do_you_use_improved_seed,
                    "has_finance_access": has_finance_access,
                    "financial_access": financial_access,
                    "source_of_income": source_of_income,
                    "have_national_id_selection_id": have_national_id_selection_id,
                    "household_head_selection_id": household_head_selection_id,
                    "farming_type_selection_id": farming_type_selection_id,
                    "role_in_cluster_selection_id": role_in_cluster_selection_id,
                    "is_member_in_farmer_cluster_selection_id": is_member_in_farmer_cluster_selection_id,
                    "is_member_of_cooperative_union_selection_id": is_member_of_coop_id,
                    "is_member_of_primary_cooperative_selection_id": is_member_of_primary_id,
                    "education_level_selection_id": education_level_selection_id,
                    "marital_status_selection_id": marital_status_selection_id,
                    "access_to_machinery_selection_id": access_to_machinery_selection_id,
                    "access_to_finance_selection_id": has_finance_access_selection_id,
                    "disability_status_selection_id": disability_status_selection_id,
                    "has_personal_phone_selection_id": has_personal_phone_selection_id,
                    "do_you_use_fertilizer_selection_id": do_you_use_fertilizer_selection_id,
                    "do_you_use_pesticide_selection_id": do_you_use_pesticide_selection_id,
                    "do_you_use_insecticide_selection_id": do_you_use_insecticide_selection_id,
                    "do_you_use_improved_seed_selection_id": do_you_use_improved_seed_selection_id,
                    "has_finance_access_selection_id": has_finance_access_selection_id,
                    "other_kebele": additional_info_data["other_kebele"],
                    "other_woreda": additional_info_data["other_woreda"],
                    "other_primary_coop": additional_info_data["other_primary_coop"],
                    "other_coop_union": additional_info_data["other_coop_union"],
                    "other_income": additional_info_data["other_income"],
                },
            )
        except Exception as e:
            return request.render(
                "g2p_registration_portal_base.error_template",
                {"error_message": str(e)},
            )

    def get_additional_info(self, beneficiary):
        additional_info = beneficiary.additional_g2p_info

        # Check if additional_info is a string and convert it to a dictionary
        if isinstance(additional_info, str):
            try:
                additional_info = json.loads(additional_info)
            except json.JSONDecodeError:
                additional_info = {}

        # Initialize default values
        info = {
            "other_kebele": "",
            "other_woreda": "",
            "other_primary_coop": "",
            "other_coop_union": "",
            "other_income": "",
        }

        # Populate the info dictionary if additional_info is valid
        if isinstance(additional_info, dict):
            info["other_kebele"] = additional_info.get("Kebele", "")
            info["other_woreda"] = additional_info.get("Woreda", "")
            info["other_primary_coop"] = additional_info.get("Primary Cooperative", "")
            info["other_coop_union"] = additional_info.get("Cooperative Union", "")
            info["other_income"] = additional_info.get("Household Income", "")

        return info

    def _get_selection_id(self, model, field_name, value):
        selection_ids = (
            request.env["ir.model.fields"]
            .sudo()
            .search([("model_id", "=", model.id), ("name", "=", field_name)])
            .selection_ids
        )
        selection_id = False
        for choice in selection_ids:
            if choice.value == value:
                selection_id = choice.id

        return [selection_ids, selection_id]

    def _prepare_land_info_data(self, beneficiary, ownership_type_selections):
        land_info_data = []
        for index, land_info in enumerate(beneficiary.land_information_ids, start=1):
            ownership_selection_id = False
            for choice in ownership_type_selections:
                if choice.value == land_info.ownership_type:
                    ownership_selection_id = choice.id

            land_certificate = {
                "filename": land_info.land_certificate.name if land_info.land_certificate else "",
                "content": (
                    base64.b64encode(land_info.land_certificate.data).decode("utf-8")
                    if land_info.land_certificate
                    else ""
                ),
                "updated": False,
            }
            certificate_url = land_info.land_certificate.url if land_info.land_certificate else ""

            land_info_data.append(
                {
                    "index": index,
                    "id": land_info.id,
                    "total_land_area": land_info.total_land_area,
                    "land_id": land_info.land_id,
                    "ownership_type_selection_id": ownership_selection_id,
                    "certificate_id": certificate_url,
                    "land_certificate": land_certificate,
                }
            )
        return land_info_data

    def _prepare_crop_info_data(self, beneficiary):
        crop_info_data = []
        serialized_crop_info_data = []
        for index, crop_info in enumerate(beneficiary.crop_information_ids, start=1):
            crop_info_data.append(
                {
                    "index": index,
                    "id": crop_info.id,
                    "crop": crop_info.crop,
                    "crop_planted_date": crop_info.collected_gc,
                    # "crop_is_diseased_selection_id": crop_is_diseased_selection_id,
                }
            )
            serialized_crop_info_data.append(
                {
                    "index": index,
                    "id": crop_info.id,
                    "crop_id": crop_info.crop.id,
                    "crop_planted_date": crop_info.collected_gc,
                }
            )

        return crop_info_data, serialized_crop_info_data

    def _prepare_livestock_info_data(self, beneficiary):
        livestock_info_data = []
        serialized_livestock_info_data = []
        for index, livestock_info in enumerate(beneficiary.livestock_information_ids, start=1):
            # livestock_is_diseased_selection_id = self._get_selection_id(
            #     livestock_info._name, "is_diseased", livestock_info.is_diseased
            # )
            livestock_info_data.append(
                {
                    "index": index,
                    "id": livestock_info.id,
                    "livestock_type": livestock_info.livestock_type,
                    "number_of_livestock": livestock_info.number_of_livestock,
                    "is_diseased": livestock_info.is_diseased,
                    "illness_type": livestock_info.illness_type,
                    # "livestock_is_diseased_selection_id": livestock_is_diseased_selection_id,
                }
            )
            serialized_livestock_info_data.append(
                {
                    "index": index,
                    "id": livestock_info.id,
                    "livestock_type": livestock_info.livestock_type.id,
                    "is_diseased": livestock_info.is_diseased,
                    "illness_type": [it.id for it in livestock_info.illness_type],
                }
            )
        return livestock_info_data, serialized_livestock_info_data

    @http.route(
        "/serviceprovider/individual/update/submit",
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def update_individual_submit(self, **kw):
        try:
            member = request.env["res.partner"].sudo().browse(int(kw.get("id holder")))

            has_national_id = member.has_national_id
            has_personal_phone = member.has_personal_phone
            primary_Language = member.primary_Language
            is_member_of_primary_cooperative = member.is_member_of_primary_cooperative
            if is_member_of_primary_cooperative == "yes":
                primary_cooperatives = member.primary_cooperatives
            else:
                primary_cooperatives = " "
            is_member_of_cooperative_union = member.is_member_of_cooperative_union
            cooperative_unions = member.cooperative_unions
            is_member_in_farmer_cluster = member.is_member_in_farmer_cluster
            primary_commodity = member.primary_commodity
            role_in_farmer_cluster = member.role_in_farmer_cluster
            martial_status = member.martial_status
            education = member.education
            crop_water_sources = member.crop_water_sources
            livestock_water_sources = member.livestock_water_sources
            access_to_machinery = member.access_to_machinery
            type_of_machinery = member.type_of_machinery
            has_finance_access = member.has_finance_access
            finance_accesses = member.finance_accesses
            martial_status = member.martial_status
            education = member.education
            hh_income_type = member.hh_income_type
            do_you_use_fertilizer = member.do_you_use_fertilizer
            do_you_use_pesticide = member.do_you_use_pesticide
            do_you_use_insecticide = member.do_you_use_insecticide
            do_you_use_improved_seed = member.do_you_use_improved_seed

            # Helper function to fetch selection values

            # Update individual details

            do_you_use_fertilizer = (
                self.get_selection_value("ir.model.fields.selection", kw.get("have_used_fertilizer"))
                or member.do_you_use_fertilizer
            )
            do_you_use_pesticide = (
                self.get_selection_value("ir.model.fields.selection", kw.get("have_used_pesticide"))
                or member.do_you_use_pesticide
            )
            do_you_use_insecticide = (
                self.get_selection_value("ir.model.fields.selection", kw.get("have_used_insecticide"))
                or member.do_you_use_insecticide
            )
            do_you_use_improved_seed = (
                self.get_selection_value("ir.model.fields.selection", kw.get("have_used_improved_seed"))
                or member.do_you_use_improved_seed
            )

            has_personal_phone = (
                self.get_selection_value("ir.model.fields.selection", kw.get("has_personal_phone"))
                or member.has_personal_phone
            )

            has_national_id = (
                self.get_selection_value("ir.model.fields.selection", kw.get("has_national_id"))
                or member.has_national_id
            )
            is_disabled = (
                self.get_selection_value("ir.model.fields.selection", kw.get("is_disabled"))
                or member.is_disabled
            )
            farming_type = (
                self.get_selection_value("ir.model.fields.selection", kw.get("farming_type"))
                or member.farming_type
            )
            primary_Language = int(kw.get("primary_language", member.primary_Language))
            name = " ".join(
                filter(None, [kw.get("given_name", ""), kw.get("family_name", ""), kw.get("gf_name_eng", "")])
            )

            # National ID handling
            # reg_ids = []
            # if has_national_id == "yes":
            #     id_type = request.env["g2p.id.type"].sudo().search([("name", "=", "UID")], limit=1)
            #     reg_ids = [(0, 0, {"id_type": id_type.id, "value": kw.get("uid"), "status":"valid"})]
            # elif has_national_id == "no" and kw.get("rid"):
            #     id_type = request.env["g2p.id.type"].sudo().search([("name", "=", "RID")], limit=1)
            #     reg_ids = [(0, 0, {"id_type": id_type.id, "value": kw.get("rid"), "status":"valid"})]

            reg_ids = []

            # Check if an existing RID is present
            existing_rid = None

            rid_input = kw.get("rid")

            for reg_id in member.reg_ids:
                if rid_input:
                    if reg_id.id_type.name == "RID" and reg_id.value == rid_input:
                        existing_rid = reg_id
                        break

            # Handling UID
            if kw.get("uid"):
                id_type_uid = request.env["g2p.id.type"].sudo().search([("name", "=", "UID")], limit=1)
                if id_type_uid:
                    reg_ids.append(
                        (0, 0, {"id_type": id_type_uid.id, "value": kw.get("uid"), "status": "valid"})
                    )

                if existing_rid:
                    try:
                        check_rid = (
                            request.env["g2p.reg.id"].sudo().search([("id", "=", existing_rid.id)], limit=1)
                        )
                        if check_rid:
                            reg_ids.append(
                                (
                                    0,
                                    0,
                                    {
                                        "id_type": existing_rid.id_type.id,
                                        "value": existing_rid.value,
                                        "status": existing_rid.status,
                                    },
                                )
                            )
                        else:
                            _logger.info(
                                f"RID with ID {existing_rid.id} not found in the database. Skipping update."
                            )
                    except Exception as e:
                        _logger.info(f"Error while checking existing RID: {e}")
                has_national_id = "yes"

            if has_national_id == "no" and kw.get("rid"):
                #     if existing_rid:
                #         print("existing")
                #         try:

                #             check_rid = request.env['g2p.reg.id'].sudo().search([('id', '=', existing_rid.id)], limit=1)
                #             if check_rid:

                #                 reg_ids.append((0,0, {
                #                     "id_type": existing_rid.id_type.id,
                #                     "value": existing_rid.value,
                #                     "status": existing_rid.status
                #                 }))
                #             else:
                #                 print(f"RID with ID {existing_rid.id} not found in the database. Skipping update.")
                #         except Exception as e:
                #             print(f"Error while checking existing RID: {e}")
                #     print("new rid")

                # else:

                id_type_rid = request.env["g2p.id.type"].sudo().search([("name", "=", "RID")], limit=1)
                if id_type_rid:
                    reg_ids.append(
                        (0, 0, {"id_type": id_type_rid.id, "value": kw.get("rid"), "status": "valid"})
                    )

            # Handle phone numbers
            ethiopia_country_id = (
                request.env["res.country"].sudo().search([("name", "=", "Ethiopia")], limit=1).id
            )

            phone_number_ids = self.handle_phone_numbers(
                has_phone=has_personal_phone,
                primary_phone=kw.get("primary_phone"),
                secondary_phone=kw.get("secondary_phone"),
                other_phone=kw.get("other_phone"),
                country_id=ethiopia_country_id,
            )

            # Socio-economic data
            martial_status = self.get_selection_value("ir.model.fields.selection", kw.get("marital_status"))
            education = self.get_selection_value("ir.model.fields.selection", kw.get("education_level"))
            hh_income_type = (
                [(6, 0, list(map(int, request.httprequest.form.getlist("hh_income_type"))))]
                if kw.get("hh_income_type")
                else []
            )

            # Membership details
            is_member_of_primary_cooperative = self.get_selection_value(
                "ir.model.fields.selection", kw.get("is_member_of_primary_coop")
            )
            is_member_of_cooperative_union = self.get_selection_value(
                "ir.model.fields.selection", kw.get("is_member_of_coop_union")
            )
            is_member_in_farmer_cluster = self.get_selection_value(
                "ir.model.fields.selection", kw.get("in_farmer_cluster")
            )

            crop_water_sources = (
                [(6, 0, list(map(int, request.httprequest.form.getlist("crop_water_source"))))]
                if kw.get("crop_water_source")
                else []
            )
            crop_ws = request.httprequest.form.getlist("crop_water_source")
            if crop_ws:
                crop_water_sources_ids = [int(id) for id in crop_ws]
                crop_water_sources = [(6, 0, crop_water_sources_ids)]

            # TODO: a new function needs to be added here
            # crop_info_data = self._prepare_crop_info_data(kw)

            # Livestock information
            livestock_water_sources = (
                [(6, 0, list(map(int, request.httprequest.form.getlist("livestock_water_source"))))]
                if kw.get("livestock_water_source")
                else []
            )

            livestock_ws = request.httprequest.form.getlist("livestock_water_source")
            if livestock_ws:
                livestock_water_sources_ids = [int(id) for id in livestock_ws]
                livestock_water_sources = [(6, 0, livestock_water_sources_ids)]

            # TODO: a new function needs to be added here
            # livestock_info_data = self._prepare_livestock_info_data(kw)

            # Access to machinery
            access_to_machinery = self.get_selection_value(
                "ir.model.fields.selection", kw.get("access_to_machinery")
            )
            type_of_machinery = (
                [(6, 0, list(map(int, request.httprequest.form.getlist("machinery_types"))))]
                if kw.get("machinery_types")
                else []
            )

            # Financial service access
            has_finance_access = self.get_selection_value(
                "ir.model.fields.selection", kw.get("has_finance_access")
            )
            finance_accesses = (
                [(6, 0, list(map(int, request.httprequest.form.getlist("finance_accesses"))))]
                if kw.get("finance_accesses")
                else []
            )

            if kw.get("is_member_of_primary_coop") and kw.get("is_member_of_primary_coop").strip():
                is_member_of_primary_cooperative = self.get_selection_value(
                    "ir.model.fields.selection", kw.get("is_member_of_primary_coop")
                )

            if is_member_of_primary_cooperative == "yes":
                if kw.get("name_of_primary_coop") and kw.get("name_of_primary_coop").strip():
                    primary_cooperatives = int(kw.get("name_of_primary_coop"))
            if kw.get("is_member_of_coop_union") and kw.get("is_member_of_coop_union").strip():
                is_member_of_cooperative_union = self.get_selection_value(
                    "ir.model.fields.selection", kw.get("is_member_of_coop_union")
                )
            if is_member_of_cooperative_union == "yes":
                if kw.get("name_of_coop_union") and kw.get("name_of_coop_union").strip():
                    cooperative_unions = int(kw.get("name_of_coop_union"))
            if kw.get("in_farmer_cluster") and kw.get("in_farmer_cluster").strip():
                is_member_in_farmer_cluster = self.get_selection_value(
                    "ir.model.fields.selection", kw.get("in_farmer_cluster")
                )
            if is_member_in_farmer_cluster == "yes":
                if kw.get("primary_commodity") and kw.get("primary_commodity").strip():
                    primary_commodity = int(kw.get("primary_commodity"))
                if kw.get("role_in_cluster") and kw.get("role_in_cluster").strip():
                    role_in_farmer_cluster = self.get_selection_value(
                        "ir.model.fields.selection", kw.get("role_in_cluster")
                    )

            backend_id = (
                request.env.ref("storage_backend.default_storage_backend").id
                or request.env["storage.backend"].sudo().search([], limit=1).id
            )

            land_info_data = self.get_land_info_data(kw, backend_id)

            crop_info_data = self.get_crop_info_data(kw)

            livestock_info_data = self.get_livestock_info_data(kw)

            supporting_documents_ids = self.get_supporting_documents_ids(kw)

            additional_info_json = self.handle_other_info(kw)
            # Clean up existing data

            update_records = {
                "has_national_id": has_national_id,
                "primary_Language": primary_Language,
                "given_name": kw.get("given_name"),
                "family_name": kw.get("family_name"),
                "gf_name_eng": kw.get("gf_name_eng"),
                "reg_ids": reg_ids,
                "name": name,
                "first_name_amh": kw.get("first_name_amh"),
                "family_name_amh": kw.get("family_name_amh"),
                "gf_name_amh": kw.get("gf_name_amh"),
                "first_name_other": kw.get("first_name_other"),
                "family_name_other": kw.get("family_name_other"),
                "gf_name_other": kw.get("gf_name_other"),
                "region": int(kw.get("region", member.region)),
                "zone": int(kw.get("zone", member.zone)),
                "woreda": int(kw.get("woreda", member.woreda)),
                "kebele": int(kw.get("kebele", member.kebele)),
                "birthdate": kw.get("birthdate", member.birthdate),
                "gender": kw.get("gender", member.gender),
                "has_personal_phone": has_personal_phone,
                "phone_number_ids": phone_number_ids,
                "email": kw.get("email", member.email),
                "is_disabled": is_disabled,
                "farming_type": farming_type,
                "martial_status": martial_status,
                "education": education,
                "hh_income_type": hh_income_type,
                "is_member_of_primary_cooperative": is_member_of_primary_cooperative,
                "primary_cooperatives": primary_cooperatives,
                "is_member_of_cooperative_union": is_member_of_cooperative_union,
                "cooperative_unions": cooperative_unions,
                "is_member_in_farmer_cluster": is_member_in_farmer_cluster,
                "primary_commodity": primary_commodity,
                "role_in_farmer_cluster": role_in_farmer_cluster,
                "land_information_ids": land_info_data,
                "supporting_documents_ids": supporting_documents_ids,
                "crop_water_sources": crop_water_sources,
                "crop_information_ids": crop_info_data,
                "livestock_water_sources": livestock_water_sources,
                "livestock_information_ids": livestock_info_data,
                "access_to_machinery": access_to_machinery,
                "type_of_machinery": type_of_machinery,
                "has_finance_access": has_finance_access,
                "finance_accesses": finance_accesses,
                "do_you_use_fertilizer": do_you_use_fertilizer,
                "do_you_use_pesticide": do_you_use_pesticide,
                "do_you_use_insecticide": do_you_use_insecticide,
                "do_you_use_improved_seed": do_you_use_improved_seed,
                "additional_g2p_info": additional_info_json,
                "supporting_documents_ids": kw.get("supporting_documents_ids", []),
            }
            # Update member details
            user = request.env.user

            # Check if the user is not a portal user (not in the 'Portal' group)

            is_locked = False
            edit_state = member.edit_state
            if user.has_group("base.group_portal") and edit_state == "locked":
                is_locked = True
            else:
                is_locked = False
                member.reg_ids.unlink()
                member.phone_number_ids.unlink()
                member.land_information_ids.unlink()
                member.crop_information_ids.unlink()
                member.livestock_information_ids.unlink()
                member.supporting_documents_ids.unlink()

            member.sudo().write(update_records)
            # request.session['update_success'] = True
            # return json.dumps({'status': 'success', 'message': 'Record updated successfully'})

            response = None

            group = kw.get("group")

            if not group:
                response = request.redirect(f"/serviceprovider/individual/update/{member.id}")

            if group:
                response = request.redirect(f"/serviceprovider/individual/update/{member.id}?group={group}")

            if is_locked == True:
                response.set_cookie("popup_status", "successful", max_age=10)
                response.set_cookie("popup_msg", "Update Sent For Validation!", max_age=10)
                return response
            else:
                response.set_cookie("popup_status", "successful", max_age=10)
                response.set_cookie("popup_msg", "Record Updated Successfully!", max_age=10)
                return response

            # return request.redirect(f"/serviceprovider/individual/update/{member.id}")

        except Exception as e:
            return request.render(
                "g2p_registration_portal_base.error_template",
                {"error_message": f"An error occurred: {e}"},
            )

    def handle_other_info(self, kw):
        other_info = {}

        # house hold income
        # income_ids = request.httprequest.form.getlist("hh_income_type")
        searched_income_id = (
            request.env["g2p.hh.income"]
            .sudo()
            .search(["|", ("name", "=", "Others"), ("name", "=", "Other")])
            .id
        )

        if str(searched_income_id) in request.httprequest.form.getlist("hh_income_type"):
            other_income_details = kw.get("other_income_details")
            if other_income_details:
                other_info["Household Income"] = other_income_details

        # woreda

        woreda_id = kw.get("woreda")
        other_woreda = kw.get("other_woreda")

        searched_woreda_id = (
            request.env["g2p.woreda"].sudo().search(["|", ("name", "=", "Others"), ("name", "=", "Other")]).id
        )

        if searched_woreda_id == int(woreda_id):
            if other_woreda:
                other_info["Woreda"] = other_woreda

        # kebele
        kebele_id = kw.get("kebele")
        other_kebele = kw.get("other_kebele")

        searched_kebele_id = (
            request.env["g2p.kebele"]
            .sudo()
            .search(
                [
                    "|",
                    ("name", "=", "Others"),
                    ("name", "=", "Other"),
                ]
            )
            .id
        )

        if searched_kebele_id == int(kebele_id):
            if other_kebele:
                other_info["Kebele"] = other_kebele

        # primary coop
        primary_coop_ids = kw.get("name_of_primary_coop")
        searched_primary_coop_id = (
            request.env["g2p.primary.cooperative"]
            .sudo()
            .search(["|", ("name", "=", "Others"), ("name", "=", "Other")])
            .id
        )

        if str(searched_primary_coop_id) in primary_coop_ids:
            other_primary_coop = kw.get("other_primary_coop")
            if other_primary_coop:
                other_info["Primary Cooperative"] = other_primary_coop

        # coop union
        coop_union_ids = kw.get("name_of_coop_union")
        searched_coop_union_id = (
            request.env["g2p.cooperative.union"]
            .sudo()
            .search(["|", ("name", "=", "Others"), ("name", "=", "Other")])
            .id
        )

        if str(searched_coop_union_id) in coop_union_ids:
            other_coop_union = kw.get("other_coop_union")
            if other_coop_union:
                other_info["Cooperative Union"] = other_coop_union

        return json.dumps(other_info)

    def get_selection_value(self, model, selection_id):
        if selection_id and len(selection_id) > 0:
            return (
                (request.env[model].sudo().search([("id", "=", selection_id)]).value)
                if selection_id
                else None
            )
        else:
            return False

    def _extract_id_from_string(self, string):
        match = re.match(r"^updated_(\d+)$", string)
        if match:
            return int(match.group(1))
        return None

    def get_land_info_data(self, kw, backend_id):
        land_info_data = []
        land_indices = set()

        _logger.info("Incoming KW data:")
        _logger.info(kw)

        # Extract valid land indices from the input data
        valid_keys = [key for key in kw.keys() if "{9999}" not in key]

        kw["supporting_documents_ids"] = []

        for key in valid_keys:
            if key.startswith("land_ownership_type_"):
                try:
                    land_index = int(key.split("_")[-1])
                    land_indices.add(land_index)

                except ValueError:
                    continue

        doc_tag = request.env["g2p.document.tag"].sudo().get_or_create_tag_from_name("Land Certificate")
        if not doc_tag:
            doc_tag = request.env["g2p.document.tag"].sudo().create({"name": "Land Certificate"})

        existing_certificates = {}

        _logger.info(f"land_index: {land_indices}")

        for index in land_indices:
            existing_land_info = self._get_existing_land_info(index)
            if existing_land_info:
                existing_certificates[index] = existing_land_info

            # Collect new land info from kw
            ownership_type = kw.get(f"land_ownership_type_{index}")
            if ownership_type == "":
                continue  # Skip if ownership type is empty

            land_id = kw.get(f"land_id_{index}")
            land_area = kw.get(f"total_land_area_{index}")

            land_ownership_type = (
                request.env["ir.model.fields.selection"].sudo().search([("id", "=", ownership_type)]).value
            )

            land_info_dict = {
                "ownership_type": land_ownership_type,
                "total_land_area": land_area,
                "land_id": land_id,
            }

            land_certificate_key = f"land_certificate_{index}"
            updated_certificate_key = f"updated_certificate_{index}"

            # _logger.info(f"land_certificate_{index}")
            # _logger.info(kw.get(f"land_certificate_{index}"))
            # _logger.info(kw.get(f"updated_certificate_{index}"))

            if kw.get(updated_certificate_key) is None:
                _logger.info("new")
                _logger.info(kw.get(updated_certificate_key))

                # New certificate upload
                land_certificate = kw.get(land_certificate_key)
                binary_content = base64.b64encode(land_certificate.read()).decode("utf-8")
                storage_file = (
                    request.env["storage.file"]
                    .sudo()
                    .create(
                        {
                            "backend_id": backend_id,
                            "name": land_certificate.filename,
                            "data": binary_content,
                            "tags_ids": [(4, doc_tag.id)],
                        }
                    )
                )
                land_info_dict["land_certificate"] = storage_file.id
                kw["supporting_documents_ids"].append((4, storage_file.id))

            elif kw.get(updated_certificate_key).startswith("updated"):
                _logger.info("updated")
                _logger.info(kw.get(updated_certificate_key))

                _logger.info(f" before the extract_id_from_string  {kw.get(updated_certificate_key)}")

                land_id = self._extract_id_from_string(kw.get(updated_certificate_key))
                land = self._get_existing_land_info(land_id)

                storage_file_old = (
                    request.env["storage.file"].sudo().search([("id", "=", land.land_certificate.id)])
                )

                # storage_file_old = self.env['storage.file'].browse(land.land_certificate.id)
                storage_file_old.unlink()

                land_certificate = kw.get(land_certificate_key)
                binary_content = base64.b64encode(land_certificate.read()).decode("utf-8")
                storage_file = (
                    request.env["storage.file"]
                    .sudo()
                    .create(
                        {
                            "backend_id": backend_id,
                            "name": land_certificate.filename,
                            "data": binary_content,
                            "tags_ids": [(4, doc_tag.id)],
                        }
                    )
                )
                land_info_dict["land_certificate"] = storage_file.id
                kw["supporting_documents_ids"].append((4, storage_file.id))

            elif (
                not kw.get(updated_certificate_key).startswith("updated")
                and kw.get(updated_certificate_key) is not None
            ):
                land_id = int(kw.get(updated_certificate_key))
                land = self._get_existing_land_info(land_id)
                # land_info_dict["land_certificate"] = land.land_certificate.id
                _logger.info(f"land_certificate id {land.land_certificate.id}")

                storage_file_old = (
                    request.env["storage.file"].sudo().search([("id", "=", land.land_certificate.id)])
                )
                storage_file_old.unlink()

                _logger.info(f"land_certificate id2 {storage_file_old.id}")

                storage_file = (
                    request.env["storage.file"]
                    .sudo()
                    .create(
                        {
                            "backend_id": backend_id,
                            "name": land.land_certificate.name,
                            "data": land.land_certificate.data,
                            "tags_ids": [(4, doc_tag.id)],
                        }
                    )
                )

                land_info_dict["land_certificate"] = storage_file.id

                kw["supporting_documents_ids"].append((4, storage_file.id))

            # Append the land info dictionary to the data list
            land_info_data.append((0, 0, land_info_dict))

        return land_info_data

    # def get_land_info_data(self, kw, backend_id):
    #     land_info_data = []
    #     land_indices = set()

    #     _logger.info("The KW")
    #     _logger.info(kw)

    #     valid_keys = [key for key in kw.keys() if "{9999}" not in key]
    #     for key in valid_keys:
    #         if key.startswith("land_ownership_type_"):
    #             try:
    #                 land_index = int(key.split("_")[-1])
    #                 land_indices.add(land_index)
    #             except ValueError:
    #                 continue

    #     doc_tag = request.env["g2p.document.tag"].sudo().get_tag_by_name("Land Certificate")
    #     if not doc_tag:
    #         doc_tag = request.env["g2p.document.tag"].sudo().create({"name": "Land Certificate"})

    #     existing_certificates = {}  # Dictionary to hold existing certificates by index

    #     # Retrieve existing land information for the current beneficiary
    #     for index in land_indices:
    #         _logger.info(f"the index {index}")
    #         existing_land_info = self._get_existing_land_info(index)  # Implement this method to fetch existing data
    #         if existing_land_info:
    #             existing_certificates[index] = existing_land_info

    #         ownership_type = kw.get(f"land_ownership_type_{index}")
    #         if ownership_type == "":
    #             continue

    #         land_id = kw.get(f"land_id{index}")
    #         land_area = kw.get(f"total_land_area{index}")

    #         land_ownership_type = (
    #             request.env["ir.model.fields.selection"]
    #             .sudo()
    #             .search([("id", "=", ownership_type)])
    #             .value
    #         )

    #         land_info_dict = {
    #             "ownership_type": land_ownership_type,
    #             "total_land_area": land_area,
    #             "land_id": land_id,
    #         }

    #         # Check if the certificate is updated (new upload)
    #         land_certificate_key = f"land_certificate_{index}"
    #         if kw.get(land_certificate_key) and kw.get(land_certificate_key).read():
    #             # New certificate uploaded, handle it as before
    #             land_certificate = kw.get(land_certificate_key)
    #             binary_content = base64.b64encode(land_certificate.read()).decode("utf-8")
    #             storage_file = (
    #                 request.env["storage.file"]
    #                 .sudo()
    #                 .create(
    #                     {
    #                         "backend_id": backend_id,
    #                         "name": land_certificate.filename,
    #                         "data": binary_content,
    #                         "tags_ids": [(4, doc_tag.id)],
    #                     }
    #                 )
    #             )
    #             land_info_dict["land_certificate"] = storage_file.id

    #         else:
    #             if index in existing_certificates:
    #                 land_info_dict["land_certificate"] = existing_certificates[index].land_certificate.id

    #         # Append the land info dict to the data list
    #         land_info_data.append((0, 0, land_info_dict))

    #     _logger.info(land_info_data)
    #     return land_info_data

    # def get_land_info_data(self, kw, backend_id):
    #     land_info_data = []
    #     land_indices = set()

    #     _logger.info("The KW")
    #     _logger.info(kw)

    #     valid_keys = [key for key in kw.keys() if "{9999}" not in key]
    #     for key in valid_keys:
    #         if key.startswith("land_ownership_type_"):
    #             try:
    #                 land_index = int(key.split("_")[-1])
    #                 land_indices.add(land_index)
    #             except ValueError:
    #                 continue

    #     doc_tag = request.env["g2p.document.tag"].sudo().get_tag_by_name("Land Certificate")
    #     if not doc_tag:
    #         doc_tag = request.env["g2p.document.tag"].sudo().create({"name": "Land Certificate"})

    #     existing_certificates = {}  # Dictionary to hold existing certificates by index

    #     # Retrieve existing land information for the current beneficiary
    #     for index in land_indices:
    #         existing_land_info = self._get_existing_land_info(index)  # Implement this method to fetch existing data
    #         if existing_land_info:
    #             existing_certificates[index] = existing_land_info

    #     for index in land_indices:
    #         ownership_type = kw.get(f"land_ownership_type_{index}")
    #         if ownership_type == "":
    #             continue

    #         land_id = kw.get(f"land_id{index}")
    #         land_area = kw.get(f"total_land_area{index}")

    #         land_ownership_type = (
    #             request.env["ir.model.fields.selection"].sudo().search([("id", "=", ownership_type)]).value
    #         )

    #         land_info_dict = {
    #             "ownership_type": land_ownership_type,
    #             "total_land_area": land_area,
    #             "land_id": land_id,
    #         }

    #         # Check if the certificate is updated
    #         land_certificate_key = f"land_certificate_{index}"
    #         updated_certificate_key = f"updated_certificate_{index}"
    #         # updated_value = kw.get(updated_certificate_key)

    #         if kw.get(land_certificate_key) and kw.get(land_certificate_key).read():
    #             # New certificate uploaded
    #             land_certificate = kw.get(land_certificate_key)
    #             binary_content = base64.b64encode(land_certificate.read()).decode("utf-8")
    #             storage_file = (
    #                 request.env["storage.file"]
    #                 .sudo()
    #                 .create(
    #                     {
    #                         "backend_id": backend_id,
    #                         "name": land_certificate.filename,
    #                         "data": binary_content,
    #                         "tags_ids": [(4, doc_tag.id)],
    #                     }
    #                 )
    #             )
    #             land_info_dict["land_certificate"] = storage_file.id
    #             # Set the hidden input value to false since the certificate is updated
    #             # land_info_dict["updated"] = False
    #         else:
    #             # If not updated, keep the existing certificate
    #             if index in existing_certificates:
    #                 land_info_dict["land_certificate"] = existing_certificates[index].land_certificate.id
    #                 # Set the hidden input value to the land ID since it is not updated
    #                 # land_info_dict["updated"] = land_id

    #         # Append the land info dict to the data list
    #         land_info_data.append((0, 0, land_info_dict))

    #     return land_info_data

    # def get_land_info_data(self, kw, backend_id):

    #     _logger.info(kw)
    #     land_info_data = []
    #     land_indices = set()

    #     valid_keys = [key for key in kw.keys() if "{9999}" not in key]
    #     for key in valid_keys:
    #         if key.startswith("land_ownership_type_"):
    #             try:
    #                 land_index = int(key.split("_")[-1])
    #                 land_indices.add(land_index)
    #             except ValueError:
    #                 continue

    #     doc_tag = request.env["g2p.document.tag"].sudo().get_tag_by_name("Land Certificate")
    #     if not doc_tag:
    #         doc_tag = request.env["g2p.document.tag"].sudo().create({"name": "Land Certificate"})

    #     existing_certificates = {}  # Dictionary to hold existing certificates by index

    #     # Retrieve existing land information for the current beneficiary
    #     for index in land_indices:
    #         existing_land_info = self._get_existing_land_info(index)  # Implement this method to fetch existing data
    #         if existing_land_info:
    #             existing_certificates[index] = existing_land_info

    #     for index in land_indices:
    #         ownership_type = kw.get(f"land_ownership_type_{index}")
    #         if ownership_type == "":
    #             continue

    #         land_id = kw.get(f"land_id{index}")
    #         land_area = kw.get(f"total_land_area{index}")

    #         land_ownership_type = (
    #             request.env["ir.model.fields.selection"].sudo().search([("id", "=", ownership_type)]).value
    #         )

    #         land_info_dict = {
    #             "ownership_type": land_ownership_type,
    #             "total_land_area": land_area,
    #             "land_id": land_id,
    #         }
    #          # lnd_idx = kw.get(f"land_certificate_{index}")

    #         existing_certificate_id = kw.get(f"land_certificate_{index}")

    #         # Check if the certificate is updated

    #         land_certificate_key = f"land_certificate_{index}"
    #         if kw.get(land_certificate_key) and kw.get(land_certificate_key).read():
    #             land_certificate = kw.get(land_certificate_key)
    #             binary_content = base64.b64encode(land_certificate.read()).decode("utf-8")

    #             storage_file = (
    #                 request.env["storage.file"]
    #                 .sudo()
    #                 .create(
    #                     {
    #                         "backend_id": backend_id,
    #                         "name": existing_certificate_id.filename,
    #                         "data": binary_content,
    #                         "tags_ids": [(4, doc_tag.id)],
    #                     }
    #                 )
    #             )
    #             land_info_dict["land_certificate"] = storage_file.id

    #         else:
    #             # If not updated, keep the existing certificate
    #             if index in existing_certificates:
    #                 land_info_dict["land_certificate"] = existing_certificates[index].land_certificate.id

    #         # Append the land info dict to the data list

    #         land_info_data.append((0, 0, land_info_dict))

    #     return land_info_data

    def _get_existing_land_info(self, index):
        # This method should retrieve existing land information from the database
        # For example, you can use:
        return request.env["g2p.land.information"].sudo().search([("id", "=", index)], limit=1)

    def get_crop_info_data(self, kw):
        crop_info_data = []
        crop_indices = set()

        valid_keys = [key for key in kw.keys() if "{9999}" not in key]
        for key in valid_keys:
            if key.startswith("crops_"):
                try:
                    crop_index = int(key.split("_")[-1])
                    crop_indices.add(crop_index)
                except ValueError:
                    continue

        for index in crop_indices:
            crop_id = kw.get(f"crops_{index}")

            crop_planted_date_id = kw.get(f"crop_planted_date{index}")

            if crop_id == "":
                continue
            if crop_planted_date_id == "":
                continue

            crop_info_data.append((0, 0, {"crop": crop_id, "collected_gc": crop_planted_date_id}))

        return crop_info_data

    def get_livestock_info_data(self, kw):
        livestock_info_data = []
        livestock_indices = set()

        valid_keys = [key for key in kw.keys() if "{9999}" not in key]
        for key in valid_keys:
            if key.startswith("livestock_types_"):
                try:
                    livestock_index = int(key.split("_")[-1])
                    livestock_indices.add(livestock_index)
                except ValueError:
                    continue

        for index in livestock_indices:
            livestock_type = kw.get(f"livestock_types_{index}")
            if livestock_type == "":
                continue
            number_of_livestock = kw.get(f"number_of_livestock_{index}")

            livestock_info_data.append(
                (
                    0,
                    0,
                    {
                        "livestock_type": livestock_type,
                        "number_of_livestock": number_of_livestock,
                    },
                )
            )

        return livestock_info_data

    def get_supporting_documents_ids(self, kw):
        supporting_documents_ids = []
        backend_id = (
            request.env.ref("storage_backend.default_storage_backend").id
            or request.env["storage.backend"].sudo().search([], limit=1).id
        )

        doc_tag = request.env["g2p.document.tag"].sudo().get_or_create_tag_from_name("Land Certificate")
        if not doc_tag:
            doc_tag = request.env["g2p.document.tag"].sudo().create({"name": "Land Certificate"})

        land_indices = set()
        valid_keys = [key for key in kw.keys() if "{9999}" not in key]
        for key in valid_keys:
            if key.startswith("land_ownership_type_"):
                try:
                    land_index = int(key.split("_")[-1])
                    land_indices.add(land_index)
                except ValueError:
                    continue

        for index in land_indices:
            if kw.get(f"land_certificate_{index}") and (f"land_certificate_{index}").strip():
                land_certificate = kw.get(f"land_certificate_{index}")
                binary_content = base64.b64encode(land_certificate.read()).decode("utf-8")
                storage_file = (
                    request.env["storage.file"]
                    .sudo()
                    .create(
                        {
                            "backend_id": backend_id,
                            "name": land_certificate.filename,
                            "data": binary_content,
                            "tags_ids": [(4, doc_tag.id)],
                        }
                    )
                )
                supporting_documents_ids.append((4, storage_file.id))

        return supporting_documents_ids

    def handle_phone_numbers(self, has_phone, primary_phone, secondary_phone, other_phone, country_id):
        phone_number_ids = []
        if has_phone == "yes":
            phone_number_ids.append(
                (0, 0, {"phone_no": primary_phone, "phone_type": "primary", "country_id": country_id})
            )
            if secondary_phone:
                phone_number_ids.append(
                    (
                        0,
                        0,
                        {
                            "phone_no": secondary_phone,
                            "phone_type": "secondary",
                            "country_id": country_id,
                        },
                    )
                )
        else:
            phone_number_ids.append(
                (0, 0, {"phone_no": other_phone, "phone_type": "other", "country_id": country_id})
            )
            if secondary_phone:
                phone_number_ids.append(
                    (
                        0,
                        0,
                        {
                            "phone_no": secondary_phone,
                            "phone_type": "secondary",
                            "country_id": country_id,
                        },
                    )
                )
        return phone_number_ids

    @http.route("/serviceprovider/individual", type="http", auth="user", website=True)
    def individual_list(self, **kw):
        user_id = request.env.user.id
        partner = request.env.user.partner_id

        individual = (
            request.env["res.partner"]
            .sudo()
            .search(
                [
                    ("active", "=", True),
                    ("is_registrant", "=", True),
                    ("is_group", "=", False),
                    ("is_farmer", "=", "yes"),
                    # "|",  # Logical OR operator
                    ("enumerator_user_id", "=", user_id),
                    # ("enumerator_user_id", "=", partner.odk_app_user.odk_user_id),
                ]
            )
        )

        region = request.env["g2p.region"].sudo().search([])
        zone = []
        woreda = []
        kebele = []
        return request.render(
            "g2p_registration_portal_base.individual_list",
            {"individual": individual, "region": region, "zone": zone, "wereda": woreda, "kebele": kebele},
        )

    @http.route("/serviceprovider/group", type="http", auth="user", website=True)
    def group_list(self, **kw):
        user_id = request.env.user.id
        partner = request.env.user.partner_id

        groups = (
            request.env["res.partner"]
            .sudo()
            .search(
                [
                    ("active", "=", True),
                    ("is_registrant", "=", True),
                    ("is_group", "=", True),
                    # "|",  # Logical OR operator
                    ("enumerator_user_id", "=", user_id),
                    # ("enumerator_user_id", "=", partner.odk_app_user.odk_user_id),
                ]
            )
        )
        region = request.env["g2p.region"].sudo().search([])
        zone = []
        woreda = []
        kebele = []
        return request.render(
            "g2p_registration_portal_base.group_list",
            {"groups": groups, "region": region, "zone": zone, "wereda": woreda, "kebele": kebele},
        )

    @http.route(
        "/serviceprovider/member/update/",
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def update_member(self, **kw):
        member_id = kw.get("member_id")

        try:
            group_id = kw.get("group_id")

            if not group_id:
                return json.dumps({"error": "Group ID is required"})

            group_rec = request.env["res.partner"].sudo().browse(int(group_id))
            if not group_rec.exists():
                return json.dumps({"error": "Group not found"})

            # Fetch the member (beneficiary) record
            beneficiary = request.env["res.partner"].sudo().browse(int(member_id))

            # Initialize kind_name to be populated from group membership
            kind_name = None

            # Search for the membership of this individual in the group
            for membership in group_rec.group_membership_ids:
                if membership.individual.id == int(member_id):
                    kind_name = membership.kind.id if membership.kind else None
                    break

            # If the beneficiary is found, populate the existing values
            if beneficiary:
                exist_value = {
                    "given_name": beneficiary.given_name,
                    "family_name": beneficiary.family_name,
                    "gf_name_eng": beneficiary.gf_name_eng,
                    "dob": str(beneficiary.birthdate),
                    "gender": beneficiary.gender,
                    "kind": kind_name,  # Populate the kind name
                    "id": beneficiary.id,
                }
                return json.dumps(exist_value)

        except Exception as e:
            _logger.error("ERROR LOG IN UPDATE MEMBER%s", e)
            return json.dumps({"error": "Failed to retrieve member data"})

    @http.route(
        "/serviceprovider/family_member/update/submit/",
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def update_family_member_submit(self, **kw):
        res = dict()
        try:
            group_id = kw.get("group_id")
            member_id = int(kw.get("member_id"))
            member = request.env["res.partner"].sudo().browse(member_id)
            if not group_id:
                return json.dumps({"error": "Group ID is required"})

            group_rec = request.env["res.partner"].sudo().browse(int(group_id))
            if not group_rec.exists():
                return json.dumps({"error": "Group not found"})

            relationship = int(kw.get("Relationship"))
            relationship = [(6, 0, [relationship])]

            if member:
                given_name = kw.get("given_name")
                family_name = kw.get("family_name")
                gf_name_eng = kw.get("gf_name_eng")
                birthdate = kw.get("birthdate")
                gender = kw.get("gender")

                full_name = f"{given_name} {family_name} {gf_name_eng}"

                partner_data = {
                    "given_name": given_name,
                    "family_name": family_name,
                    "gf_name_eng": gf_name_eng,
                    "name": full_name,
                    "birthdate": str(birthdate),
                    "gender": gender,
                    "is_group": False,
                }

                member.sudo().write(partner_data)

                existing_membership = (
                    request.env["g2p.group.membership"]
                    .sudo()
                    .search([("individual", "=", member.id), ("group", "=", group_rec.id)])
                )

                # Update
                if existing_membership:
                    existing_membership.write(
                        {
                            "kind": relationship  # Update kind for existing membership
                        }
                    )

                member_list = []

                for membership in group_rec.group_membership_ids:
                    if membership.individual.is_farmer == "yes":
                        continue
                    else:
                        kind_name = membership.kind.name if membership.kind else None

                        member_list.append(
                            {
                                "id": membership.individual.id,
                                "name": membership.individual.name,
                                "age": str(
                                    membership.individual.age,
                                ),  # Ensure date is serialized
                                "gender": membership.individual.gender,
                                "kind": kind_name,
                                "active": membership.individual.active,
                                "group_id": membership.group.id,
                            }
                        )

                res["member_list"] = member_list

                return json.dumps(res)

        except Exception:
            # _logger.error("ERROR LOG IN INDIVIDUAL%s", e)
            return json.dumps({"error": "Failed to edit family member"})

    @http.route(
        "/serviceprovider/family_member/add/submit/",
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def add_family_member_submit(self, **kw):
        res = dict()
        try:
            group_id = kw.get("group_id")
            if not group_id:
                return json.dumps({"error": "Group ID is required"})

            group_rec = request.env["res.partner"].sudo().browse(int(group_id))
            if not group_rec.exists():
                return json.dumps({"error": "Group not found"})

            given_name = kw.get("given_name")
            family_name = kw.get("family_name")
            gf_name_eng = kw.get("gf_name_eng")
            relationship = int(kw.get("Relationship"))
            relationship = [(6, 0, [relationship])]

            name = f"{given_name} {family_name} {gf_name_eng}"

            user = request.env.user

            # Create the enumerator record associated with the current user
            enumerator = request.env["g2p.enumerator"].create(
                {
                    "name": user.name,
                    "enumerator_user_id": str(user.id),
                    "data_collection_date": date.today(),
                }
            )

            partner_data = {
                "name": name,
                "given_name": given_name,
                "family_name": family_name,
                "gf_name_eng": gf_name_eng,
                "birthdate": kw.get("birthdate"),
                "gender": kw.get("gender"),
                "is_registrant": True,
                "is_group": False,
                "is_farmer": "no",
                "enumerator_id": enumerator.id,
            }
            individual = request.env["res.partner"].sudo().create(partner_data)

            group_membership_vals = [
                (0, 0, {"individual": individual.id, "group": group_rec.id, "kind": relationship})
            ]

            group_rec.write({"group_membership_ids": group_membership_vals})

            member_list = []

            for membership in group_rec.group_membership_ids:
                if membership.individual.is_farmer == "yes":
                    continue
                else:
                    kind_name = membership.kind.name if membership.kind else None
                    member_list.append(
                        {
                            "id": membership.individual.id,
                            "name": membership.individual.name,
                            "age": membership.individual.age,
                            "gender": membership.individual.gender,
                            "active": membership.individual.active,
                            "group_id": membership.group.id,
                            "kind": kind_name,
                        }
                    )

            _logger.info("in coming herer tehe rquest")

            res["member_list"] = member_list
            return json.dumps(res)

        except Exception as e:
            _logger.error("ERROR LOG IN INDIVIDUAL%s", e)
            return json.dumps({"error": "Failed to add family member"})

    @http.route(
        "/serviceprovider/member/delete/",
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def delete_family_member(self, **kw):
        # res = dict()
        try:
            member_id = int(kw.get("member_id"))
            group_id = int(kw.get("group_id"))
            member = request.env["res.partner"].sudo().browse(member_id)
            group_rec = request.env["res.partner"].sudo().browse(group_id)

            if not member.exists():
                return json.dumps({"error": "Member not found"})

            if not group_rec.exists():
                return json.dumps({"error": "Group not found"})

            if member.hh_is_household_head != "yes":
                group_membership = (
                    request.env["g2p.group.membership"]
                    .sudo()
                    .search([("group", "=", group_id), ("individual", "=", member_id)])
                )

                if group_membership:
                    group_membership.unlink()

                if member.is_farmer != "yes":
                    member.unlink()
                    return json.dumps(
                        {"success": True, "message": "Family member removed and successfully deleted."}
                    )
                else:
                    return json.dumps(
                        {
                            "success": True,
                            "message": "Farmer family member removed from household, but record will remain as individual",
                        }
                    )

            else:
                return json.dumps({"error": "Household head can't be removed."})

        except Exception as e:
            _logger.error("ERROR LOG IN DELETE FAMILY MEMBER: %s", e)
            return json.dumps({"error": f"An error occurred while deleting the member: {str(e)}"})

    def get_membership_kind(self, relationship):
        if relationship == "Wife":
            relationship = "Wife - Head"
        if relationship == "Husband":
            relationship = "Husband - Head"

        membership_kind = (
            request.env["g2p.group.membership.kind"].sudo().search([("name", "=", relationship)], limit=1)
        )
        return membership_kind.id

    def process_land(self, kw, vals):
        land_records = json.loads(kw.get("landRecords", "[]"))

        land_info_data = []
        supporting_documents_ids = []
        backend_id = (
            request.env.ref("storage_backend.default_storage_backend").id
            or request.env["storage.backend"].sudo().search([], limit=1).id
        )

        doc_tag = request.env["g2p.document.tag"].sudo().get_or_create_tag_from_name("Land Certificate")
        if not doc_tag:
            doc_tag = request.env["g2p.document.tag"].sudo().create({"name": "Land Certificate"})
        for record in land_records:
            # Skip the record if any of its keys contain "{9999}"
            if any("{9999}" in key for key in record.keys()):
                continue

            # Extract the index from the first key (you can choose any key that contains the index)
            for key in record.keys():
                if "ownership_type_" in key:
                    index = key.split("_")[-1]

                    ownership_type = record.get(f"ownership_type_{index}", "").strip()
                    if not ownership_type:
                        continue

                    land_id = record.get(f"land_id_{index}")
                    land_area = record.get(f"total_land_area_{index}")

                    # Fetch land ownership type value
                    land_ownership_type = (
                        request.env["ir.model.fields.selection"]
                        .sudo()
                        .search([("id", "=", ownership_type)])
                        .value
                    )

                    land_info_dict = {
                        "ownership_type": land_ownership_type,
                        "total_land_area": land_area,
                        "land_id": land_id,
                    }

                    # Process land certificate if it exists and is not empty
                    land_certificate = record.get(f"land_certificate_{index}")
                    if land_certificate:
                        content = land_certificate.get("content")
                        binary_data = bytes(content, "latin1")
                        storage_file = (
                            request.env["storage.file"]
                            .sudo()
                            .create(
                                {
                                    "backend_id": backend_id,
                                    "name": land_certificate.get("filename"),
                                    "data": binary_data,
                                    "tags_ids": [(4, doc_tag.id)],
                                }
                            )
                        )
                        land_info_dict["land_certificate"] = storage_file.id
                        supporting_documents_ids.append((4, storage_file.id))
                    land_info_data.append((0, 0, land_info_dict))
                break  # Exit the loop since the index is identified for this record
        # return
        vals["land_information_ids"] = land_info_data
        vals["supporting_documents_ids"] = supporting_documents_ids
        return vals

    @http.route(
        ["/serviceprovider/individual/create/"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def individual_create(self, **kw):
        res = dict()
        try:
            region = self._convert_to_int(kw.get("region"))
            zone = self._convert_to_int(kw.get("zone"))
            woreda = self._convert_to_int(kw.get("woreda"))
            kebele = self._convert_to_int(kw.get("kebele"))

            additional_info = kw.get("additional_info", {})
            # try:
            #     additional_info_json = json.loads(additional_info)
            # except json.JSONDecodeError as e:
            #     additional_info_json = {}

            user = request.env.user

            # Create the enumerator record associated with the current user
            enumerator = request.env["g2p.enumerator"].create(
                {
                    "name": user.name,
                    "enumerator_user_id": str(user.id),
                    "data_collection_date": date.today(),
                }
            )

            group_rec = self._get_or_create_group(kw, region, zone, woreda, kebele, enumerator)

            vals = self._prepare_individual_vals(kw, region, zone, woreda, kebele)

            vals = self.process_land(kw, vals)

            vals["crop_information_ids"] = self._prepare_crop_information(kw.get("cropRecords"))
            vals["livestock_information_ids"] = self._livestock_information(kw.get("livestockRecord"))
            vals["phone_number_ids"] = self._prepare_phone_numbers(kw, region, zone, woreda, kebele, vals)
            # Socioeconomic data
            self._prepare_socioeconomic_data(kw, vals)

            # Membership details
            self._prepare_membership_details(kw, vals)

            # Financial Service
            self._prepare_financial_agricultural_service(kw, vals)
            # Additional details
            vals["is_farmer"] = "yes"
            vals["additional_g2p_info"] = additional_info
            vals["enumerator_id"] = enumerator.id

            individual = request.env["res.partner"].sudo().create(vals)

            # self._manage_group_membership(group_rec, individual)
            group_membership_vals = [(0, 0, {"individual": individual.id, "group": group_rec.id})]

            # Add head_individual membership if created

            group_rec.write({"group_membership_ids": group_membership_vals})

            member_list = []
            for membership in group_rec.group_membership_ids:
                if membership.individual.is_farmer == "yes":
                    member_list.append(
                        {
                            "id": membership.individual.id,
                            "name": membership.individual.name,
                            "age": membership.individual.age,
                            "gender": membership.individual.gender,
                            "hh_is_household_head": membership.individual.hh_is_household_head,
                            "group_id": membership.group.id,
                        }
                    )

            res["member_list"] = member_list

            return json.dumps(res)

        except Exception as e:
            _logger.error(e)

    def _convert_to_int(self, value):
        return int(value.strip()) if value and value.strip() else None

    def _get_or_create_group(self, kw, region, zone, woreda, kebele, enumerator):
        given_name = kw.get("given_name")
        father_name = kw.get("family_name")
        family_name = kw.get("gf_name_eng")
        head_name = " ".join(filter(None, [given_name, father_name, family_name]))
        if kw.get("group_id"):
            return request.env["res.partner"].sudo().browse(int(kw.get("group_id")))
        elif head_name:
            group_type = request.env["g2p.group.kind"].sudo().search([("name", "=", "Household")], limit=1)
            return (
                request.env["res.partner"]
                .sudo()
                .create(
                    {
                        "name": head_name,
                        "region": region,
                        "zone": zone,
                        "woreda": woreda,
                        "kebele": kebele,
                        "kind": group_type.id,
                        "is_registrant": True,
                        "is_group": True,
                        "enumerator_id": enumerator.id,
                    }
                )
            )
        return None

    def _prepare_individual_vals(self, kw, region, zone, woreda, kebele):
        vals = {
            "is_registrant": True,
            "is_group": False,
            "region": region,
            "zone": zone,
            "woreda": woreda,
            "kebele": kebele,
        }
        name_parts = []
        for field in ["given_name", "family_name", "gf_name_eng"]:
            if kw.get(field):
                vals[field] = kw.get(field)
                name_parts.append(kw.get(field))

        vals["name"] = " ".join(name_parts).strip()

        other_fields = {
            "first_name_amh": "firstNameAmh",
            "family_name_amh": "familyNameAmh",
            "gf_name_amh": "gFNameAmh",
            "first_name_other": "firstNameOther",
            "family_name_other": "familyNameOther",
            "gf_name_other": "lastNameOther",
            "birthdate": "dob",
            "gender": "gender",
        }
        for key, field in other_fields.items():
            if kw.get(field):
                vals[key] = kw.get(field)
        # National ID and Registration
        self._prepare_national_id(kw, vals)

        # Handle individual details
        self._process_individual_details(vals, kw)
        # Handle socio-economic data
        self._process_socio_economic_data(vals, kw)

        # Handle membership details
        self._process_membership_details(vals, kw)

        return vals

    def _prepare_crop_information(self, crop_records):
        crop_records = json.loads(crop_records or "[]")
        crop_info_data = []
        for record in crop_records:
            if any("{9999}" in key for key in record.keys()):
                continue
            for key in record.keys():
                if "crops_" in key:
                    crop_id = record.get(f"crops_{key.split('_')[-1]}", "").strip()
                    planted_date = record.get(f"crop_planted_date_{key.split('_')[-1]}", "").strip()
                    if crop_id:
                        crop_info_data.append((0, 0, {"crop": int(crop_id), "collected_gc": planted_date}))
                        break
        return crop_info_data

    def _livestock_information(self, livestock_records):
        livestock_records = json.loads(livestock_records or "[]")
        livestock_info_data = []
        for record in livestock_records:
            if any("{9999}" in key for key in record.keys()):
                continue
            for key in record.keys():
                if "livestock_types_" in key:
                    livestock_type = record.get(f"livestock_types_{key.split('_')[-1]}").strip()
                    if livestock_type:
                        livestock_info_data.append(
                            (
                                0,
                                0,
                                {
                                    "livestock_type": int(livestock_type),
                                    "number_of_livestock": record.get(
                                        f"number_of_livestock_{key.split('_')[-1]}"
                                    ),
                                },
                            )
                        )
                        break
        return livestock_info_data

    def _prepare_phone_numbers(self, kw, region, zone, woreda, kebele, vals):
        has_personal_phone = self._get_selection_value("ir.model.fields.selection", kw.get("havePhoneNumber"))
        vals["has_personal_phone"] = has_personal_phone
        ethiopia_country_id = (
            request.env["res.country"].sudo().search([("name", "=", "Ethiopia")], limit=1).id
        )
        phone_no = []
        if has_personal_phone == "yes":
            phone_no.append(
                (
                    0,
                    0,
                    {
                        "phone_no": kw.get("primaryPhoneNumber"),
                        "phone_type": "primary",
                        "country_id": ethiopia_country_id,
                    },
                )
            )
            if kw.get("secondaryPhoneNumber") and kw.get("secondaryPhoneNumber").strip():
                phone_no.append(
                    (
                        0,
                        0,
                        {
                            "phone_no": kw.get("secondaryPhoneNumber"),
                            "phone_type": "secondary",
                            "country_id": ethiopia_country_id,
                        },
                    )
                )
        elif has_personal_phone == "no":
            phone_no.append(
                (
                    0,
                    0,
                    {
                        "phone_no": kw.get("otherPhoneNumber"),
                        "phone_type": "other",
                        "country_id": ethiopia_country_id,
                    },
                )
            )
            if kw.get("secondaryPhoneNumber") and kw.get("secondaryPhoneNumber").strip():
                phone_no.append(
                    (
                        0,
                        0,
                        {
                            "phone_no": kw.get("secondaryPhoneNumber"),
                            "phone_type": "secondary",
                            "country_id": ethiopia_country_id,
                        },
                    )
                )
        return phone_no

    def _prepare_national_id(self, kw, vals):
        has_national_id = self._get_selection_value("ir.model.fields.selection", kw.get("hasNationalId"))
        vals["has_national_id"] = has_national_id

        selected_id = kw.get("selectedId")
        selected_id = selected_id.replace(" ", "")
        if has_national_id == "yes":
            id_type = request.env["g2p.id.type"].sudo().search([("name", "=", "UID")], limit=1)
            vals["reg_ids"] = [(0, 0, {"id_type": id_type.id, "value": selected_id, "status": "valid"})]

        elif has_national_id == "no":
            id_type = request.env["g2p.id.type"].sudo().search([("name", "=", "RID")], limit=1)
            vals["reg_ids"] = [(0, 0, {"id_type": id_type.id, "value": selected_id, "status": "valid"})]

    def _prepare_socioeconomic_data(self, kw, vals):
        fields = {
            "martial_status": "maritalStatus",
            "education": "educationLevel",
        }
        for key, field in fields.items():
            if kw.get(field):
                vals[key] = self._get_selection_value("ir.model.fields.selection", kw.get(field))

        income_type = json.loads(kw.get("newIncomeType", "[]"))
        if income_type:
            vals["hh_income_type"] = [(6, 0, [int(id) for id in income_type])]

        crop_water_source = json.loads(kw.get("cropWaterSource", "[]"))
        if crop_water_source:
            vals["crop_water_sources"] = [(6, 0, [int(id) for id in crop_water_source])]

        livestock_water_source = json.loads(kw.get("livestockWaterSource", "[]"))
        if livestock_water_source:
            vals["livestock_water_sources"] = [(6, 0, [int(id) for id in livestock_water_source])]

    def _prepare_membership_details(self, kw, vals):
        is_member_of_primary_cooperative = self._get_selection_value(
            "ir.model.fields.selection", kw.get("isMemberOfPrimaryCoop")
        )
        vals["is_member_of_primary_cooperative"] = is_member_of_primary_cooperative
        if is_member_of_primary_cooperative == "yes" and kw.get("nameOfPrimaryCoop").strip():
            vals["primary_cooperatives"] = int(kw.get("nameOfPrimaryCoop"))

        is_member_of_cooperative_union = self._get_selection_value(
            "ir.model.fields.selection", kw.get("isMemberOfCoopUnion")
        )
        vals["is_member_of_cooperative_union"] = is_member_of_cooperative_union
        if is_member_of_cooperative_union == "yes" and kw.get("nameOfCoopUnion").strip():
            vals["cooperative_unions"] = int(kw.get("nameOfCoopUnion"))

        is_member_in_farmer_cluster = self._get_selection_value(
            "ir.model.fields.selection", kw.get("inFarmerCluster")
        )
        vals["is_member_in_farmer_cluster"] = is_member_in_farmer_cluster
        if is_member_in_farmer_cluster == "yes":
            if kw.get("primaryComodity").strip():
                vals["primary_commodity"] = int(kw.get("primaryComodity"))
            if kw.get("roleInCluster").strip():
                vals["role_in_farmer_cluster"] = self._get_selection_value(
                    "ir.model.fields.selection", kw.get("roleInCluster")
                )

    def _prepare_financial_agricultural_service(self, kw, vals):
        can_access_financial_service = self._get_selection_value(
            "ir.model.fields.selection", kw.get("accessToFinance")
        )
        vals["has_finance_access"] = can_access_financial_service
        if can_access_financial_service == "yes":
            vals["finance_accesses"] = [
                (6, 0, [int(id) for id in json.loads(kw.get("financialSectors", "[]"))])
            ]

        if vals.get("farming_type") != "livestock_farming":
            if kw.get("usedFertilizer"):
                vals["do_you_use_fertilizer"] = self._get_selection_value(
                    "ir.model.fields.selection", kw.get("usedFertilizer")
                )

            if kw.get("usedInsecticide"):
                vals["do_you_use_insecticide"] = self._get_selection_value(
                    "ir.model.fields.selection", kw.get("usedInsecticide")
                )

            if kw.get("usedPesticide"):
                vals["do_you_use_pesticide"] = self._get_selection_value(
                    "ir.model.fields.selection", kw.get("usedPesticide")
                )

            if kw.get("usedImprovedSeed"):
                vals["do_you_use_improved_seed"] = self._get_selection_value(
                    "ir.model.fields.selection", kw.get("usedImprovedSeed")
                )

        can_access_machinery = self._get_selection_value(
            "ir.model.fields.selection", kw.get("accessToMachinary")
        )
        vals["access_to_machinery"] = can_access_machinery
        if can_access_machinery == "yes":
            vals["type_of_machinery"] = [
                (6, 0, [int(id) for id in json.loads(kw.get("matchinaryTypes", "[]"))])
            ]

    def _manage_group_membership(self, group_rec, individual):
        if group_rec:
            group_rec.write({"individual_id": [(4, individual.id)]})
            individual.write({"group_id": group_rec.id})

    def _get_member_list(self, group_rec):
        members = []
        if group_rec:
            for member in group_rec.individual_id:
                members.append({"name": member.name, "id": member.id})
        return members

    def _get_selection_value(self, model, field_value):
        if field_value and len(field_value) > 0:
            selection = request.env[model].sudo().search([("id", "=", field_value)]).value
            return selection
        else:
            return False

    @http.route(
        ["/serviceprovider/member/create/"],
        type="http",
        auth="user",
        website=True,
        csrf=False,
    )
    def member_create(self, **kw):
        res = dict()
        try:
            # head_name = kw.get("household_name")
            head_individual = None
            # Group creation
            if kw.get("group_id"):
                group_rec = request.env["res.partner"].sudo().browse(int(kw.get("group_id")))

            given_name = kw.get("given_name")
            family_name = kw.get("family_name")
            gf_name_eng = kw.get("addl_name")

            name = f"{given_name}, {gf_name_eng} {family_name}"

            partner_data = {
                "name": name,
                "given_name": given_name,
                "family_name": family_name,
                "gf_name_eng": gf_name_eng,
                "birthdate": kw.get("birthdate"),
                "gender": kw.get("gender"),
                "is_registrant": True,
                "is_group": False,
                "is_farmer": "no",
            }

            individual = request.env["res.partner"].sudo().create(partner_data)

            def get_membership_kind(relationship):
                if relationship == "Wife":
                    relationship = "Wife - Head"
                if relationship == "Husband":
                    relationship = "Husband - Head"

                membership_kind = (
                    request.env["g2p.group.membership.kind"]
                    .sudo()
                    .search([("name", "=", relationship)], limit=1)
                )
                if not membership_kind:
                    membership_kind = (
                        request.env["g2p.group.membership.kind"].sudo().create({"name": relationship})
                    )
                return membership_kind.id

            if kw.get("relationship").strip():
                membership_kind = get_membership_kind(kw.get("relationship"))

            # Member creation only if head_individual is created
            group_membership_vals = [
                (0, 0, {"individual": individual.id, "group": group_rec.id, "kind": [(4, membership_kind)]})
            ]

            # Add head_individual membership if created
            if head_individual:
                group_membership_vals.insert(
                    0, (0, 0, {"individual": head_individual.id, "group": group_rec.id})
                )

            group_rec.write({"group_membership_ids": group_membership_vals})

            member_list = []
            for membership in group_rec.group_membership_ids:
                if membership.individual.is_farmer == "no":
                    member_list.append(
                        {
                            "id": membership.individual.id,
                            "name": membership.individual.name,
                            "age": membership.individual.age,
                            "gender": membership.individual.gender,
                            "active": membership.individual.active,
                            "group_id": membership.group.id,
                        }
                    )

            res["member_list"] = member_list
            return json.dumps(res)

        except Exception as e:
            _logger.error("ERROR LOG IN INDIVIDUAL%s", e)
