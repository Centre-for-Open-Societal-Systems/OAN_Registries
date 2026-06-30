import base64
import json
from datetime import date

import logging

import jq

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OdkImportInherit(models.Model):
    _inherit = "odk.import"

    def _get_odk_import_source_id(self):
        odk_source = self.env.ref("g2p_ati.import_source_odk", raise_if_not_found=False)
        return odk_source.id if odk_source else False

    def _set_odk_import_source(self, vals):
        odk_source_id = self._get_odk_import_source_id()
        if odk_source_id:
            vals["rec_import_source"] = odk_source_id
        return vals

    def _get_odk_submission_instance_id(self, mapped_json=None, member=None):
        for values in (mapped_json or {}, member or {}):
            if not isinstance(values, dict):
                continue

            for key in ("odk_instance_id", "instance_id", "__id"):
                if values.get(key):
                    return str(values.get(key))

            meta = values.get("meta") or {}
            if isinstance(meta, dict):
                for key in ("instanceID", "instanceId", "__id"):
                    if meta.get(key):
                        return str(meta.get(key))

            system = values.get("__system") or {}
            if isinstance(system, dict):
                for key in ("instanceID", "instanceId", "__id"):
                    if system.get(key):
                        return str(system.get(key))

        return False

    def _set_odk_instance_id(self, vals, instance_id):
        if instance_id:
            vals["odk_instance_id"] = str(instance_id)
        return vals

    def _is_odk_instance_imported(self, instance_id):
        if not instance_id:
            return False
        return bool(
            self.env["res.partner"]
            .sudo()
            .with_context(active_test=False)
            .search_count([("odk_instance_id", "=", str(instance_id))])
        )

    def _is_odk_instance_queued(self, instance_id):
        if not instance_id:
            return False
        return bool(
            self.env["odk.instance.id"]
            .sudo()
            .search_count(
                [
                    ("instance_id", "=", str(instance_id)),
                    ("status", "in", ["pending", "processing", "done"]),
                ]
            )
        )

    def import_records(self):
        self.ensure_one()
        sync_started_at = fields.Datetime.now()

        if self.enable_async:
            instance_ids = self.odk_config.get_submissions(
                fields="__id",
                last_sync_time=self.last_sync_time,
            )
            for instance in instance_ids:
                if isinstance(instance, dict):
                    extracted_instance_id = instance.get("__id")

                    if extracted_instance_id:
                        if self._is_odk_instance_imported(
                            extracted_instance_id
                        ) or self._is_odk_instance_queued(extracted_instance_id):
                            continue
                        self.env["odk.instance.id"].create(
                            {
                                "instance_id": extracted_instance_id,
                                "odk_import_id": self.id,
                                "status": "pending",
                            }
                        )
                    else:
                        _logger.error("Missing '__id' in submission: %s", instance)

            self.last_sync_time = sync_started_at
            return self.process_pending_instances()

        imported = self.process_records(last_sync_time=self.last_sync_time)
        if "form_updated" in imported:
            partner_count = imported.get("partner_count", 0)
            message = f"ODK form {partner_count} records were imported successfully."
            types = "success"
            self.last_sync_time = sync_started_at
        elif "form_failed" in imported:
            message = "ODK form import failed"
            types = "danger"
        else:
            message = "No new form records were submitted."
            types = "warning"
            self.last_sync_time = sync_started_at

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": types,
                "message": message,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _process_pending_instance_id(self, instance_ids):
        for instance in instance_ids:
            _logger.info("Processing instance ID: %s", instance.instance_id)
            instance.status = "processing"
            try:
                instance.odk_import_id.process_records(instance_id=instance.instance_id)
                instance.status = "done"
            except Exception as exc:
                _logger.exception(
                    "Failed to import instance ID %s: %s",
                    instance.instance_id,
                    exc,
                )
                instance.status = "failed"

    def process_records(self, instance_id=None, last_sync_time=None):
        self.ensure_one()

        if not self.odk_config:
            raise ValidationError(_("Please configure the ODK."))

        data = self.odk_config.download_records(instance_id=instance_id, last_sync_time=last_sync_time)

        partner_count = 0
        skipped_count = 0
        for member in data["value"]:
            _logger.debug("ODK RAW DATA:%s", member)

            mapped_json = jq.first(self.json_formatter, member)
            if not isinstance(mapped_json, dict):
                raise ValidationError(_("The ODK jq formatter must return a JSON object."))

            odk_instance_id = self._get_odk_submission_instance_id(mapped_json, member)
            if self._is_odk_instance_imported(odk_instance_id):
                skipped_count += 1
                _logger.info("Skipping duplicate ODK submission with instance ID: %s", odk_instance_id)
                continue

            self._set_odk_instance_id(mapped_json, odk_instance_id)

            if self.target_registry == "individual":
                mapped_json.update({"is_registrant": True, "is_group": False})
            elif self.target_registry == "group":
                mapped_json.update({"is_registrant": True, "is_group": True})

            self.process_records_handle_one2many_fields(mapped_json)
            self.process_records_handle_media_import(mapped_json, member)
            self._set_odk_instance_id(
                mapped_json,
                mapped_json.get("odk_instance_id") or mapped_json.get("instance_id"),
            )
            self.process_records_handle_many2one_fields(mapped_json)

            self.process_records_handle_addl_data(mapped_json)

            self._set_odk_import_source(mapped_json)
            self._set_odk_instance_id(
                mapped_json,
                mapped_json.get("odk_instance_id") or mapped_json.get("instance_id"),
            )
            self.env["res.partner"].sudo().create(mapped_json)
            partner_count += 1
            data.update({"form_updated": True})

        data.update({"partner_count": partner_count, "skipped_count": skipped_count})

        return data

    def get_value_ids(self, model, value_list):
        ids = []
        for value in value_list:
            if value == "other":
                ids.append(value)
            record = self.env[model].search([("code", "=", value)], limit=1)
            if record:
                ids.append(record.id)

        return ids

    def get_value_many2one(self, model, value):
        id_val = False
        if value:
            record = self.env[model].search([("code", "=", value)], limit=1)
            if record:
                id_val = record.id
        return id_val

    def process_many2one_field(self, model_name, field_value):
        if field_value == "other":
            return field_value
        field_id = self.get_value_many2one(model_name, field_value)
        return field_id if field_id else None

    def process_many2many_field(self, model_name, field_value):
        if field_value is not None:
            field_list = field_value.split(" ")
        else:
            field_list = []
        field_ids = self.get_value_ids(model_name, field_list)
        return field_ids

    def process_phone_ids(self, json_data):
        # Fetch the country ID for Ethiopia
        ethiopia_country_id = self.env["res.country"].search([("name", "=", "Ethiopia")], limit=1).id
        json_data["phone_number_ids"] = [
            (
                0,
                0,
                {
                    "phone_no": "+" + phone.get("phone_no"),
                    "phone_type": phone.get("phone_type"),
                    "country_id": ethiopia_country_id,
                },
            )
            for phone in json_data["phone_ids"]
        ]
        return json_data

    def process_land_ids(self, json_data, is_member, other_json):
        land_information_ids = []
        supporting_documents_ids = []
        if json_data["land_information_ids"] is not None:
            for land_info in json_data["land_information_ids"]:
                ownership_type = land_info.get(
                    "hh_member_land_ownership" if is_member else "land_ownership", None
                )
                if not ownership_type:
                    continue

                land_info_dict = {
                    "ownership_type": ownership_type,
                    "total_land_area": land_info.get(
                        "hh_member_total_land_area" if is_member else "total_land_area", 0
                    ),
                    "land_id": land_info.get("hh_member_land_id" if is_member else "land_id", 0),
                }

                # Add land_kebele from within land_info data
                land_kebele = land_info.get("hh_member_land_kebele" if is_member else "land_kebele")
                if land_kebele:
                    kebele_id = self.process_many2one_field("g2p.kebele", land_kebele)
                    if kebele_id:
                        if kebele_id == "other":
                            # Store other land kebele value
                            other_field = "hh_member_other_land_kebele" if is_member else "other_land_kebele"
                            other_land_kebele = land_info.get(other_field)
                            if other_land_kebele:
                                other_json["Land Kebele"] = other_land_kebele
                        else:
                            land_info_dict["land_kebele"] = kebele_id

                land_certificate = land_info.get(
                    "hh_member_land_certificate" if is_member else "land_certificate", None
                )
                land_certificate_id = None
                if land_certificate:
                    supporting_document_id, land_certificate_id = self.process_land_certificate(
                        land_certificate, json_data.get("instance_id")
                    )
                    if land_certificate_id:
                        supporting_documents_ids.append(supporting_document_id)
                        land_info_dict["land_certificate"] = land_certificate_id
                land_information_ids.append((0, 0, land_info_dict))
        return [land_information_ids, supporting_documents_ids]

    def process_crop_ids(self, json_data, is_member):
        unique_crops = {}
        if json_data["crop_information_ids"] is not None:
            for crop_info in json_data["crop_information_ids"]:
                crop = crop_info.get("hh_member_crop_name" if is_member else "crop_name", None)
                if not crop:
                    continue
                crop_id = self.get_value_many2one(
                    "g2p.crop", crop_info.get("hh_member_crop_name" if is_member else "crop_name", None)
                )
                crop_date = crop_info.get("hh_member_crop_date" if is_member else "crop_date", None)
                if crop_id:
                    if crop_id in unique_crops:
                        unique_crops[crop_id]["collected_gc"] = crop_date
                    else:
                        unique_crops[crop_id] = {"crop": crop_id, "collected_gc": crop_date}

        # Convert the dictionary values back to a list of tuples
        crop_information_ids = [(0, 0, info) for info in unique_crops.values()]

        return crop_information_ids

    def process_livestock_ids(self, json_data, is_member):
        unique_livestock = {}
        if json_data["livestock_information_ids"] is not None:
            for livestock_info in json_data["livestock_information_ids"]:
                live_type = livestock_info.get("hh_member_animal" if is_member else "animal", None)
                if not live_type:
                    continue
                livestock_type = self.get_value_many2one("g2p.livestock.type", live_type)
                no_of_livestock = livestock_info.get(
                    "hh_member_num_animals" if is_member else "num_animals", 0
                )
                if no_of_livestock is None:
                    no_of_livestock = 0
                if livestock_type:
                    # Store or update the livestock information in the dictionary
                    if livestock_type in unique_livestock:
                        unique_livestock[livestock_type]["number_of_livestock"] += no_of_livestock
                    else:
                        unique_livestock[livestock_type] = {
                            "livestock_type": livestock_type,
                            "number_of_livestock": no_of_livestock,
                        }

        # Convert the dictionary values back to a list of tuples
        livestock_information_ids = [(0, 0, info) for info in unique_livestock.values()]

        return livestock_information_ids

    def process_reg_ids(self, json_data, id_type_name, id_value_key):
        id_type = self.env["g2p.id.type"].sudo().search([("name", "=", id_type_name)], limit=1)

        if "reg_ids" in json_data:
            json_data["reg_ids"].append(
                (
                    0,
                    0,
                    {"id_type": id_type.id, "value": json_data[id_value_key], "status": "valid"},
                )
            )
        else:
            json_data["reg_ids"] = [
                (
                    0,
                    0,
                    {"id_type": id_type.id, "value": json_data[id_value_key], "status": "valid"},
                )
            ]
        return json_data

    def process_basic_information(self, individual, vals, other_json):
        hh_head = individual.get("hh_is_household_head")
        if hh_head and hh_head.strip():
            vals["hh_is_household_head"] = hh_head

        # NATIONAL ID
        vals["has_national_id"] = individual.get("has_national_id")
        if individual.get("has_national_id") == "yes":
            individual = self.process_reg_ids(individual, "UID", "uid")

        elif individual.get("has_national_id") == "no":
            individual = self.process_reg_ids(individual, "RID", "rid")
        vals["reg_ids"] = individual.get("reg_ids")

        # BASIC INFORMATION

        region_id = self.process_many2one_field("g2p.region", individual.get("region"))
        if region_id:
            if region_id == "other":
                other_json["Region"] = individual.get("other_region")
            else:
                vals["region"] = region_id

        zone_id = self.process_many2one_field("g2p.zone", individual.get("zone"))
        if zone_id:
            if zone_id == "other":
                other_json["Zone"] = individual.get("other_zone")
            else:
                vals["zone"] = zone_id

        woreda_id = self.process_many2one_field("g2p.woreda", individual.get("woreda"))
        if woreda_id:
            if woreda_id == "other":
                other_json["Woreda"] = individual.get("other_woreda")
            else:
                vals["woreda"] = woreda_id

        kebele_id = self.process_many2one_field("g2p.kebele", individual.get("kebele"))
        if kebele_id:
            if kebele_id == "other":
                other_json["Kebele"] = individual.get("other_kebele")
            else:
                vals["kebele"] = kebele_id

        language_id = self.process_many2one_field("g2p.lang", individual.get("primary_Language"))
        if language_id:
            if language_id == "other":
                other_json["Primary Language"] = individual.get("primary_Language")
            else:
                vals["primary_Language"] = language_id

        vals["given_name"] = individual.get("given_name")
        vals["family_name"] = individual.get("family_name")
        vals["gf_name_eng"] = individual.get("gf_name_eng")
        vals["name"] = individual.get("name")
        vals["first_name_amh"] = individual.get("first_name_amh")
        vals["family_name_amh"] = individual.get("family_name_amh")
        vals["gf_name_amh"] = individual.get("gf_name_amh")
        vals["first_name_other"] = individual.get("first_name_other")

        vals["family_name_other"] = individual.get("family_name_other")
        vals["gf_name_other"] = individual.get("gf_name_other")
        vals["gender"] = individual.get("gender")

        birthdate = individual.get("birthdate")

        if birthdate:
            vals["birthdate"] = birthdate

        if not birthdate:
            age = individual.get("age")

            if age:
                today = date.today()
                year = today.year - int(age)
                estimated_birthdate = date(year, 9, 1)
                vals["birthdate"] = estimated_birthdate.strftime("%Y-%m-%d")

        vals["has_personal_phone"] = individual.get("has_personal_phone")
        if "phone_ids" in individual:
            individual = self.process_phone_ids(individual)
            vals["phone_number_ids"] = individual.get("phone_number_ids")

        vals["email"] = individual.get("email")
        vals["is_disabled"] = individual.get("is_disabled")
        vals["farming_type"] = individual.get("farming_type")

        vals["martial_status"] = individual.get("martial_status")
        vals["is_psnp_user"] = individual.get("is_psnp_user")
      

        vals["education"] = individual.get("education")

        vals["size_of_family"] = individual.get("size_of_family")
        vals["number_of_children_in_family"] = individual.get("number_of_children_in_family")
        vals["number_of_males_in_family"] = individual.get("number_of_males_in_family")
        vals["number_of_females_in_family"] = individual.get("number_of_females_in_family")

        source_of_income_ids = self.process_many2many_field("g2p.hh.income", individual.get("hh_income_type"))
        if source_of_income_ids:
            if "other" in source_of_income_ids:
                other_json["House Hold Income"] = individual.get("other_income_type")
                source_of_income_ids.remove("other")
            vals["hh_income_type"] = [(6, 0, source_of_income_ids)]



    def process_membership(self, individual, vals, other_json):
        # MEMBERSHIP
        vals["is_member_of_primary_cooperative"] = individual.get("is_member_of_primary_cooperative")
        vals["is_member_of_cooperative_union"] = individual.get("is_member_of_cooperative_union")
        primary_cooperative_id = self.process_many2one_field(
            "g2p.primary.cooperative", individual.get("primary_cooperatives")
        )
        if primary_cooperative_id:
            if primary_cooperative_id == "other":
                other_json["Primary Cooperative"] = individual.get("other_primary_cooperative")
            else:
                vals["primary_cooperatives"] = primary_cooperative_id

        cooperative_union_id = self.process_many2one_field(
            "g2p.cooperative.union", individual.get("cooperative_unions")
        )
        if cooperative_union_id:
            if cooperative_union_id == "other":
                other_json["Cooperative Union"] = individual.get("other_coop_union")
            else:
                vals["cooperative_unions"] = cooperative_union_id

        vals["is_member_in_farmer_cluster"] = individual.get("is_member_in_farmer_cluster")
        primary_commodity_id = self.process_many2one_field(
            "g2p.primary.commodity", individual.get("primary_commodity")
        )
        if primary_commodity_id:
            vals["primary_commodity"] = primary_commodity_id

        vals["role_in_farmer_cluster"] = individual.get("role_in_farmer_cluster")

    def process_land_crop_livestock_information(self, individual, vals, is_member, other_json):
        # LAND INFORMATION
        if "land_information_ids" in individual:
            vals["land_information_ids"], vals["supporting_documents_ids"] = self.process_land_ids(
                individual, is_member, other_json
            )

        # CROP INFORMATION
        if "crop_information_ids" in individual:
            vals["crop_information_ids"] = self.process_crop_ids(individual, is_member)
        crop_water_sources_ids = self.process_many2many_field(
            "g2p.water.source", individual.get("crop_water_sources")
        )
        if crop_water_sources_ids:
            if "other" in crop_water_sources_ids:
                crop_water_sources_ids.remove("other")
            vals["crop_water_sources"] = [(6, 0, crop_water_sources_ids)]

        # LIVESTOCK INFORMATION
        if "livestock_information_ids" in individual:
            vals["livestock_information_ids"] = self.process_livestock_ids(individual, is_member)
        livestock_water_sources_ids = self.process_many2many_field(
            "g2p.water.source", individual.get("livestock_water_sources")
        )
        if livestock_water_sources_ids:
            if "other" in livestock_water_sources_ids:
                livestock_water_sources_ids.remove("other")
            vals["livestock_water_sources"] = [(6, 0, livestock_water_sources_ids)]

    def process_agriculture_resource_finance(self, individual, vals):
        # AGRICULTURAL INPUT
        vals["do_you_use_fertilizer"] = individual.get("do_you_use_fertilizer")
        vals["do_you_use_pesticide"] = individual.get("do_you_use_pesticide")
        vals["do_you_use_insecticide"] = individual.get("do_you_use_insecticide")
        vals["do_you_use_improved_seed"] = individual.get("do_you_use_improved_seed")

        # ACCESS TO RESOURCE
        vals["access_to_machinery"] = individual.get("access_to_machinery")
        if individual.get("access_to_machinery") == "yes":
            type_of_machinery_ids = self.process_many2many_field(
                "g2p.machinery", individual.get("type_of_machinery")
            )
            if type_of_machinery_ids:
                if "other" in type_of_machinery_ids:
                    type_of_machinery_ids.remove("other")
                vals["type_of_machinery"] = [(6, 0, type_of_machinery_ids)]

        # ACCESS TO FINANCE
        vals["has_finance_access"] = individual.get("has_finance_access")
        if individual.get("has_finance_access") == "yes":
            finance_accesses_ids = self.process_many2many_field(
                "g2p.finance.access", individual.get("finance_accesses")
            )
            if finance_accesses_ids:
                if "other" in finance_accesses_ids:
                    finance_accesses_ids.remove("other")
                vals["finance_accesses"] = [(6, 0, finance_accesses_ids)]

    def create_enumerator(self, enumerator_name, enumerator_odk_id, data_collection_date):
        enumerator = (
            self.env["g2p.enumerator"]
            .sudo()
            .create(
                {
                    "name": enumerator_name,
                    "enumerator_user_id": enumerator_odk_id,
                    "data_collection_date": data_collection_date,
                }
            )
        )
        return enumerator

    def remove_non_partner_fields_in_place(self, data_dict):
        """Remove fields from data_dict that don't exist in res.partner model (in place)"""
        partner_fields = self.env["res.partner"]._fields.keys()

        special_fields = [
            "is_registrant",
            "is_group",
            "reg_ids",
            "group_membership_ids",
            "individual_membership_ids",
            "supporting_documents_ids",
            "phone_number_ids",
            "kind",
            "enumerator_id",
            "land_information_ids",
            "crop_information_ids",
            "livestock_information_ids",
            "crop_water_sources",
            "livestock_water_sources",
            "finance_accesses",
            "type_of_machinery",
        ]

        # Identify and remove fields that don't exist in res.partner
        fields_to_remove = []
        for field in list(data_dict.keys()):
            if field not in partner_fields and field not in special_fields:
                fields_to_remove.append(field)

        for field in fields_to_remove:
            data_dict.pop(field, None)

    def get_individual_data(self, individual, is_member, enumerator):
        vals = {
            "is_registrant": True,
            "is_group": False,
            "is_farmer": "yes",
        }
        other_json = {}

        self.process_basic_information(individual, vals, other_json)

        self.process_membership(individual, vals, other_json)
        self.process_land_crop_livestock_information(individual, vals, is_member,other_json )
        self.process_agriculture_resource_finance(individual, vals)

        individual = self.process_reg_ids(individual, "Farmer ODK ACK ID", "odk_reference_id")
        vals["reg_ids"] = individual.get("reg_ids")

        if individual.get("member_registered") and individual.get("member_registered") == "yes":
            individual = self.process_reg_ids(individual, "Member ODK ACK ID", "member_reference_id")
            vals["reg_ids"] = individual.get("reg_ids")

        if individual.get("head_registered") and individual.get("head_registered") == "yes":
            individual = self.process_reg_ids(individual, "Member ODK ACK ID", "member_reference_id")
            vals["reg_ids"] = individual.get("reg_ids")

        if other_json:
            vals["additional_g2p_info"] = json.dumps(other_json)

        if individual.get("farmer_location") is not None:
            vals["partner_longitude"] = individual.get("farmer_location")["coordinates"][0]
            vals["partner_latitude"] = individual.get("farmer_location")["coordinates"][1]

        if enumerator:
            vals["enumerator_id"] = enumerator.id

        self._set_odk_import_source(vals)
        self._set_odk_instance_id(vals, individual.get("odk_instance_id") or individual.get("instance_id"))

        # Remove any fields that don't exist in res.partner model
        self.remove_non_partner_fields_in_place(vals)

        return vals

    def get_member_data(self, member, head, enumerator):
        vals = {"is_registrant": True, "is_group": False, "is_farmer": "no", "hh_is_household_head": "no"}

        first_name, family_name, gf_name_eng = member.get("name").split()
        vals["given_name"] = first_name
        vals["family_name"] = family_name
        vals["gf_name_eng"] = gf_name_eng
        vals["name"] = member.get("name")
        
        if member.get("name_amharic") and member.get("name_amharic").strip():
            fn, mn, ln = member.get("name_amharic").split()
            vals["first_name_amh"] = fn
            vals["family_name_amh"] = mn
            vals["gf_name_amh"] = ln
        
        if member.get("name_other") and member.get("name_other").strip():
            fn, mn, ln = member.get("name_other").split()
            vals["first_name_other"] = fn
            vals["family_name_other"] = mn
            vals["gf_name_other"] = ln
        
        vals["gender"] = member.get("gender")
        vals["birthdate"] = member.get("birthdate")

        region_id = self.process_many2one_field("g2p.region", head.get("region"))
        if region_id:
            if region_id != "other":
                vals["region"] = region_id

        zone_id = self.process_many2one_field("g2p.zone", head.get("zone"))
        if zone_id:
            if zone_id != "other":
                vals["zone"] = zone_id

        woreda_id = self.process_many2one_field("g2p.woreda", head.get("woreda"))
        if woreda_id:
            if woreda_id != "other":
                vals["woreda"] = woreda_id

        kebele_id = self.process_many2one_field("g2p.kebele", head.get("kebele"))
        if kebele_id:
            if kebele_id != "other":
                vals["kebele"] = kebele_id

        language_id = self.process_many2one_field("g2p.lang", head.get("primary_Language"))
        if language_id:
            if language_id != "other":
                vals["primary_Language"] = language_id

        if enumerator:
            vals["enumerator_id"] = enumerator.id

        self._set_odk_import_source(vals)
        self._set_odk_instance_id(vals, head.get("odk_instance_id") or head.get("instance_id"))

        # Remove any fields that don't exist in res.partner model
        self.remove_non_partner_fields_in_place(vals)

        return vals

    def get_membership_kind(self, relationship):
        if relationship == "Wife":
            relationship = "Wife - Head"
        if relationship == "Husband":
            relationship = "Husband - Head"

        membership_kind = (
            self.env["g2p.group.membership.kind"].sudo().search([("name", "=", relationship)], limit=1)
        )
        if not membership_kind:
            membership_kind = self.env["g2p.group.membership.kind"].sudo().create({"name": relationship})
        return membership_kind.id

    def process_land_certificate(self, land_certificate, instance_id):
        # return [None, None]
        if not instance_id:
            return [None, None]

        doc_tag = self.env["g2p.document.tag"].get_or_create_tag_from_name("Land Certificate")

        if not doc_tag:
            doc_tag = self.env["g2p.document.tag"].create({"name": "Land Certificate"})

        get_attachment = self.odk_config.download_attachment(instance_id, land_certificate)

        attachment_base64 = base64.b64encode(get_attachment).decode("utf-8")

        backend_id = (
            self.env.ref("storage_backend.default_storage_backend").id
            or self.env["storage.backend"].search([], limit=1).id
        )
        storage_file = (
            self.env["storage.file"]
            .sudo()
            .create(
                {
                    "name": land_certificate,
                    "backend_id": backend_id,
                    "data": attachment_base64,
                    "tags_ids": [(4, doc_tag.id)],
                }
            )
        )

        return [(4, storage_file.id), storage_file.id]

    def handle_household_head_yes(self):
        return

    def handle_household_head_no(self, mapped_json, individual_data):
        if mapped_json.get("head_registered") == "yes":
            # Search for the head farmer that has this ID under "Farmer ODK ACK ID"
            odk_ack_id_type = (
                self.env["g2p.id.type"].sudo().search([("name", "=", "Farmer ODK ACK ID")], limit=1)
            )
            head = (
                self.env["res.partner"]
                .sudo()
                .search(
                    [
                        (
                            "reg_ids",
                            "in",
                            self.env["g2p.reg.id"]
                            .sudo()
                            .search(
                                [
                                    ("id_type", "=", odk_ack_id_type.id),
                                    ("value", "=", mapped_json.get("member_reference_id")),
                                ]
                            )
                            .ids,
                        )
                    ],
                    limit=1,
                )
            )

            if head:
                # Add the new individual farmer to the household the head belongs to
                group_membership_ids = head.individual_membership_ids
                household = group_membership_ids.group
                r_ship = "Member"

                if mapped_json.get("relationship_with_head") is not None:
                    r_ship = mapped_json.get("relationship_with_head")

                membership_kind = self.get_membership_kind(r_ship)

                individual_data["individual_membership_ids"] = [
                    (0, 0, {"group": household.id, "kind": [(4, membership_kind)]})
                ]
            else:
                reg_ids = individual_data.get("reg_ids")
                # Find the ID type with the name 'Member ODK ACK ID'
                odk_member_ack_id_type = (
                    self.env["g2p.id.type"].sudo().search([("name", "=", "Member ODK ACK ID")], limit=1)
                )
                for reg_id in reg_ids:
                    # Check if the id_type.id and value match
                    if reg_id[2].get("id_type") == odk_member_ack_id_type.id and reg_id[2].get(
                        "value"
                    ) == mapped_json.get("member_reference_id"):
                        # Add the status and description to the matching entry
                        reg_id[2].update(
                            {"status": "invalid", "description": "Head farmer with this ACK ID not found"}
                        )
                        break  # Exit the loop once the matching entry is found and updated
                individual_data["reg_ids"] = reg_ids

        return individual_data

    def process_records_handle_media_import(self, mapped_json, member):
        self.ensure_one()
        instance_id = mapped_json.get("meta", {}).get("instanceID")

        if instance_id:
            mapped_json["instance_id"] = instance_id
            mapped_json["odk_instance_id"] = instance_id
        else:
            instance_id = member.get("meta", {}).get("instanceID")
            if instance_id:
                mapped_json["instance_id"] = instance_id
                mapped_json["odk_instance_id"] = instance_id

    def remove_specific_keys_in_place(self, mapped_json):
        keys_to_remove = [
            "uid",
            "rid",
            "other_woreda",
            "other_kebele",
            "other_land_kebele",
            "phone_ids",
            "head_registered",
            "member_registered",  # Added to fix the error
            "other_primary_cooperative",
            "other_coop_union",
            "farmer_location",
            "hh_income_type",
            "primary_cooperatives",
            # "instance_id"
        ]

        for key in keys_to_remove:
            mapped_json.pop(key, None)

    def process_records_handle_addl_data(self, mapped_json):
        submission_time = mapped_json.get("submission_time") or mapped_json.get("odk_submission_date")
        enumerator = self.create_enumerator(
            mapped_json.get("data_enumerator_name"),
            mapped_json.get("data_enumerator_odk_id"),
            submission_time,
        )

        if mapped_json["hh_is_household_head"] == "yes":
            group = {
                "is_registrant": True,
                "is_group": True,
            }
            individual_ids = []

            # Create household head
            individual_data = self.get_individual_data(mapped_json, False, enumerator)

            # Copy all geographic and land information fields from individual_data to mapped_json
            mapped_json["land_information_ids"] = individual_data.get("land_information_ids", False)
            mapped_json["crop_information_ids"] = individual_data.get("crop_information_ids", False)
            mapped_json["livestock_information_ids"] = individual_data.get("livestock_information_ids", False)
            mapped_json["hh_income_type"] = individual_data.get("hh_income_type", False)
            mapped_json["birthdate"] = individual_data.get("birthdate", False)

            # Geographic fields
            mapped_json["region"] = individual_data.get("region", False)
            mapped_json["zone"] = individual_data.get("zone", False)
            mapped_json["woreda"] = individual_data.get("woreda", False)
            mapped_json["kebele"] = individual_data.get("kebele", False)  # Fixed typo: keble -> kebele
            mapped_json["primary_Language"] = individual_data.get("primary_Language", False)

            mapped_json["size_of_family"] = individual_data.get("size_of_family", False)
            mapped_json["number_of_children_in_family"] = individual_data.get(
                "number_of_children_in_family", False
            )
            mapped_json["number_of_males_in_family"] = individual_data.get("number_of_males_in_family", False)
            mapped_json["number_of_females_in_family"] = individual_data.get(
                "number_of_females_in_family", False
            )

            self.remove_specific_keys_in_place(mapped_json)

            household_found = False
            existing_household = None
            household_head = self.env["res.partner"].sudo().create(individual_data)

            # LINK OTHER FARMER USING REFERENCE ID
            if mapped_json.get("member_registered") == "yes":
                member_reference_id = mapped_json.get("member_reference_id")

                # Search for the farmer that has this ID under "Farmer ODK ACK ID"
                odk_ack_id_type = (
                    self.env["g2p.id.type"].sudo().search([("name", "=", "Farmer ODK ACK ID")], limit=1)
                )
                other_farmer = (
                    self.env["res.partner"]
                    .sudo()
                    .search(
                        [
                            (
                                "reg_ids",
                                "in",
                                self.env["g2p.reg.id"]
                                .sudo()
                                .search(
                                    [
                                        ("id_type", "=", odk_ack_id_type.id),
                                        ("value", "=", member_reference_id),
                                    ]
                                )
                                .ids,
                            )
                        ],
                        limit=1,
                    )
                )

                if other_farmer:
                    r_ship = "Member"
                    if mapped_json.get("relationship_to_head") is not None:
                        r_ship = mapped_json.get("relationship_to_head")
                    if other_farmer.individual_membership_ids.group:
                        household_found = True
                        existing_household = other_farmer.individual_membership_ids.group
                        membership_kind = self.get_membership_kind(r_ship)
                        household_head.sudo().write(
                            {
                                "hh_is_household_head": "no",
                                "individual_membership_ids": [
                                    (0, 0, {"group": existing_household.id, "kind": [(4, membership_kind)]})
                                ],
                            }
                        )
                    else:
                        r_ship = "Member"
                        if mapped_json.get("relationship_to_head") is not None:
                            r_ship = mapped_json.get("relationship_to_head")
                        membership_kind = self.get_membership_kind(r_ship)
                        individual_ids.append(
                            (0, 0, {"individual": other_farmer.id, "kind": [(4, membership_kind)]})
                        )
                else:
                    # Filter household_head.reg_ids to find the specific ID with
                    # "Member ODK ACK ID" and the member_reference_id
                    head_reg_id = household_head.reg_ids.filtered(
                        lambda r: r.id_type.name == "Member ODK ACK ID" and r.value == member_reference_id
                    )
                    # Update the status to 'invalid' and add the description
                    head_reg_id.sudo().write(
                        {"status": "invalid", "description": "Farmer with this ACK ID not found"}
                    )
            membership_kind = self.get_membership_kind("Head")

            individual_ids.append((0, 0, {"individual": household_head.id, "kind": [(4, membership_kind)]}))

            # OTHER HOUSEHOLD MEMBERS WHO ARE FARMERS
            if mapped_json.get("additional_farmers") is not None:
                for additional_farmer in mapped_json.get("additional_farmers"):
                    additional_farmer["instance_id"] = mapped_json.get("instance_id")
                    addl_farmer_data = self.get_individual_data(additional_farmer, True, enumerator)

                    self.remove_specific_keys_in_place(mapped_json)

                    addl_farmer = self.env["res.partner"].sudo().create(addl_farmer_data)
                    membership_kind = self.get_membership_kind(additional_farmer["household_relationship"])
                    if household_found:
                        existing_household.sudo().write(
                            {
                                "group_membership_ids": [
                                    (0, 0, {"individual": addl_farmer.id, "kind": [(4, membership_kind)]})
                                ]
                            }
                        )
                    else:
                        individual_ids.append(
                            (0, 0, {"individual": addl_farmer.id, "kind": [(4, membership_kind)]})
                        )

            # OTHER HOUSEHOLD MEMBERS WHO ARE NOT FARMERS
            if mapped_json.get("other_household_members") is not None:
                for other_household_member in mapped_json.get("other_household_members"):
                    other_member_data = self.get_member_data(other_household_member, mapped_json, enumerator)
                    other_member = self.env["res.partner"].sudo().create(other_member_data)
                    membership_kind = self.get_membership_kind(
                        other_household_member["household_relationship"]
                    )
                    if household_found:
                        existing_household.sudo().write(
                            {
                                "group_membership_ids": [
                                    (0, 0, {"individual": other_member.id, "kind": [(4, membership_kind)]})
                                ]
                            }
                        )
                    else:
                        individual_ids.append(
                            (0, 0, {"individual": other_member.id, "kind": [(4, membership_kind)]})
                        )

            if not household_found:
                group_kind = self.env["g2p.group.kind"].sudo().search([("name", "=", "Household")], limit=1)
                if not group_kind:
                    group_kind = self.env["g2p.group.kind"].sudo().create({"name": "Household"})

                mapped_json["is_registrant"] = True
                mapped_json["is_group"] = True
                mapped_json["enumerator_id"] = enumerator.id
                mapped_json["group_membership_ids"] = individual_ids
                mapped_json["kind"] = group_kind.id

                group_fields = {
                    "is_registrant",
                    "is_group",
                    "name",
                    "region",
                    "zone",
                    "woreda",
                    "kebele",
                    "enumerator_id",
                    "group_membership_ids",
                    "kind",
                    "rec_import_source",
                    "odk_instance_id",
                }

                for key in list(mapped_json.keys()):
                    if key not in group_fields:
                        mapped_json.pop(key, None)

            #     return group
            # else:
            #     return []
        else:
            individual_data = self.get_individual_data(mapped_json, False, enumerator)
         
            individual_data = self.handle_household_head_no(mapped_json, individual_data)

            mapped_json["land_information_ids"] = individual_data.get("land_information_ids", False)
            mapped_json["is_psnp_user"] = individual_data.get("is_psnp_user", False)
            mapped_json["crop_information_ids"] = individual_data.get("crop_information_ids", False)
            mapped_json["livestock_information_ids"] = individual_data.get("livestock_information_ids", False)
            mapped_json["hh_income_type"] = individual_data.get("hh_income_type", False)

            mapped_json["region"] = individual_data.get("region", False)
            mapped_json["zone"] = individual_data.get("zone", False)
            mapped_json["woreda"] = individual_data.get("woreda", False)
            mapped_json["kebele"] = individual_data.get("kebele", False)
            mapped_json["birthdate"] = individual_data.get("birthdate", False)

            mapped_json["primary_Language"] = individual_data.get("primary_Language", False)
            mapped_json["enumerator_id"] = individual_data.get("enumerator_id", False)
            mapped_json["reg_ids"] = individual_data.get("reg_ids", False)
            mapped_json["individual_membership_ids"] = individual_data.get("individual_membership_ids", False)
            mapped_json["is_group"] = False
            mapped_json["primary_Language"] = individual_data.get("primary_Language", False)
            mapped_json["size_of_family"] = individual_data.get("size_of_family", False)
            mapped_json["number_of_children_in_family"] = individual_data.get(
                "number_of_children_in_family", False
            )
            mapped_json["number_of_males_in_family"] = individual_data.get("number_of_males_in_family", False)
            mapped_json["number_of_females_in_family"] = individual_data.get(
                "number_of_females_in_family", False
            )

        self._set_odk_import_source(mapped_json)
        self._set_odk_instance_id(mapped_json, mapped_json.get("odk_instance_id") or mapped_json.get("instance_id"))
        self.remove_non_partner_fields_in_place(mapped_json)
