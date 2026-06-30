import base64
import json
import logging
import traceback
from datetime import datetime, timezone
from datetime import timedelta
from uuid import uuid4

import jq

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OdkImport(models.Model):
    _inherit = "odk.import"

    is_consent_import = fields.Boolean(string="Consent Import")
    enable_webhook_import = fields.Boolean(string="Enable Webhook Import")
    webhook_secret = fields.Char(
        string="Webhook Secret",
        copy=False,
        default=lambda self: uuid4().hex,
    )
    webhook_url = fields.Char(string="Webhook URL", compute="_compute_webhook_url")

    def _compute_webhook_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        for rec in self:
            rec.webhook_url = (
                f"{base_url}/api/odk/import/{rec.id}/webhook" if rec.id and base_url else False
            )

    def action_regenerate_webhook_secret(self):
        for rec in self:
            rec.webhook_secret = uuid4().hex

    def extract_webhook_secret(self, payload=None, params=None):
        self.ensure_one()
        headers = request_headers = self.env.context.get("odk_webhook_headers") or {}
        payload = payload or {}
        params = params or {}

        auth_header = request_headers.get("Authorization") or request_headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            return auth_header.split(" ", 1)[1].strip()

        for key in ("X-Webhook-Secret", "X-ODK-Webhook-Secret", "x-webhook-secret", "x-odk-webhook-secret"):
            if request_headers.get(key):
                return request_headers[key].strip()

        for key in ("webhook_secret", "secret", "token"):
            value = payload.get(key) or params.get(key)
            if value:
                return str(value).strip()
        return ""

    def is_valid_webhook_secret(self, provided_secret):
        self.ensure_one()
        expected_secret = (self.webhook_secret or "").strip()
        return bool(expected_secret and provided_secret and expected_secret == provided_secret)

    def extract_instance_id_from_webhook_payload(self, payload=None, params=None):
        payload = payload or {}
        params = params or {}

        candidate_values = [
            payload.get("instance_id"),
            payload.get("__id"),
            payload.get("instanceId"),
            payload.get("submission_id"),
            params.get("instance_id"),
            params.get("__id"),
            params.get("instanceId"),
        ]
        meta = payload.get("meta") or {}
        if isinstance(meta, dict):
            candidate_values.extend([meta.get("instanceID"), meta.get("instanceId")])

        data = payload.get("data") or {}
        if isinstance(data, dict):
            candidate_values.extend(
                [
                    data.get("instance_id"),
                    data.get("__id"),
                    data.get("instanceId"),
                ]
            )
            data_meta = data.get("meta") or {}
            if isinstance(data_meta, dict):
                candidate_values.extend([data_meta.get("instanceID"), data_meta.get("instanceId")])

        for value in candidate_values:
            if value:
                return str(value).strip()
        return ""

    def process_records(self, instance_id=None, last_sync_time=None):
        self.ensure_one()
        if not self.is_consent_import:
            return super().process_records(instance_id=instance_id, last_sync_time=last_sync_time)

        if not self.odk_config:
            raise ValidationError(_("Please configure the ODK."))

        data = self.odk_config.download_records(instance_id=instance_id, last_sync_time=last_sync_time)
        created_count = 0
        skipped_count = 0
        failed_count = 0

        for member in data.get("value", []):
            current_instance_id = self._extract_instance_id({}, member)
            try:
                mapped_json = self._map_submission(member)
                current_instance_id = self._extract_instance_id(mapped_json, member)
                result = self._process_consent_submission(mapped_json, member)
                if result == "created":
                    created_count += 1
                else:
                    skipped_count += 1
            except Exception as exc:
                failed_count += 1
                _logger.exception(
                    "Consent ODK import failed for instance_id=%s: %s",
                    current_instance_id or "unknown",
                    exc,
                )

        if created_count:
            data["form_updated"] = True
        if failed_count:
            data["form_failed"] = True

        data["partner_count"] = created_count
        data["consent_count"] = created_count
        data["skipped_count"] = skipped_count
        data["failed_count"] = failed_count
        return data

    def process_pending_instances(self):
        self.ensure_one()
        if not self.is_consent_import:
            return super().process_pending_instances()

        _logger.info("Processing consent ODK async queue synchronously for import_id=%s", self.id)
        batch_size = 10
        pending_instance_ids = (
            self.env["odk.instance.id"]
            .sudo()
            .search([("status", "=", "pending"), ("odk_import_id", "=", self.id)])
        )
        if not pending_instance_ids:
            _logger.info("No pending consent ODK instance IDs found for import_id=%s", self.id)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "warning",
                    "message": "No pending instance IDs found to process.",
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        total_instances = len(pending_instance_ids)
        for batch_start in range(0, total_instances, batch_size):
            batch = pending_instance_ids[batch_start : batch_start + batch_size]
            self._process_pending_instance_id(batch)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": f"Processed {total_instances} consent ODK instance IDs.",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _process_pending_instance_id(self, instance_ids):
        self.ensure_one()
        if not self.is_consent_import:
            return super()._process_pending_instance_id(instance_ids)

        for instance in instance_ids:
            _logger.info("Processing consent ODK instance ID: %s", instance.instance_id)
            instance.status = "processing"
            try:
                imported = instance.odk_import_id.process_records(instance_id=instance.instance_id)
                if imported.get("form_failed"):
                    instance.status = "failed"
                else:
                    instance.status = "done"
            except Exception as exc:
                _logger.error(traceback.format_exc())
                _logger.error("Failed to import consent ODK instance ID %s: %s", instance.instance_id, exc)
                instance.status = "failed"

    def _map_submission(self, member):
        mapped_json = jq.first(self.json_formatter, member) or {}
        if not isinstance(mapped_json, dict):
            raise ValidationError(_("The consent jq formatter must return a JSON object."))
        return self._backfill_known_fields_from_member(mapped_json, member)

    def _member_value(self, member, *paths):
        for path in paths:
            if not path:
                continue
            if path in member and member.get(path) not in (None, ""):
                return member.get(path)

            current = member
            found = True
            for part in path.split("."):
                if isinstance(current, dict) and part in current:
                    current = current.get(part)
                else:
                    found = False
                    break
            if found and current not in (None, ""):
                return current
        return None

    def _backfill_known_fields_from_member(self, mapped_json, member):
        fallback_map = {
            "partner_user_login": (
                "page_identity.partner_user_login",
                "page_identity-partner_user_login",
                "partner_user_login",
                "SubmitterName",
            ),
            "national_id": (
                "page_identity.national_id",
                "page_identity-national_id",
                "national_id",
            ),
            "farmer_id": (
                "page_identity.farmer_id",
                "page_identity-farmer_id",
                "farmer_id",
            ),
            "consent_type": (
                "page_request_details.consent_type",
                "page_request_details-consent_type",
                "consent_type",
            ),
            "validity_months": (
                "page_request_details.validity_months",
                "page_request_details-validity_months",
                "validity_months",
            ),
            "purpose": (
                "page_request_details.purpose",
                "page_request_details-purpose",
                "purpose",
            ),
            "allowed_data_field_codes": (
                "page_request_details.allowed_data_field_codes",
                "page_request_details-allowed_data_field_codes",
                "allowed_data_field_codes",
            ),
            "consent_attachment": (
                "page_evidence.consent_attachment",
                "page_evidence-consent_attachment",
                "consent_attachment",
            ),
            "camera_capture_image": (
                "page_evidence.camera_capture_image",
                "page_evidence-camera_capture_image",
                "camera_capture_image",
            ),
            "camera_capture_taken_at": (
                "page_evidence.camera_capture_taken_at",
                "page_evidence-camera_capture_taken_at",
                "camera_capture_taken_at",
            ),
            "instance_id": (
                "meta.instanceID",
                "meta-instanceID",
                "__id",
                "KEY",
            ),
            "odk_submitter_name": ("SubmitterName", "__system.submitterName"),
            "odk_submitter_id": ("SubmitterID", "__system.submitterId"),
        }

        for field_name, paths in fallback_map.items():
            if mapped_json.get(field_name) in (None, "", []):
                value = self._member_value(member, *paths)
                if value not in (None, "", []):
                    mapped_json[field_name] = value

        latitude = self._member_value(
            member,
            "page_evidence.camera_capture_location.Latitude",
            "page_evidence-camera_capture_location-Latitude",
        )
        longitude = self._member_value(
            member,
            "page_evidence.camera_capture_location.Longitude",
            "page_evidence-camera_capture_location-Longitude",
        )
        altitude = self._member_value(
            member,
            "page_evidence.camera_capture_location.Altitude",
            "page_evidence-camera_capture_location-Altitude",
        )
        accuracy = self._member_value(
            member,
            "page_evidence.camera_capture_location.Accuracy",
            "page_evidence-camera_capture_location-Accuracy",
        )
        if (
            mapped_json.get("camera_capture_location") in (None, "", [])
            and latitude not in (None, "")
            and longitude not in (None, "")
        ):
            mapped_json["camera_capture_location"] = {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
                "accuracy": accuracy,
            }

        return mapped_json

    def _process_consent_submission(self, mapped_json, member):
        instance_id = self._extract_instance_id(mapped_json, member)
        if not instance_id:
            raise ValidationError(_("ODK instance ID is required for consent imports."))

        if self.env["g2p.consent.request"].sudo().search_count(
            [("consent_creation_request_id", "=", instance_id)]
        ):
            _logger.info("Skipping duplicate consent import for instance_id=%s", instance_id)
            return "skipped"

        partner_user, consent_partner = self._resolve_consent_partner(mapped_json)
        farmer = self._find_farmer(mapped_json)
        requested_field_ids = self._resolve_data_field_ids(
            consent_partner,
            mapped_json.get("allowed_data_field_codes"),
        )
        media_vals, attachments = self._prepare_media_vals(instance_id, mapped_json)
        vals = self._build_consent_vals(
            mapped_json=mapped_json,
            instance_id=instance_id,
            partner_user=partner_user,
            consent_partner=consent_partner,
            farmer=farmer,
            requested_field_ids=requested_field_ids,
            media_vals=media_vals,
        )
        consent = self.env["g2p.consent.request"].sudo().create(vals)
        if attachments:
            attachments.write({"res_id": consent.id})
        _logger.info(
            "Consent request imported from ODK: id=%s instance_id=%s farmer_id=%s partner_id=%s",
            consent.id,
            instance_id,
            farmer.id,
            consent_partner.id,
        )
        return "created"

    def _extract_instance_id(self, mapped_json, member):
        return (
            mapped_json.get("instance_id")
            or mapped_json.get("meta", {}).get("instanceID")
            or member.get("meta", {}).get("instanceID")
            or member.get("__id")
        )

    def _find_partner_user(self, login):
        login = (login or "").strip()
        if not login:
            return self.env["res.users"].browse()

        user = self.env["res.users"].sudo().search(
            ["|", ("login", "=ilike", login), ("partner_id.email", "=ilike", login)],
            limit=1,
        )
        return user

    def _resolve_consent_partner(self, mapped_json):
        partner_user_login = (mapped_json.get("partner_user_login") or "").strip()
        if partner_user_login:
            partner_user = self._find_partner_user(partner_user_login)
            if partner_user:
                return partner_user, self._get_consent_partner(partner_user)

        partner = self._find_consent_partner_by_identifiers(mapped_json)
        if partner:
            return self.env.user, partner

        _logger.error(
            "Consent partner resolution failed. mapped identifiers: partner_user_login=%r partner_record_id=%r partner_code=%r partner_name=%r instance_id=%r",
            mapped_json.get("partner_user_login"),
            mapped_json.get("partner_record_id"),
            mapped_json.get("partner_code"),
            mapped_json.get("partner_name"),
            mapped_json.get("instance_id"),
        )
        raise ValidationError(
            _(
                "Could not resolve the consent partner. Provide one of: "
                "partner_user_login, partner_code, partner_record_id, or partner_name."
            )
        )

    def _find_consent_partner_by_identifiers(self, mapped_json):
        partner_obj = self.env["res.partner"].sudo()

        partner_record_id = mapped_json.get("partner_record_id")
        if partner_record_id not in (None, "", False):
            try:
                partner = partner_obj.browse(int(partner_record_id))
            except (TypeError, ValueError):
                partner = partner_obj.browse()
            if partner.exists() and partner.is_consent_parent and partner.active:
                return partner

        partner_code = (mapped_json.get("partner_code") or "").strip()
        if partner_code:
            partner = partner_obj.search(
                [
                    ("is_consent_parent", "=", True),
                    ("active", "=", True),
                    "|",
                    ("ref", "=", partner_code),
                    ("name", "=", partner_code),
                ],
                limit=1,
            )
            if partner:
                return partner

        partner_name = (mapped_json.get("partner_name") or "").strip()
        if partner_name:
            partner = partner_obj.search(
                [("is_consent_parent", "=", True), ("active", "=", True), ("name", "=", partner_name)],
                limit=1,
            )
            if partner:
                return partner

        return partner_obj.browse()

    def _get_consent_partner(self, user):
        partner = user.consent_parent_partner_id
        if not partner:
            raise ValidationError(_("User '%s' is not linked to a consent parent partner.") % user.login)
        if not partner.is_consent_parent:
            raise ValidationError(
                _("Partner '%s' is not configured as a consent parent.") % partner.display_name
            )
        if not partner.active:
            raise ValidationError(_("Consent partner '%s' is inactive.") % partner.display_name)
        return partner

    def _approved_farmer_domain(self):
        return [("is_registrant", "=", True), ("is_group", "=", False), ("state", "=", "approved")]

    def _find_farmer(self, mapped_json):
        partner_obj = self.env["res.partner"].sudo()
        reg_id_obj = self.env["g2p.reg.id"].sudo()
        base_domain = self._approved_farmer_domain()

        farmer_db_id = mapped_json.get("farmer_db_id")
        if farmer_db_id:
            try:
                farmer = partner_obj.search(base_domain + [("id", "=", int(farmer_db_id))], limit=1)
            except (TypeError, ValueError):
                farmer = partner_obj.browse()
            if farmer:
                return farmer

        farmer_external_id = (mapped_json.get("farmer_id") or "").strip()
        if farmer_external_id:
            farmer = partner_obj.search(base_domain + [("farmer_id", "=", farmer_external_id)], limit=1)
            if farmer:
                return farmer

        candidate_values = []
        for key in ("national_id", "uid", "rid"):
            value = (mapped_json.get(key) or "").strip()
            if value and value not in candidate_values:
                candidate_values.append(value)

        for search_value in candidate_values:
            farmer = partner_obj.search(base_domain + [("unique_id", "=", search_value)], limit=1)
            if farmer:
                return farmer

            reg_ids = reg_id_obj.search([("value", "=", search_value)], limit=100)
            if reg_ids:
                farmer = partner_obj.search(
                    base_domain + [("id", "in", reg_ids.mapped("partner_id").ids)],
                    limit=1,
                )
                if farmer:
                    return farmer

        raise ValidationError(
            _("Farmer not found. Provide a valid farmer_db_id, farmer_id, national_id, UID, or RID.")
        )

    def _normalize_codes(self, value):
        if not value:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except ValueError:
                    parsed = None
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in stripped.replace(",", " ").split() if item.strip()]
        return [str(value).strip()]

    def _resolve_data_field_ids(self, consent_partner, codes):
        normalized_codes = []
        seen_codes = set()
        for code in self._normalize_codes(codes):
            lowered = code.lower()
            if lowered not in seen_codes:
                normalized_codes.append(code)
                seen_codes.add(lowered)
        if not normalized_codes:
            raise ValidationError(_("allowed_data_field_codes is required for consent imports."))

        available_fields = self.env["g2p.consent.data.field"].sudo().search([("active", "=", True)])
        fields_by_code = {
            (field.code or "").strip().lower(): field
            for field in available_fields
            if (field.code or "").strip()
        }
        resolved_fields = []
        for code in normalized_codes:
            field = fields_by_code.get(code.lower())
            if field:
                resolved_fields.append(field)

        allowed_partner_ids = set(consent_partner.allowed_data_field_ids.ids)
        filtered_ids = [field.id for field in resolved_fields if field.id in allowed_partner_ids]
        if not filtered_ids:
            raise ValidationError(
                _(
                    "No valid consent data fields were found for partner '%s'. "
                    "Check the submitted codes and the partner's allowed data fields."
                )
                % consent_partner.display_name
            )
        return filtered_ids

    def _extract_filename(self, value):
        if isinstance(value, list):
            return next((str(item).strip() for item in value if str(item).strip()), False)
        if isinstance(value, str):
            value = value.strip()
            return value or False
        return False

    def _download_odk_file(self, instance_id, filename):
        filename = self._extract_filename(filename)
        if not filename:
            return None
        content = self.odk_config.download_attachment(instance_id, filename)
        if not content:
            raise ValidationError(_("Unable to download ODK attachment '%s'.") % filename)
        return content

    def _prepare_media_vals(self, instance_id, mapped_json):
        attachment_model = self.env["ir.attachment"].sudo()
        attachments = attachment_model.browse()
        vals = {}

        consent_attachment = self._extract_filename(mapped_json.get("consent_attachment"))
        if not consent_attachment:
            raise ValidationError(_("consent_attachment is required for consent imports."))

        consent_attachment_data = self._download_odk_file(instance_id, consent_attachment)
        attachments |= attachment_model.create(
            {
                "name": consent_attachment,
                "datas": base64.b64encode(consent_attachment_data),
                "res_model": "g2p.consent.request",
                "res_id": 0,
            }
        )
        vals["attachment_ids"] = [(6, 0, attachments.ids)]

        camera_capture_image = self._extract_filename(mapped_json.get("camera_capture_image"))
        if camera_capture_image:
            camera_capture_data = self._download_odk_file(instance_id, camera_capture_image)
            vals["portal_capture_image"] = base64.b64encode(camera_capture_data)
            vals["portal_capture_image_filename"] = camera_capture_image

        capture_taken_at = self._coerce_datetime(
            mapped_json.get("camera_capture_taken_at")
            or mapped_json.get("submission_time")
            or mapped_json.get("odk_submission_date")
        )
        if capture_taken_at:
            vals["portal_capture_taken_at"] = fields.Datetime.to_string(capture_taken_at)

        vals.update(self._extract_capture_location_vals(mapped_json.get("camera_capture_location")))
        if mapped_json.get("camera_capture_accuracy") is not None and "portal_capture_accuracy_m" not in vals:
            accuracy = self._coerce_float(mapped_json.get("camera_capture_accuracy"))
            if accuracy is not None:
                vals["portal_capture_accuracy_m"] = accuracy

        return vals, attachments

    def _coerce_datetime(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            if value.tzinfo:
                return value.astimezone(timezone.utc).replace(tzinfo=None)
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None
            try:
                dt_value = fields.Datetime.to_datetime(normalized)
                if dt_value:
                    return dt_value
            except (TypeError, ValueError):
                pass
            try:
                dt_value = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
            except ValueError:
                dt_value = None
            if dt_value:
                if dt_value.tzinfo:
                    return dt_value.astimezone(timezone.utc).replace(tzinfo=None)
                return dt_value
        return None

    def _coerce_float(self, value):
        if value in (None, "", False):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _extract_capture_location_vals(self, raw_location):
        if not raw_location:
            return {}

        latitude = None
        longitude = None
        accuracy = None

        if isinstance(raw_location, dict):
            coordinates = raw_location.get("coordinates")
            if isinstance(coordinates, (list, tuple)) and len(coordinates) >= 2:
                longitude = self._coerce_float(coordinates[0])
                latitude = self._coerce_float(coordinates[1])
            if latitude is None:
                latitude = self._coerce_float(
                    raw_location.get("latitude") or raw_location.get("lat")
                )
            if longitude is None:
                longitude = self._coerce_float(
                    raw_location.get("longitude") or raw_location.get("lon")
                )
            accuracy = self._coerce_float(
                raw_location.get("accuracy") or raw_location.get("accuracy_m")
            )
        elif isinstance(raw_location, (list, tuple)) and len(raw_location) >= 2:
            longitude = self._coerce_float(raw_location[0])
            latitude = self._coerce_float(raw_location[1])
        elif isinstance(raw_location, str):
            parts = [part for part in raw_location.replace(",", " ").split() if part]
            if len(parts) >= 2:
                latitude = self._coerce_float(parts[0])
                longitude = self._coerce_float(parts[1])
            if len(parts) >= 4:
                accuracy = self._coerce_float(parts[3])

        vals = {}
        if latitude is not None or longitude is not None:
            if latitude is None or longitude is None:
                raise ValidationError(_("camera_capture_location must include both latitude and longitude."))
            if latitude < -90 or latitude > 90 or longitude < -180 or longitude > 180:
                raise ValidationError(_("camera_capture_location coordinates are out of range."))
            vals["portal_capture_latitude"] = latitude
            vals["portal_capture_longitude"] = longitude
        if accuracy is not None:
            if accuracy < 0:
                raise ValidationError(_("camera_capture_location accuracy cannot be negative."))
            vals["portal_capture_accuracy_m"] = accuracy
        return vals

    def _normalize_consent_type(self, value):
        return value if value in {"baseline", "specific"} else "specific"

    def _normalize_originated_from(self, value):
        return value if value in {"beneficiary", "agent", "staff", "partner"} else "partner"

    def _coerce_months(self, value):
        try:
            months = int(value) if value not in (None, "", False) else 12
        except (TypeError, ValueError):
            months = 12
        return max(months, 1)

    def _build_consent_vals(
        self,
        mapped_json,
        instance_id,
        partner_user,
        consent_partner,
        farmer,
        requested_field_ids,
        media_vals,
    ):
        purpose = (mapped_json.get("purpose") or "").strip()
        if not purpose:
            raise ValidationError(_("purpose is required for consent imports."))

        now = fields.Datetime.now()
        validity_months = self._coerce_months(mapped_json.get("validity_months"))
        vals = {
            "consent_creation_request_id": instance_id,
            "partner_record_id": consent_partner.id,
            "farmer_id": farmer.id,
            "consent_type": self._normalize_consent_type(mapped_json.get("consent_type")),
            "purpose": purpose,
            "validity_from": now,
            "validity_to": now + timedelta(days=validity_months * 30),
            "originated_from": self._normalize_originated_from(mapped_json.get("originated_from")),
            "status": "pending",
            "requester_user_id": partner_user.id if partner_user else self.env.user.id,
            "allowed_data_field_ids": [(6, 0, requested_field_ids)],
        }

        for optional_field in (
            "consent_provider_register",
            "consent_provider_person_id",
            "consent_target_object_ids",
            "attribute_lists",
            "rejection_reason",
        ):
            if mapped_json.get(optional_field):
                vals[optional_field] = mapped_json.get(optional_field)

        vals.update(media_vals)
        return vals
