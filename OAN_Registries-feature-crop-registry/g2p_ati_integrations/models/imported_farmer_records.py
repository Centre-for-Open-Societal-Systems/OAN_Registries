import ast
import json
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ImportedRecordSource(models.Model):
    _name = 'g2p.imported.record.source'
    _description = 'Imported Record Source'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    color = fields.Integer('Color Index', default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Source name already exists!"),
    ]

    @staticmethod
    def _extract_db_from_name(name):
        if not name:
            return None
        if not isinstance(name, str):
            name = str(name)
        stripped = name.strip()
        # print("[source_db] raw name:", name)
        if (
            len(stripped) >= 2
            and stripped[0] == stripped[-1]
            and stripped[0] in ("'", '"')
        ):
            stripped = stripped[1:-1].strip()
        # print("[source_db] stripped name:", stripped)
        if not stripped or not (stripped.startswith("{") or stripped.startswith("[")):
            return None
        parsed = None
        try:
            parsed = json.loads(stripped)
        except (TypeError, json.JSONDecodeError):
            try:
                parsed = ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                match = re.search(r"(?:'db'|\"db\")\s*:\s*(?:'([^']+)'|\"([^\"]+)\")", stripped)
                if match:
                    # print("[source_db] regex match:", match.group(1) or match.group(2))
                    return match.group(1) or match.group(2)
                return None
        if isinstance(parsed, dict):
            # print("[source_db] parsed dict db:", parsed.get("db"))
            return parsed.get("db")
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict) and item.get("db"):
                    # print("[source_db] parsed list dict db:", item.get("db"))
                    return item.get("db")
                if isinstance(item, str):
                    nested = ImportedRecordSource._extract_db_from_name(item)
                    if nested:
                        # print("[source_db] parsed list nested db:", nested)
                        return nested
        return None

    def name_get(self):
        result = []
        for rec in self:
            db_name = self._extract_db_from_name(rec.name)
            # print("[source_db] name_get:", rec.id, rec.name, "=>", db_name)
            result.append((rec.id, db_name or rec.name))
        return result


class G2PImportedRecord(models.Model):
    _name = "g2p.imported.record"
    _description = "Imported Record"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char()
    given_name = fields.Char(string="First Name")
    family_name = fields.Char(string="Father's Name")
    gf_name_eng = fields.Char(string="Grand Father's Name")
    phone = fields.Char(required=True)
    gender = fields.Char()
    region = fields.Char()
    state = fields.Selection(selection=[("draft", "Draft"), ("moved", "Created")], default="draft")
    language = fields.Char()
    record_from = fields.Char()
    record_type = fields.Selection(selection=[("single", "Single Source"), ("composed", "Composed")])
    db_import = fields.Boolean("Imported", default=False)
    zone = fields.Char(string="Zone")
    woreda = fields.Char(string="Woreda")
    kebele = fields.Char(string="Kebele")
    source = fields.Json(string="Source Information", help="Stores the source information in JSON format")
    draft_record_ids = fields.One2many(
        "draft.record",
        "import_record_id",
        string="Draft Records",
        readonly=True,
    )
    draft_creator_id = fields.Many2one(
        "res.users",
        string="Draft Creator",
        compute="_compute_draft_creator",
        store=True,
        readonly=True,
    )
    draft_status = fields.Selection(
        selection=[
            ("draft_created", "Draft Created"),
            ("no_draft", "No Draft"),
        ],
        compute="_compute_draft_status",
        store=True,
        readonly=True,
    )
    source_db_ids = fields.Many2many(
        "g2p.imported.record.source",
        "g2p_imported_record_source_rel",
        "imported_record_id",
        "source_id",
        string="Source DBs",
        compute="_compute_source_db_ids",
        store=True,
        readonly=True,
    )

    assigned_region = fields.Many2many(
        "g2p.region", string="Regions Assigned"
    )
    assigned_languages = fields.Many2many(
        "g2p.lang", string="Language Assigned"
    )

    _sql_constraints = [
        ("phone_unique", "unique(phone)", "The phone number must be unique."),
    ]

    @staticmethod
    def _compose_name(given_name=None, family_name=None, gf_name_eng=None, phone=None):
        name_parts = []
        if given_name:
            name_parts.append(given_name)
        if family_name:
            name_parts.append(family_name)
        if gf_name_eng:
            name_parts.append(gf_name_eng)
        if name_parts:
            return " ".join(name_parts).upper()
        return phone or None

    @api.onchange("family_name", "given_name", "gf_name_eng", "phone")
    def name_change_farmer(self):
        self.name = self._compose_name(
            given_name=self.given_name,
            family_name=self.family_name,
            gf_name_eng=self.gf_name_eng,
            phone=self.phone,
        )


    @api.constrains("assigned_region", "assigned_languages")
    def _check_region_languages(self):
        for record in self:
            if record.assigned_region and not record.assigned_languages:
                raise ValidationError(_("Please specify at least one language when a region is assigned."))
            if record.assigned_languages and not record.assigned_region:
                raise ValidationError(_("Please specify a region when languages are assigned."))

    @api.depends("draft_record_ids")
    def _compute_draft_status(self):
        for record in self:
            record.draft_status = "draft_created" if record.draft_record_ids else "no_draft"

    @api.depends("draft_record_ids.create_uid", "draft_record_ids.create_date")
    def _compute_draft_creator(self):
        for record in self:
            if not record.draft_record_ids:
                record.draft_creator_id = False
                continue
            latest_draft = record.draft_record_ids.sorted(
                key=lambda r: r.create_date or r.id
            )[-1]
            record.draft_creator_id = latest_draft.create_uid

    @staticmethod
    def _normalize_source_name(name):
        if name is None:
            return None
        if not isinstance(name, str):
            name = str(name)
        name = name.strip()
        return name or None

    @classmethod
    def _extract_db_from_dict(cls, data):
        if not isinstance(data, dict):
            return None
        for key in ("db", "db_name", "source_db", "database", "dbname"):
            value = data.get(key)
            normalized = cls._normalize_source_name(value)
            if normalized:
                return normalized
        # Fallback to "source" if no db key is present
        value = data.get("source")
        return cls._normalize_source_name(value)

    def _extract_source_names(self, source_data):
        if not source_data:
            return []

        # print("[source_db] source_data:", source_data)
        if isinstance(source_data, str):
            try:
                source_data = json.loads(source_data)
            except (TypeError, json.JSONDecodeError):
                return []

        names = []

        def add_name(value):
            if isinstance(value, str):
                stripped = value.strip()
                if stripped and (stripped.startswith("{") or stripped.startswith("[")):
                    try:
                        parsed = json.loads(stripped)
                        add_name(parsed)
                        return
                    except (TypeError, json.JSONDecodeError):
                        try:
                            parsed = ast.literal_eval(stripped)
                            add_name(parsed)
                            return
                        except (ValueError, SyntaxError):
                            pass
            if isinstance(value, dict):
                extracted = self._extract_db_from_dict(value)
                if extracted:
                    # print("[source_db] extracted from dict:", extracted)
                    names.append(extracted)
                    return
            if isinstance(value, list):
                for item in value:
                    add_name(item)
                return

            normalized = self._normalize_source_name(value)
            if normalized:
                # print("[source_db] normalized name:", normalized)
                names.append(normalized)

        if isinstance(source_data, dict):
            extracted = self._extract_db_from_dict(source_data)
            if extracted:
                add_name(extracted)
            else:
                for key in source_data.keys():
                    add_name(key)
        elif isinstance(source_data, list):
            for item in source_data:
                if isinstance(item, dict):
                    extracted = self._extract_db_from_dict(item)
                    if extracted:
                        add_name(extracted)
                    elif len(item) == 1:
                        add_name(next(iter(item.keys())))
                else:
                    add_name(item)
        else:
            add_name(source_data)

        cleaned = []
        seen = set()
        for name in names:
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(name)
        # print("[source_db] cleaned names:", cleaned)
        return cleaned

    @api.depends("source")
    def _compute_source_db_ids(self):
        Source = self.env["g2p.imported.record.source"].sudo()
        all_names = []
        per_record_names = {}

        for record in self:
            names = record._extract_source_names(record.source)
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

    def _ensure_source_db_ids(self):
        if not self:
            return
        self.with_context(skip_source_db_ensure=True)._compute_source_db_ids()
        self.flush_recordset(["source_db_ids"])

    def read(self, fields=None, load="_classic_read"):
        if not self.env.context.get("skip_source_db_ensure"):
            if not fields or "source_db_ids" in fields or "source" in fields:
                self._ensure_source_db_ids()
        return super().read(fields=fields, load=load)

    @api.model
    def create(self, vals):
        if not vals.get("name"):
            vals["name"] = self._compose_name(
                given_name=vals.get("given_name"),
                family_name=vals.get("family_name"),
                gf_name_eng=vals.get("gf_name_eng"),
                phone=vals.get("phone"),
            )
        return super().create(vals)

    def write(self, vals):
        if "name" not in vals and any(
            key in vals for key in ("given_name", "family_name", "gf_name_eng", "phone")
        ):
            for record in self:
                updated_name = self._compose_name(
                    given_name=vals.get("given_name", record.given_name),
                    family_name=vals.get("family_name", record.family_name),
                    gf_name_eng=vals.get("gf_name_eng", record.gf_name_eng),
                    phone=vals.get("phone", record.phone),
                )
                if not updated_name:
                    continue
                if not record.name or record.name == record.phone:
                    super(G2PImportedRecord, record).write({**vals, "name": updated_name})
                else:
                    super(G2PImportedRecord, record).write(vals)
            return True
        return super().write(vals)

    def action_view_draft_records(self):
        return {
            "name": "Draft Records",
            "type": "ir.actions.act_window",
            "res_model": "draft.record",
            "view_mode": "kanban,form",
            "domain": [("import_record_id", "=", self.id)],
            "context": dict(self.env.context, default_import_record_id=self.id),
        }


    def action_to_draft(self):
        
        for record in self:
            associated_records = self.env["draft.record"].sudo().search([
                ("import_record_id", "=", record.id)
            ])

            # Check for published records
            if any(rec.state == "published" for rec in associated_records):
                raise ValidationError(
                    _("Cannot set to draft. There are associated records that are already published.")
                )

            # Only non-admin users are restricted by create_uid
            if not self.env.user.has_group("g2p_draft_publish.group_int_admin"):
                unauthorized_records = associated_records.filtered(
                    lambda rec: rec.create_uid.id != self.env.uid
                )
                if unauthorized_records:
                    raise ValidationError(
                        _("You cannot remove associated records that were not created by you.")
                    )

            # Admins or allowed users can delete the records
            associated_records.unlink()
            record.write({"state": "draft"})




    def action_move(self):
        self.write({"state": "moved"})

    def create_draft_imported_record(self):
        self.ensure_one()

        started = self.env["g2p.validation.status"].sudo().search([("name", "=", "Started")])
        partner_data = {
            "given_name": self.given_name,
            "family_name": self.family_name,
            "addl_name": self.gf_name_eng,
            "gf_name_eng": self.gf_name_eng,
            "phone": self.phone,
            "gender": self.gender,
            "region": self.region,
        }

        data = {
            "name": self.name,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "addl_name": self.gf_name_eng,
            "gf_name_eng": self.gf_name_eng,

            "phone": self.phone,
            "gender": self.gender,
            "region": self.region,
            "import_record_id": self.id,
            "validation_status": started.id,
            "partner_data": json.dumps(partner_data),
        }

        new_record = self.env["draft.record"].sudo().create(data)
        new_record.sudo().write({"message_partner_ids": [(6, 0, self.message_partner_ids.ids)]})

        self.write({"state": "moved"})

        return {
            "name": "Draft Records",
            "type": "ir.actions.act_window",
            "res_model": "draft.record",
            "view_mode": "kanban,form,tree",
            "domain": [("import_record_id", "=", self.id)],
            "context": dict(self.env.context, default_import_record_id=self.id),
        }

    def assign_records(self):
        return {
            "name": "Draft Records",
            "type": "ir.actions.act_window",
            "res_model": "assign.records.wizard",
            "view_mode": "form",
            "target": "new",
        }
