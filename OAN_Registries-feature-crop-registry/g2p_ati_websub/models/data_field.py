import json
import logging
from datetime import date, datetime

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


FILTER_OPERATOR_SELECTION = [
    ("=", "Equals"),
    ("!=", "Not Equals"),
    ("in", "In"),
    ("not in", "Not In"),
    ("ilike", "Contains"),
]

PATH_PICKER_RELATIONAL_TYPES = {"many2one", "one2many", "many2many"}
PATH_PICKER_EXCLUDED_TYPES = {"binary", "html"}
PATH_PICKER_MAX_DEPTH = 4
PATH_PICKER_IMAGE_PREFIXES = ("avatar_", "image_")
PATH_PICKER_EXCLUDED_PREFIXES = ("message_", "activity_", "website_")
PATH_PICKER_EXCLUDED_NAMES = {
    "__last_update",
    "active_lang_count",
    "active_test",
    "activity_exception_decoration",
    "activity_state",
    "activity_summary",
    "activity_type_icon",
    "commercial_partner_id",
    "create_date",
    "create_uid",
    "display_name",
    "id",
    "preview_partner_id",
    "preview_payload",
    "source_model_display",
    "source_path_display",
    "filter_model_display",
    "filter_path_display",
    "fallback_filter_model_display",
    "fallback_filter_path_display",
    "write_date",
    "write_uid",
}


class G2PConsentDataFieldMapLine(models.Model):
    _name = "g2p.consent.data.field.map.line"
    _description = "Consent Data Field Mapping Line"
    _order = "id"

    data_field_id = fields.Many2one(
        "g2p.consent.data.field",
        required=True,
        ondelete="cascade",
    )
    payload_key = fields.Char(
        help="Optional key to use inside this data field payload. Defaults to the final segment of source path."
    )
    source_path = fields.Char(
        required=True,
        help=(
            "Dot path from farmer (res.partner), e.g. "
            "'region.name' or 'land_information_ids.total_land_area'."
        ),
    )
    filter_path = fields.Char(
        help=(
            "Optional filter path evaluated on the first collection record in source path, "
            "e.g. 'id_type.name' or 'phone_type'."
        ),
    )
    filter_operator = fields.Selection(
        selection=FILTER_OPERATOR_SELECTION,
        default="=",
        help="Operator used with Filter Path and Filter Value.",
    )
    filter_value = fields.Char(
        help="Expected value for the primary filter. Use comma-separated values for 'in' / 'not in'."
    )
    fallback_filter_path = fields.Char(
        help="Optional fallback filter path used only if the primary filter returns no records."
    )
    fallback_filter_operator = fields.Selection(
        selection=FILTER_OPERATOR_SELECTION,
        default="=",
        help="Operator used with the fallback filter.",
    )
    fallback_filter_value = fields.Char(
        help="Expected value for the fallback filter."
    )
    source_path_display = fields.Char(
        compute="_compute_path_display_fields",
        string="Source Path",
    )
    source_model_display = fields.Char(
        compute="_compute_path_display_fields",
        string="Source Model",
    )
    filter_path_display = fields.Char(
        compute="_compute_path_display_fields",
        string="Filter Path",
    )
    filter_model_display = fields.Char(
        compute="_compute_path_display_fields",
        string="Filter Model",
    )
    fallback_filter_path_display = fields.Char(
        compute="_compute_path_display_fields",
        string="Fallback Filter Path",
    )
    fallback_filter_model_display = fields.Char(
        compute="_compute_path_display_fields",
        string="Fallback Filter Model",
    )

    @api.depends(
        "source_path",
        "filter_path",
        "fallback_filter_path",
    )
    def _compute_path_display_fields(self):
        helper = self.env["g2p.consent.data.field"]
        for record in self:
            record.source_path_display = helper._get_path_display_label(
                record.source_path,
                purpose="source",
            )
            record.source_model_display = helper._get_path_root_label(
                purpose="source",
                source_path=record.source_path,
            )
            record.filter_path_display = helper._get_path_display_label(
                record.filter_path,
                purpose="filter",
                source_path=record.source_path,
            )
            record.filter_model_display = helper._get_path_root_label(
                purpose="filter",
                source_path=record.source_path,
            )
            record.fallback_filter_path_display = helper._get_path_display_label(
                record.fallback_filter_path,
                purpose="filter",
                source_path=record.source_path,
            )
            record.fallback_filter_model_display = helper._get_path_root_label(
                purpose="filter",
                source_path=record.source_path,
            )


class G2PConsentDataField(models.Model):
    _name = "g2p.consent.data.field"
    _description = "Consent Data Field"
    _rec_name = "name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    payload_key = fields.Char(
        help="Payload key for this data field. Defaults to the field code."
    )
    source_path = fields.Char(
        help=(
            "Optional simple source path from farmer (res.partner). "
            "If empty, the system tries to use code as path."
        ),
    )
    filter_path = fields.Char(
        help=(
            "Optional filter path evaluated on the first collection record in source path, "
            "e.g. 'id_type.name' or 'phone_type'."
        ),
    )
    filter_operator = fields.Selection(
        selection=FILTER_OPERATOR_SELECTION,
        default="=",
        help="Operator used with Filter Path and Filter Value.",
    )
    filter_value = fields.Char(
        help="Expected value for the primary filter. Use comma-separated values for 'in' / 'not in'."
    )
    fallback_filter_path = fields.Char(
        help="Optional fallback filter path used only if the primary filter returns no records."
    )
    fallback_filter_operator = fields.Selection(
        selection=FILTER_OPERATOR_SELECTION,
        default="=",
        help="Operator used with the fallback filter.",
    )
    fallback_filter_value = fields.Char(
        help="Expected value for the fallback filter."
    )
    mapping_line_ids = fields.One2many(
        "g2p.consent.data.field.map.line",
        "data_field_id",
        string="Advanced Mapping",
    )
    source_path_display = fields.Char(
        compute="_compute_path_display_fields",
        string="Source Path",
    )
    source_model_display = fields.Char(
        compute="_compute_path_display_fields",
        string="Source Model",
    )
    filter_path_display = fields.Char(
        compute="_compute_path_display_fields",
        string="Filter Path",
    )
    filter_model_display = fields.Char(
        compute="_compute_path_display_fields",
        string="Filter Model",
    )
    fallback_filter_path_display = fields.Char(
        compute="_compute_path_display_fields",
        string="Fallback Filter Path",
    )
    fallback_filter_model_display = fields.Char(
        compute="_compute_path_display_fields",
        string="Fallback Filter Model",
    )
    preview_partner_id = fields.Many2one(
        "res.partner",
        string="Sample Farmer",
        domain=[("is_registrant", "=", True), ("is_group", "=", False), ("state", "=", "approved")],
        help="Select one approved farmer to preview the payload produced by this data field.",
    )
    preview_payload = fields.Text(
        compute="_compute_preview_payload",
        string="Preview Payload",
        readonly=True,
    )

    _sql_constraints = [
        ("g2p_consent_data_field_code_uniq", "unique(code)", "Data field code must be unique."),
    ]

    @api.depends(
        "source_path",
        "filter_path",
        "fallback_filter_path",
    )
    def _compute_path_display_fields(self):
        for record in self:
            record.source_path_display = record._get_path_display_label(
                record.source_path,
                purpose="source",
            )
            record.source_model_display = record._get_path_root_label(
                purpose="source",
                source_path=record.source_path,
            )
            record.filter_path_display = record._get_path_display_label(
                record.filter_path,
                purpose="filter",
                source_path=record.source_path,
            )
            record.filter_model_display = record._get_path_root_label(
                purpose="filter",
                source_path=record.source_path,
            )
            record.fallback_filter_path_display = record._get_path_display_label(
                record.fallback_filter_path,
                purpose="filter",
                source_path=record.source_path,
            )
            record.fallback_filter_model_display = record._get_path_root_label(
                purpose="filter",
                source_path=record.source_path,
            )

    def _compute_preview_payload(self):
        for record in self:
            record.preview_payload = False

    @api.model
    def get_path_picker_options(
        self,
        purpose="source",
        source_path=None,
        model_name=None,
        technical_prefix=None,
        label_prefix=None,
    ):
        if model_name:
            root_model = model_name
            root_label = self._get_model_label(model_name)
            message = False
        else:
            root_info = self._get_picker_root_info(purpose=purpose, source_path=source_path)
            if not root_info["available"]:
                return root_info
            root_model = root_info["model_name"]
            root_label = root_info["root_label"]
            technical_prefix = root_info["technical_prefix"]
            label_prefix = root_info["label_prefix"]
            message = root_info.get("message")

        return {
            "available": True,
            "purpose": purpose,
            "root_label": root_label,
            "model_name": root_model,
            "technical_prefix": technical_prefix or "",
            "label_prefix": label_prefix or "",
            "message": message,
            "fields": self._get_picker_level_fields(
                model_name=root_model,
                technical_prefix=technical_prefix or "",
                label_prefix=label_prefix or "",
            ),
        }

    @api.model
    def get_path_selector_context(self, purpose="source", source_path=None):
        root_info = self._get_picker_root_info(purpose=purpose, source_path=source_path)
        return {
            "available": root_info["available"],
            "purpose": purpose,
            "model_name": root_info["model_name"],
            "root_label": root_info["root_label"],
            "message": root_info.get("message"),
        }

    @api.model
    def get_path_display_label(self, path, purpose="source", source_path=None):
        return self._get_path_display_label(path, purpose=purpose, source_path=source_path)

    @api.model
    def _get_path_root_label(self, purpose="source", source_path=None):
        root_info = self._get_picker_root_info(purpose=purpose, source_path=source_path)
        if not root_info.get("available"):
            return False
        return root_info.get("root_label") or False

    @api.model
    def preview_payload_from_values(self, values=None, preview_partner_id=None):
        values = values or {}
        if not preview_partner_id:
            raise UserError("Select a sample farmer before previewing the payload.")

        farmer = self.env["res.partner"].browse(preview_partner_id).exists()
        if not farmer:
            raise UserError("The selected sample farmer was not found.")

        data_field = self._build_preview_data_field(values)
        payload_key = (
            (values.get("payload_key") or values.get("code") or values.get("name") or "preview")
            .strip()
        )
        websub_config = self.env["g2p.datashare.config.websub"]
        value = websub_config._extract_data_field_value(data_field, farmer)
        payload = {}
        if payload_key and not websub_config._is_empty_payload_value(value):
            payload[payload_key] = value

        return {
            "payload": payload,
            "pretty_json": json.dumps(payload, indent=2, ensure_ascii=False),
        }

    def _build_preview_data_field(self, values):
        mapping_lines = []
        for line in values.get("mapping_lines", []):
            source_path = (line.get("source_path") or "").strip()
            payload_key = (line.get("payload_key") or "").strip()
            if not source_path and not payload_key:
                continue
            mapping_lines.append(
                (
                    0,
                    0,
                    {
                        "payload_key": payload_key,
                        "source_path": source_path,
                        "filter_path": (line.get("filter_path") or "").strip() or False,
                        "filter_operator": line.get("filter_operator") or "=",
                        "filter_value": (line.get("filter_value") or "").strip() or False,
                        "fallback_filter_path": (line.get("fallback_filter_path") or "").strip() or False,
                        "fallback_filter_operator": line.get("fallback_filter_operator") or "=",
                        "fallback_filter_value": (line.get("fallback_filter_value") or "").strip()
                        or False,
                    },
                )
            )

        return self.new(
            {
                "name": (values.get("name") or "").strip(),
                "code": (values.get("code") or "").strip(),
                "payload_key": (values.get("payload_key") or "").strip() or False,
                "source_path": (values.get("source_path") or "").strip() or False,
                "mapping_line_ids": mapping_lines,
            }
        )

    def _get_picker_root_info(self, purpose="source", source_path=None):
        if purpose == "filter":
            collection_info = self._get_collection_root_info("res.partner", source_path)
            if not collection_info:
                return {
                    "available": False,
                    "root_label": False,
                    "model_name": False,
                    "technical_prefix": "",
                    "label_prefix": "",
                    "message": (
                        "Select a source path that goes through multiple related records before "
                        "choosing a filter."
                    ),
                    "fields": [],
                }
            return {
                "available": True,
                "root_label": collection_info["root_label"],
                "model_name": collection_info["root_model_name"],
                "technical_prefix": "",
                "label_prefix": "",
                "message": (
                    f"Filtering applies within {collection_info['root_label']} records."
                ),
            }

        return {
            "available": True,
            "root_label": "Farmer",
            "model_name": "res.partner",
            "technical_prefix": "",
            "label_prefix": "",
            "message": "Choose fields from the farmer record and related records.",
        }

    def _get_picker_level_fields(self, model_name, technical_prefix="", label_prefix=""):
        model = self.env[model_name]
        depth = technical_prefix.count(".") + (1 if technical_prefix else 0)
        field_model = self.env["ir.model.fields"].sudo()
        field_records = field_model.search([("model", "=", model_name)], order="field_description, name")
        result = []
        for field_record in field_records:
            field = model._fields.get(field_record.name)
            if not self._is_picker_field_supported(field_record.name, field):
                continue

            field_label = field_record.field_description or field.string or field_record.name
            technical_path = self._join_path(technical_prefix, field_record.name)
            display_path = self._join_path(label_prefix, field_label, separator=" > ")
            can_expand = (
                field.type in PATH_PICKER_RELATIONAL_TYPES
                and depth < PATH_PICKER_MAX_DEPTH
                and bool(field.comodel_name)
            )
            result.append(
                {
                    "name": field_record.name,
                    "label": field_label,
                    "technical_path": technical_path,
                    "display_path": display_path,
                    "field_type": field.type,
                    "field_type_label": self._get_field_type_label(field.type),
                    "relation_model": field.comodel_name if field.type in PATH_PICKER_RELATIONAL_TYPES else False,
                    "can_select": True,
                    "can_expand": can_expand,
                }
            )
        return result

    def _get_path_display_label(self, path, purpose="source", source_path=None):
        path = (path or "").strip()
        if not path:
            return False

        if purpose == "filter":
            collection_info = self._get_collection_root_info("res.partner", source_path)
            if not collection_info:
                return path
            model_name = collection_info["root_model_name"]
        else:
            model_name = "res.partner"

        label_parts = []
        current_model = self.env[model_name]
        for segment in [segment.strip() for segment in path.split(".") if segment.strip()]:
            field = current_model._fields.get(segment)
            if not field:
                return path
            label_parts.append(field.string or segment)
            if field.type in PATH_PICKER_RELATIONAL_TYPES and field.comodel_name:
                current_model = self.env[field.comodel_name]
        return " > ".join(label_parts)

    def _get_collection_root_info(self, model_name, source_path):
        source_path = (source_path or "").strip()
        if not source_path:
            return None

        segments = [segment.strip() for segment in source_path.split(".") if segment.strip()]
        if not segments:
            return None

        current_model = self.env[model_name]
        root_segments = []
        root_labels = []
        for segment in segments:
            field = current_model._fields.get(segment)
            if not field:
                return None
            root_segments.append(segment)
            root_labels.append(field.string or segment)
            if field.type in ("one2many", "many2many"):
                return {
                    "root_segments": root_segments,
                    "root_model_name": field.comodel_name,
                    "root_label": " > ".join(root_labels),
                }
            if field.type == "many2one" and field.comodel_name:
                current_model = self.env[field.comodel_name]

        return None

    def _get_model_label(self, model_name):
        ir_model = self.env["ir.model"].sudo().search([("model", "=", model_name)], limit=1)
        if ir_model:
            return ir_model.name
        return model_name

    def _is_picker_field_supported(self, field_name, field):
        if not field:
            return False
        if field_name in PATH_PICKER_EXCLUDED_NAMES:
            return False
        is_image_field = field_name.startswith(PATH_PICKER_IMAGE_PREFIXES)
        if field_name.startswith(PATH_PICKER_EXCLUDED_PREFIXES):
            return False
        if field.type in PATH_PICKER_EXCLUDED_TYPES and not (field.type == "binary" and is_image_field):
            return False
        return True

    def _get_field_type_label(self, field_type):
        labels = {
            "char": "Text",
            "date": "Date",
            "datetime": "Date Time",
            "float": "Number",
            "integer": "Integer",
            "boolean": "Yes/No",
            "selection": "Choice",
            "many2one": "Related Record",
            "one2many": "Multiple Records",
            "many2many": "Multiple Records",
            "text": "Long Text",
            "json": "Structured Data",
        }
        return labels.get(field_type, field_type.replace("_", " ").title())

    def _join_path(self, prefix, part, separator="."):
        prefix = (prefix or "").strip()
        part = (part or "").strip()
        if not prefix:
            return part
        if not part:
            return prefix
        return f"{prefix}{separator}{part}"


class G2PDatashareConfigWebsubDataField(models.Model):
    _inherit = "g2p.datashare.config.websub"

    data_field_mode = fields.Selection(
        selection=[("dynamic", "Dynamic"), ("static", "Static")],
        string="Consent Data Field Mode",
        required=True,
        default="dynamic",
        help=(
            "Dynamic: publish only the data fields selected on the individual consent request. "
            "Static: publish all allowed data fields configured on the consent partner."
        ),
    )
    shared_data_field_ids = fields.Many2many(
        "g2p.consent.data.field",
        "g2p_datashare_config_data_field_rel",
        "config_id",
        "field_id",
        string="Shared Data Fields",
        help=(
            "Optional payload fields for INTERNAL WebSub publishers. "
            "If left empty, ATI falls back to the legacy hard-coded payload enrichment."
        ),
    )

    @api.model
    def _cleanup_old_consent_data_field_ui(self):
        xmlid_names = [
            "menu_g2p_consent_data_fields",
            "menu_g2p_consent_configuration_root",
            "action_g2p_consent_data_field",
            "view_g2p_consent_data_field_form",
            "view_g2p_consent_data_field_tree",
        ]
        model_data = self.env["ir.model.data"].sudo()
        for xmlid_name in xmlid_names:
            xmlid = model_data.search(
                [
                    ("module", "=", "g2p_ati_consent_mgt"),
                    ("name", "=", xmlid_name),
                ],
                limit=1,
            )
            if not xmlid:
                continue

            record = self.env[xmlid.model].sudo().browse(xmlid.res_id).exists()
            if record:
                _logger.info(
                    "ATI WebSub - Removing stale consent-owned data field UI xmlid=%s.%s model=%s res_id=%s",
                    xmlid.module,
                    xmlid.name,
                    xmlid.model,
                    xmlid.res_id,
                )
                record.unlink()
            xmlid.unlink()

    def _get_consent_shared_data_fields(self, consent_request):
        self.ensure_one()
        if self.data_field_mode == "static":
            return consent_request.partner_record_id.allowed_data_field_ids
        return consent_request.allowed_data_field_ids

    def _build_data_field_payload(self, farmer, data_fields):
        payload = {}
        for data_field in data_fields:
            payload_key = (data_field.payload_key or data_field.code or data_field.name or "").strip()
            if not payload_key:
                continue
            value = self._extract_data_field_value(data_field, farmer)
            if self._is_empty_payload_value(value):
                continue
            payload[payload_key] = value
        return payload

    def _extract_data_field_value(self, data_field, farmer):
        # Preserve the current one2many order so preview works with unsaved NewId rows.
        mapping_lines = data_field.mapping_line_ids
        if mapping_lines:
            collection_payload = self._extract_collection_mapping_payload(mapping_lines, farmer)
            if collection_payload is not None:
                return collection_payload

            payload = {}
            for line in mapping_lines:
                line_value = self._resolve_source_path(farmer, line.source_path, filter_holder=line)
                if self._is_empty_payload_value(line_value):
                    continue
                key = (line.payload_key or self._fallback_payload_key(line.source_path)).strip()
                if not key:
                    continue
                payload[key] = line_value
            return payload

        source_path = (data_field.source_path or data_field.code or "").strip()
        if not source_path:
            return None
        return self._resolve_source_path(farmer, source_path)

    def _extract_collection_mapping_payload(self, mapping_lines, farmer):
        root_path_infos = []
        for line in mapping_lines:
            info = self._get_collection_root_info(farmer._name, line.source_path)
            if not info:
                return None
            info["filter_signature"] = self._get_filter_signature(line)
            root_path_infos.append((line, info))

        root_paths = {tuple(info["root_segments"]) for _, info in root_path_infos}
        if len(root_paths) != 1:
            return None
        filter_signatures = {info["filter_signature"] for _, info in root_path_infos}
        if len(filter_signatures) != 1:
            return None

        root_segments = list(next(iter(root_paths)))
        root_filter_holder = root_path_infos[0][0]
        root_values = self._resolve_raw_path_values(farmer, root_segments, filter_holder=root_filter_holder)
        root_records = [value for value in root_values if isinstance(value, models.BaseModel)]
        if not root_records:
            return []

        rows = []
        for root_record in root_records:
            row = {}
            for line, info in root_path_infos:
                key = (line.payload_key or self._fallback_payload_key(line.source_path)).strip()
                if not key:
                    continue

                remaining_segments = info["remaining_segments"]
                if remaining_segments:
                    line_value = self._resolve_source_path(root_record, ".".join(remaining_segments))
                else:
                    line_value = self._serialize_payload_value(root_record)

                if self._is_empty_payload_value(line_value):
                    continue
                row[key] = line_value

            if row:
                rows.append(row)

        return rows

    def _get_collection_root_info(self, model_name, source_path):
        source_path = (source_path or "").strip()
        if not source_path:
            return None

        segments = [segment.strip() for segment in source_path.split(".") if segment.strip()]
        if not segments:
            return None

        current_model = self.env[model_name]
        root_segments = []
        for idx, segment in enumerate(segments):
            field = current_model._fields.get(segment)
            if not field:
                return None

            root_segments.append(segment)
            if field.type in ("one2many", "many2many"):
                return {
                    "root_segments": root_segments,
                    "remaining_segments": segments[idx + 1 :],
                }

            if field.type == "many2one":
                current_model = self.env[field.comodel_name]
                continue

            return None

        return None

    def _resolve_raw_path_values(self, source_record, segments, filter_holder=None):
        values = [source_record]
        filter_applied = False
        for segment in segments:
            next_values = []
            for value in values:
                if isinstance(value, models.BaseModel):
                    if not value or segment not in value._fields:
                        continue
                    field = value._fields[segment]
                    field_value = value[segment]
                    if field.type in ("one2many", "many2many"):
                        if filter_holder and not filter_applied:
                            field_value = self._apply_collection_filter(field_value, filter_holder)
                            filter_applied = True
                        if field_value:
                            next_values.extend(field_value)
                    elif field.type == "many2one":
                        if field_value:
                            next_values.append(field_value)
                    else:
                        next_values.append(field_value)
                elif isinstance(value, dict) and segment in value:
                    next_values.append(value.get(segment))

            values = next_values
            if not values:
                return []

        return values

    def _fallback_payload_key(self, source_path):
        if not source_path:
            return ""
        return source_path.split(".")[-1].strip()

    def _resolve_source_path(self, farmer, source_path, filter_holder=None):
        source_path = (source_path or "").strip()
        if not source_path:
            return None

        segments = [segment.strip() for segment in source_path.split(".") if segment.strip()]
        if not segments:
            return None

        values = [farmer]
        force_list = False
        filter_applied = False

        for segment in segments:
            next_values = []
            for value in values:
                if isinstance(value, models.BaseModel):
                    if not value or segment not in value._fields:
                        continue
                    field = value._fields[segment]
                    field_value = value[segment]
                    if field.type in ("one2many", "many2many"):
                        force_list = True
                        if filter_holder and not filter_applied:
                            field_value = self._apply_collection_filter(field_value, filter_holder)
                            filter_applied = True
                        if field_value:
                            next_values.extend(field_value)
                    elif field.type == "many2one":
                        if field_value:
                            next_values.append(field_value)
                    else:
                        next_values.append(field_value)
                elif isinstance(value, dict) and segment in value:
                    next_values.append(value.get(segment))
            values = next_values
            if not values:
                return [] if force_list else None

        serialized = []
        for value in values:
            serialized_value = self._serialize_payload_value(value)
            if self._is_empty_payload_value(serialized_value):
                continue
            serialized.append(serialized_value)

        if not serialized:
            return [] if force_list else None
        if force_list:
            return serialized
        if len(serialized) == 1:
            return serialized[0]
        return serialized

    def _apply_collection_filter(self, records, filter_holder):
        if not isinstance(records, models.BaseModel):
            return records

        filter_specs = self._get_filter_specs(filter_holder)
        if not filter_specs:
            return records

        for filter_spec in filter_specs:
            filtered_records = records.filtered(lambda rec: self._record_matches_filter(rec, filter_spec))
            if filtered_records:
                return filtered_records
        return records.browse()

    def _get_filter_specs(self, filter_holder):
        filter_specs = []
        primary_path = (getattr(filter_holder, "filter_path", "") or "").strip()
        if primary_path:
            filter_specs.append(
                {
                    "path": primary_path,
                    "operator": getattr(filter_holder, "filter_operator", "=") or "=",
                    "value": getattr(filter_holder, "filter_value", ""),
                }
            )

        fallback_path = (getattr(filter_holder, "fallback_filter_path", "") or "").strip()
        if fallback_path:
            filter_specs.append(
                {
                    "path": fallback_path,
                    "operator": getattr(filter_holder, "fallback_filter_operator", "=") or "=",
                    "value": getattr(filter_holder, "fallback_filter_value", ""),
                }
            )
        return filter_specs

    def _get_filter_signature(self, filter_holder):
        return tuple(
            (spec["path"], spec["operator"], spec["value"] or "")
            for spec in self._get_filter_specs(filter_holder)
        )

    def _record_matches_filter(self, record, filter_spec):
        actual_value = self._resolve_source_path(record, filter_spec["path"])
        operator = filter_spec["operator"]
        expected_values = self._parse_filter_values(filter_spec["value"], operator)
        actual_values = self._flatten_filter_values(actual_value)

        if operator == "ilike":
            return any(
                expected.lower() in actual.lower()
                for actual in actual_values
                for expected in expected_values
                if actual and expected
            )

        matched = any(actual == expected for actual in actual_values for expected in expected_values)
        if operator in ("!=", "not in"):
            return not matched
        return matched

    def _parse_filter_values(self, raw_value, operator):
        raw_value = "" if raw_value is None else str(raw_value)
        if operator in ("in", "not in"):
            return [item.strip() for item in raw_value.split(",") if item.strip()]
        return [raw_value.strip()]

    def _flatten_filter_values(self, value):
        if value is None:
            return []
        if isinstance(value, dict):
            preferred_keys = [key for key in ("value", "code", "name", "id") if key in value]
            if preferred_keys:
                return [self._normalize_filter_scalar(value[key]) for key in preferred_keys]
            return [self._normalize_filter_scalar(value)]
        if isinstance(value, (list, tuple, set)):
            flattened = []
            for item in value:
                flattened.extend(self._flatten_filter_values(item))
            return flattened
        return [self._normalize_filter_scalar(value)]

    def _normalize_filter_scalar(self, value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, datetime):
            return fields.Datetime.to_string(value)
        if isinstance(value, date):
            return fields.Date.to_string(value)
        return str(value).strip()

    def _serialize_payload_value(self, value):
        if isinstance(value, models.BaseModel):
            if len(value) > 1:
                return [self._serialize_payload_value(rec) for rec in value]
            if not value:
                return None
            record = value[0]
            payload = {
                "id": record.id,
                "name": record.display_name,
            }
            if "code" in record._fields and record.code:
                payload["code"] = record.code
            return payload
        if isinstance(value, datetime):
            return fields.Datetime.to_string(value)
        if isinstance(value, date):
            return fields.Date.to_string(value)
        if isinstance(value, dict):
            return {k: self._serialize_payload_value(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._serialize_payload_value(v) for v in value]
        return value

    def _is_empty_payload_value(self, value):
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) == 0
        return False
