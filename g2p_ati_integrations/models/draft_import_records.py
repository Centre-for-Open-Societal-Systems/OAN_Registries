import json
import logging

import requests
from datetime import datetime, date
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)
import ast

BATCH_SIZE = 500


class G2PLandInformation(models.Model):
    _inherit = "g2p.land.information"

    polygon_data = fields.Text(string="Polygon Data")
    current_land_use = fields.Text(string="Current Land Use")
    soil_fertility = fields.Text(string="Soil Fertility")
    means_of_acquisition = fields.Text(string="Means Of Acquisition")
    year_of_acquisition = fields.Date(string="Year Of Acquisition")

    integration_status = fields.Selection([("valid", "Valid"), ("invalid", "Invalid")])

    def fetch_land_records(self):
        try:
            api_parameters = self.env["narlis.integration"].sudo().search([], limit=1)
            if not api_parameters:
                raise UserError(_("API configuration is missing. Please configure it in settings."))

            domain = ["|", ("integration_status", "=", False), ("integration_status", "=", "invalid")]

            total_records = self.env["g2p.land.information"].sudo().search_count(domain)

            for offset in range(0, total_records, BATCH_SIZE):
                land_records = (
                    self.env["g2p.land.information"].sudo().search(domain, limit=BATCH_SIZE, offset=offset)
                )

                for land in land_records:
                    url = f"{api_parameters.host_url}{api_parameters.end_point_url}"
                    headers = {
                        "api-key": api_parameters.api_key,
                    }
                    params = {"version": "v1", "upid": land.land_id, "data-depth": "3"}

                    try:
                        response = requests.get(url, headers=headers, params=params, timeout=10)
                        response.raise_for_status()  # Raises an error for non-200 status codes

                        land_informations = response.json()

                        if not land_informations.get("parcel"):
                            land.integration_status = "invalid"
                            continue

                        # Extracting parcel data
                        parcel_data = land_informations.get("parcel", {})
                        rights_data = parcel_data.get("rights", [{}])[0]
                        party_data = rights_data.get("party", {})

                        # Updating land record fields
                        land.partner_id.is_orphan = party_data.get("isorphan", "").lower()
                        land.polygon_data = parcel_data.get("geometryWkt", "")
                        land.current_land_use = parcel_data.get("landUse", "")
                        land.total_land_area = parcel_data.get("parcelArea", 0)
                        land.integration_status = "valid"

                    except (
                        requests.exceptions.Timeout,
                        requests.exceptions.ConnectionError,
                        requests.exceptions.RequestException,
                        ValueError,
                    ):
                        land.integration_status = "invalid"
                        continue  # Skip this record and proceed with the next one

                self.env.cr.commit()

        except UserError as e:
            raise e

    def action_open_map_view(self):
        if self.polygon_data:
            land_details = []
            polygone_data = ast.literal_eval(self.polygon_data)

            land_info = {
                "total_land_area": self.total_land_area,
                "polygon_data": polygone_data,
                "ownership_type": self.ownership_type,
            }
            land_details.append(land_info)
            # List to store details of all lands

            action = {
                "type": "ir.actions.act_window",
                "name": "Partner Map",
                "res_model": "g2p.land.information",
                "view_mode": "lmap",
                "view_id": self.env.ref("g2p_ati_integrations.your_map_view_id").id,
                "target": "new",
                "context": {
                    "polygon_coords": land_details,
                    "partner_latitiude": self.partner_id.partner_latitude,
                    "partner_longitude": self.partner_id.partner_longitude,
                },  # Passing polygon data
            }
            return action

    def update_land_id_prefix(self):
        records = self.search([("land_id", "!=", False), ("land_id", "not ilike", "OR/07/06%")])
        for record in records:
            if record.land_id.startswith("04/"):
                new_land_id = record.land_id.replace("04/", "OR/", 1)
            else:
                new_land_id = f"OR/07/06/{record.land_id}"

            record.land_id = new_land_id

        return True


class G2PDraftRecord(models.Model):
    _inherit = "draft.record"
    _order = "create_date desc"

    gf_name_eng = fields.Char(string="Last Name")
    zone = fields.Char(string="Zone")
    woreda = fields.Char(string="Woreda")
    kebele = fields.Char(string="Kebele")
    validation_status = fields.Many2one("g2p.validation.status")
    status_remark = fields.Text(string="Status Remark")
    import_record_id = fields.Many2one("g2p.imported.record", string="Import Record")
    source = fields.Json(related="import_record_id.source")
    source_db_ids = fields.Many2many(
        related="import_record_id.source_db_ids",
        string="Source DBs",
        readonly=True,
    )

    @api.model
    def create(self, vals):
        record = super().create(vals)

        partner_data = json.loads(record.partner_data or "{}")

        if "addl_name" in partner_data:
            partner_data["gf_name_eng"] = partner_data.pop("addl_name")

        record.partner_data = json.dumps(partner_data)

        return record

    def write(self, vals):
        result = super().write(vals)
        if vals.get("state") in ("rejected", "published"):
            self._close_record_activities()
        return result

    def _close_record_activities(self):
        activities = self.sudo().env["mail.activity"].search(
            [("res_model", "=", "draft.record"), ("res_id", "in", self.ids)]
        )
        if activities:
            activities.action_done()

    def _get_db_import_source_id(self):
        source = self.env.ref("g2p_ati.import_source_db_import", raise_if_not_found=False)
        if not source:
            source = (
                self.env["g2p.import.source"]
                .sudo()
                .search([("code", "=", "db_import")], limit=1)
            )
        return source.id if source else False

    def _notify_draft_owner_rejected(self, reason):
        self.ensure_one()
        owner_user = self.create_uid
        if owner_user:
            note = "Your draft record was rejected."
            if reason:
                note = f"{note} Reason: {reason}"
            self._create_owner_activity(summary="Record Rejected", note=note)

    def action_change_state(self):
        _logger.info("Action Change State called")
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Change State",
            "res_model": "change.state.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("g2p_ati_integrations.change_state_wizard_view").id,
            "target": "new",
            "context": {
                **self.env.context,
                "active_id": self.id,
                "active_ids": self.ids,
                "active_model": self._name,
            },
        }

    def action_publish(self):
        self.ensure_one()
        partner_data = json.loads(self.partner_data)
        res_partner_model = self.env["res.partner"]
        fields_metadata = res_partner_model.fields_get()
        valid_data = {}
        given_name = partner_data.get("given_name", "")
        family_name = partner_data.get("family_name", "")
        gf_name_en = partner_data.get("gf_name_eng", "")

        # Validate phone number types before publishing
        phone_number_ids = partner_data.get("phone_number_ids", [])
        if phone_number_ids:
            for phone_entry in phone_number_ids:
                if isinstance(phone_entry, list) and len(phone_entry) >= 3 and isinstance(phone_entry[2], dict):
                    phone_data = phone_entry[2]
                    phone_type = phone_data.get("phone_type")
                    
                    # Check if phone_type is missing or False
                    if not phone_type:
                        raise ValidationError(_("Phone number type should be set for all phone numbers before publishing."))

        self._prepare_valid_data(valid_data, fields_metadata, partner_data)

        if valid_data:
            valid_data["db_import"] = "yes"
            valid_data.pop("rec_import_source", None)
            db_import_source_id = self._get_db_import_source_id()
            if db_import_source_id:
                valid_data["rec_import_source"] = db_import_source_id
            valid_data["name"] = f"{given_name} {family_name} {gf_name_en}".upper()
            
            import_record = self.sudo().import_record_id
            if import_record and import_record.source:
                valid_data["source"] = import_record.source
            res_partner_model.sudo().create(valid_data)
            self.write({"state": "published"})

            self._notify_validators()
            self._notify_draft_owner_published()

        else:
            raise ValueError("No valid data found to create a partner record.")

    def action_open_wizard(self):
        self.ensure_one()
        if (
            self.state == "submitted"
            and not self.env.user.has_group("g2p_draft_publish.group_int_admin")
            and not self.env.user.has_group("g2p_draft_publish.group_int_approver")
        ):
            raise UserError(_("Edit is not allowed for submitted records."))
        return super().action_open_wizard()

    def action_submit(self):
        for record in self:
            if not record._has_region_in_partner_data():
                raise UserError(
                    _(
                        "Before submitting, Add Region and Location Data in The Draft Farmer Form"
                    )
                )
        result = super().action_submit()
        for record in self:
            # Owner has acted on rejection by resubmitting; close prior rejection activity.
            record._close_owner_status_activities(["Record Rejected"])
            target_users = record._get_target_approver_users()
            record._sync_submit_activities(target_users)
            if target_users:
                record._notify_approvers(target_users)
        return result

    def _get_target_approver_users(self):
        self.ensure_one()
        approver_group = self.env.ref("g2p_draft_publish.group_int_approver")
        approver_users = approver_group.users
        import_record = self.sudo().import_record_id
        if not import_record:
            return approver_users.browse()

        import_region_ids = set(import_record.assigned_region.ids)
        import_language_ids = set(import_record.assigned_languages.ids)

        if not import_region_ids and not import_language_ids:
            return approver_users.browse()

        def _matches(user):
            partner = user.partner_id.sudo()
            if import_region_ids:
                user_region_ids = set(partner.asigned_region.ids)
                if not (user_region_ids & import_region_ids):
                    return False
            if import_language_ids:
                user_language_ids = set(partner.language_skills.ids)
                if not (user_language_ids & import_language_ids):
                    return False
            return True

        return approver_users.filtered(_matches)

    def _has_region_in_partner_data(self):
        self.ensure_one()
        partner_data = self.partner_data or {}
        if isinstance(partner_data, str):
            try:
                partner_data = json.loads(partner_data)
            except (TypeError, ValueError):
                partner_data = {}
        if not isinstance(partner_data, dict):
            return False

        region_value = partner_data.get("region")
        if isinstance(region_value, int):
            return region_value > 0
        if isinstance(region_value, str):
            return bool(region_value.strip())
        return bool(region_value)
    
    def _sync_submit_activities(self, target_users):
        self.ensure_one()
        activity_model = self.sudo().env["mail.activity"]
        todo_type = self.env.ref("mail.mail_activity_data_todo").id
        model_id = self.sudo().env["ir.model"].search([("model", "=", "draft.record")], limit=1).id

        activities = activity_model.search(
            [
                ("res_model", "=", "draft.record"),
                ("res_id", "=", self.id),
                ("activity_type_id", "=", todo_type),
                ("summary", "=", "Record Submitted For Approval"),
            ]
        )

        target_user_ids = set(target_users.ids)
        for activity in activities:
            if activity.user_id.id not in target_user_ids:
                activity.unlink()

        existing_user_ids = set(
            activity_model.search(
                [
                    ("res_model", "=", "draft.record"),
                    ("res_id", "=", self.id),
                    ("activity_type_id", "=", todo_type),
                    ("summary", "=", "Record Submitted For Approval"),
                ]
            ).mapped("user_id").ids
        )

        missing_users = target_users.filtered(lambda user: user.id not in existing_user_ids)
        for user in missing_users:
            activity_model.create(
                {
                    "activity_type_id": todo_type,
                    "res_model_id": model_id,
                    "res_id": self.id,
                    "user_id": user.id,
                    "summary": "Record Submitted For Approval",
                    "note": "Record has been submitted for approval.",
                }
            )

    def _notify_approvers(self, approver_users):
        self.ensure_one()
        partner_ids = approver_users.mapped("partner_id").ids
        if partner_ids:
            self.sudo().message_post(
                body=_("Record submitted for approval."),
                subject=_("Record Submitted"),
                message_type="notification",
                partner_ids=partner_ids,
            )

    def _notify_draft_owner_published(self):
        owner_user = self.create_uid
        if owner_user:
            self._create_owner_activity(
                summary="Record Published",
                note="Your draft record has been published.",
                auto_done=True,
            )

    def _close_owner_status_activities(self, summaries):
        self.ensure_one()
        owner_user = self.create_uid
        if not owner_user:
            return

        activities = self.sudo().env["mail.activity"].search(
            [
                ("res_model", "=", "draft.record"),
                ("res_id", "=", self.id),
                ("user_id", "=", owner_user.id),
                ("summary", "in", summaries),
            ]
        )
        if activities:
            activities.action_done()

    def _create_owner_activity(self, summary, note, auto_done=False):
        self.ensure_one()
        owner_user = self.create_uid
        if not owner_user:
            return

        activity_model = self.sudo().env["mail.activity"]
        todo_type = self.env.ref("mail.mail_activity_data_todo").id
        model_id = self.sudo().env["ir.model"].search([("model", "=", "draft.record")], limit=1).id

        existing = activity_model.search(
            [
                ("res_model", "=", "draft.record"),
                ("res_id", "=", self.id),
                ("activity_type_id", "=", todo_type),
                ("summary", "=", summary),
                ("user_id", "=", owner_user.id),
            ]
        )
        if existing:
            existing.unlink()

        activity = activity_model.create(
            {
                "activity_type_id": todo_type,
                "res_model_id": model_id,
                "res_id": self.id,
                "user_id": owner_user.id,
                "summary": summary,
                "note": note,
            }
        )
        if auto_done:
            activity.action_done()

    def _process_json_data(self, json_data):
        context_data, additional_g2p_info = super()._process_json_data(json_data)
        context_data["default_gf_name_eng"] = self.gf_name_eng
        import_record = self.sudo().import_record_id if self.import_record_id else self.env["g2p.imported.record"]
        import_source = import_record.source if import_record else False
        if "default_source" not in context_data and import_source:
            context_data["default_source"] = import_source
        if import_record and import_record.source_db_ids:
            context_data["default_source_db_ids"] = [(6, 0, import_record.source_db_ids.ids)]
        additional_fields = ['zone', 'woreda', 'kebele']
        for field_name in additional_fields:
            if field_name in json_data:
                field_value = json_data[field_name]
                
                if isinstance(field_value, int) and field_value > 0:
                    print(f"  -> {field_name} is valid ID, adding to context")
                    context_data[f"default_{field_name}"] = field_value
                    removed_value = additional_g2p_info.pop(field_name, None)
                    if removed_value:
                        pass  # print(f"  -> Removed {field_name} from additional_g2p_info: {removed_value}")
                elif field_value is not None and field_value != "" and field_value is not False:
                    additional_g2p_info[field_name] = field_value
                else:
                    print(f"  -> {field_name} is None/False/empty in JSON, checking if should be removed from additional_info")
            else:
                draft_field_value = getattr(self, field_name, None)
                # print(f"Draft record {field_name}: {draft_field_value}")
                
                # Only add from draft record if not already in additional_g2p_info and has value
                if field_name not in additional_g2p_info and draft_field_value and draft_field_value.strip():
                    # The draft record has a value for this field, add it to additional_g2p_info
                    # print(f"  -> Adding draft record {field_name} to additional_g2p_info: {draft_field_value}")
                    additional_g2p_info[field_name] = draft_field_value
                else:
                    print(f"  -> Not modifying additional_g2p_info for {field_name} (already exists or no draft value)")



        return context_data, additional_g2p_info


  

class G2PRespartnerIntegration(models.Model):
    _inherit = "res.partner"

    is_orphan = fields.Selection([("yes", "Yes"), ("no", "No")])
    asigned_region = fields.Many2many("g2p.region", string="Regions")
    language_skills = fields.Many2many("g2p.lang", string="Languages")
    source = fields.Json(string="Source Information", help="Stores the source information in JSON format")
    source_db_ids = fields.Many2many(
        "g2p.imported.record.source",
        "g2p_res_partner_source_rel",
        "partner_id",
        "source_id",
        string="Source DBs",
        compute="_compute_source_db_ids",
        store=True,
        readonly=True,
    )
    def write(self, values):
        result = super().write(values)

        if "asigned_region" in values or "language_skills" in values:
            self.env.registry.clear_cache()

        return result

    @api.depends("source")
    def _compute_source_db_ids(self):
        Source = self.env["g2p.imported.record.source"].sudo()
        extractor = self.env["g2p.imported.record"]
        all_names = []
        per_record_names = {}

        for record in self:
            names = extractor._extract_source_names(record.source)
            per_record_names[record.id] = names
            all_names.extend(names)

        unique_names = []
        seen = set()
        for name in all_names:
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            unique_names.append(name)

        existing_map = {}
        if unique_names:
            existing = Source.search([("name", "in", unique_names)])
            existing_map = {rec.name.lower(): rec for rec in existing}

            to_create = []
            for name in unique_names:
                key = name.lower()
                if key in existing_map:
                    continue
                matched = Source.search([("name", "=ilike", name)], limit=1)
                if matched:
                    existing_map[matched.name.lower()] = matched
                else:
                    to_create.append(name)
            if to_create:
                created = Source.create([{"name": name} for name in to_create])
                for rec in created:
                    existing_map[rec.name.lower()] = rec

        for record in self:
            names = per_record_names.get(record.id, [])
            source_ids = [existing_map[name.lower()].id for name in names if name.lower() in existing_map]
            record.source_db_ids = [(6, 0, source_ids)] if source_ids else [(5, 0, 0)]

    # def _ensure_source_db_ids(self):
    #     if not self:
    #         return
    #     self.with_context(skip_source_db_ensure=True)._compute_source_db_ids()
    #     self.flush_recordset(["source_db_ids"])

    # def read(self, fields=None, load="_classic_read"):
    #     if not self.env.context.get("skip_source_db_ensure"):
    #         if not fields or "source_db_ids" in fields or "source" in fields:
    #             self._ensure_source_db_ids()
    #     return super().read(fields=fields, load=load)



    def action_save_to_draft(self, vals):
        """
        Saves data from the wizard to the draft record.

        --- EXTENDED METHOD v4 ---
        This version correctly handles both initial setup and subsequent changes
        for cascading administrative fields.
        """
        _logger.info("Executing extended action_save_to_draft v4 with robust dependency handling.")

        context = self.env.context
        model_name = context.get("active_model")
        record_id = context.get("active_id")
        if not all([model_name, record_id]):
            raise UserError(_("Could not find the source draft record. Missing context."))

        active_record = self.env[model_name].browse(record_id)
        active_record.ensure_one()



        # 2. Load the original `partner_data`
        try:
            original_partner_data = json.loads(active_record.partner_data or "{}")
        except (json.JSONDecodeError, TypeError):
            original_partner_data = {}



        # Create a working copy to modify
        partner_data = original_partner_data.copy()

        # 3. Reconcile invalid data from `additional_g2p_info` first
        additional_info_str = vals.get("additional_g2p_info", "{}")
        try:
            additional_info = json.loads(additional_info_str)
        except (json.JSONDecodeError, TypeError):
            additional_info = {}



        processed_vals = vals.copy()
        if additional_info:
            for field_name, original_invalid_value in additional_info.items():
                # print(f"Processing {field_name}: original_invalid={original_invalid_value}, vals_value={processed_vals.get(field_name)}")
                if field_name in processed_vals and not processed_vals[field_name]:
                    # print(f"  -> Restoring {field_name} to {original_invalid_value}")
                    processed_vals[field_name] = original_invalid_value
                else:
                    print(f"  -> NOT restoring {field_name} (has valid value or not in vals)")

   
        # Check if region changed. If so, clear children in our temporary data copy.
        # The final update from processed_vals will restore them if they were set in the same wizard transaction.
        if processed_vals.get('region') != partner_data.get('region'):
            _logger.info("Region changed. Invalidating child fields before final update.")
            partner_data['zone'] = False
            partner_data['woreda'] = False
            partner_data['kebele'] = False

        # Independent check: if zone changed, clear its children.
        if processed_vals.get('zone') != partner_data.get('zone'):
            _logger.info("Zone changed. Invalidating child fields before final update.")
            partner_data['woreda'] = False
            partner_data['kebele'] = False
        
        # Independent check: if woreda changed, clear its child.
        if processed_vals.get('woreda') != partner_data.get('woreda'):
            _logger.info("Woreda changed. Invalidating child fields before final update.")
            partner_data['kebele'] = False

        # 5. Merge ALL values from the wizard. This overwrites our invalidations
        # if valid children were provided in the same transaction.
        partner_data.update(processed_vals)



        # 6. Handle specific data transformations (name, flags)
        name_parts = [
            partner_data.get("given_name", context.get("given_name")),
            partner_data.get("family_name", context.get("family_name")),
            partner_data.get("gf_name_eng", context.get("gf_name_eng")),
        ]
        computed_name = " ".join(filter(None, name_parts)).strip().upper()
        if computed_name:
            partner_data["name"] = computed_name

        partner_data.update({
            "is_company": False,
            "is_group": False,
            "is_registrant": True,
            "db_import": "yes",
        })

        # 7. Prepare the final dictionary for the `write` call
        final_update_vals = {"partner_data": json.dumps(partner_data)}

        # 8. Denormalize all relevant fields. This part remains the same.
        draft_model_fields = active_record._fields

        # Simple fields
        fields_to_sync = ["name", "given_name", "family_name", "gf_name_eng", "gender"]
        for field_name in fields_to_sync:
            if field_name in partner_data and field_name in draft_model_fields:
                final_update_vals[field_name] = partner_data.get(field_name)

        # Hierarchical and other special fields
        denormalize_map = {
            'region': 'g2p.region', 'zone': 'g2p.zone',
            'woreda': 'g2p.woreda', 'kebele': 'g2p.kebele',
        }
        for field_name, model_name in denormalize_map.items():
            if field_name in draft_model_fields: # Check if field exists on draft model
                field_val = partner_data.get(field_name)
                if isinstance(field_val, int) and field_val > 0:
                    # Valid ID - get the name from the related model
                    obj = self.env[model_name].browse(field_val).exists()
                    if obj:
                        final_update_vals[field_name] = obj.name
                elif isinstance(field_val, str) and field_val.strip():
                    # Invalid text value - preserve it in the draft record field
                    final_update_vals[field_name] = field_val
                elif field_name in partner_data and (field_val is False or field_val == 0 or field_val == ""):
                    # Field exists in partner_data but is explicitly cleared (False, 0, empty string)
                    # Clear it in the draft record too
                    final_update_vals[field_name] = ''


        if "gender" in partner_data and partner_data.get("gender") and "gender" in draft_model_fields:
            gender_val = partner_data.get("gender")
            if isinstance(gender_val, int):
                gender_obj = self.env["g2p.gender"].browse(gender_val).exists()
                if gender_obj:
                    final_update_vals["gender"] = gender_obj.name 
            # else:  # It's likely the original invalid text

        # Phone
        if "phone_number_ids" in partner_data and "phone" in draft_model_fields:
            phone_numbers = partner_data.get("phone_number_ids", [])
            phone_no = False
            if phone_numbers and isinstance(phone_numbers, list) and phone_numbers[0][2]:
                phone_no = phone_numbers[0][2].get("phone_no", False)
                if phone_no:
                    final_update_vals["phone"] = phone_no

     

        active_record.write(final_update_vals)

 
        
        # Check the updated partner_data
        updated_partner_data = json.loads(active_record.partner_data or "{}")


  
            
       
    def view_all_lands(self):
        land_details = []  # List to store details of all lands
        for land in self.land_information_ids:
            if land.polygon_data:
                # Parse the string representation of the polygon data into an actual list of coordinates
                try:
                    polygon = ast.literal_eval(land.polygon_data)
                except (ValueError, SyntaxError):
                    print(f"Invalid polygon data: {land.polygon_data}")
                    continue

                # Collect all the relevant land information in a dictionary
                land_info = {
                    "total_land_area": land.total_land_area,
                    "polygon_data": polygon,
                    "ownership_type": land.ownership_type,
                }

                land_details.append(land_info)
        action = {
            "type": "ir.actions.act_window",
            "name": "Partner Map",
            "res_model": "res.partner",
            "view_mode": "lmap",
            "view_id": self.env.ref("g2p_ati_integrations.your_map_view_id").id,
            "target": "new",
            "context": {
                "polygon_coords": land_details,
                "partner_latitiude": self.partner_latitude,
                "partner_longitude": self.partner_longitude,
            },  # Passing polygon data
        }
        return action




class G2PRegIdInherit(models.Model):
    _inherit = "g2p.reg.id"

    @api.onchange("value")
    def _onchange_value(self):
        national_ids = self.env["g2p.reg.id"].sudo().search([], limit=1)

        for rec in national_ids:
            if self.value != False and self.value == rec.value and self.id_type == rec.id_type:
                raise UserError(_("Farmer With the same id exists in the system"))
