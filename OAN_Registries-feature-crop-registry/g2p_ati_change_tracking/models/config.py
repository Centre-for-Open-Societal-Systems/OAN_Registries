import copy
from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import OrderedSet

FIELDS_BLACKLIST = [
    "id",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
    "display_name",
    "__last_update",
]
EMPTY_DICT = {}


class DictDiffer:
    def __init__(self, current_dict, past_dict):
        self.current_dict, self.past_dict = current_dict, past_dict
        self.set_current = set(current_dict)
        self.set_past = set(past_dict)
        self.intersect = self.set_current.intersection(self.set_past)

    def added(self):
        return self.set_current - self.intersect

    def removed(self):
        return self.set_past - self.intersect

    def changed(self):
        return {o for o in self.intersect if self.past_dict[o] != self.current_dict[o]}

    def unchanged(self):
        return {o for o in self.intersect if self.past_dict[o] == self.current_dict[o]}


class ThrowAwayCache:
    def __init__(self, env):
        self._transaction = env.transaction

    def __enter__(self):
        self._original_cache = self._transaction.cache
        self._original_tocompute = defaultdict(OrderedSet)
        for key, value in self._transaction.tocompute.items():
            self._original_tocompute[key] = OrderedSet(value)
        temporary_cache = api.Cache()
        for env in self._transaction.envs:
            env.cache = temporary_cache
        self._transaction.cache = temporary_cache
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for env in self._transaction.envs:
            env.cache = self._original_cache
        self._transaction.cache = self._original_cache
        self._transaction.tocompute = self._original_tocompute


class G2PChangeLogRule(models.Model):
    _name = "g2p.change.log.rule"
    _description = "Change Log Rule"
    _order = "model_model"

    name = fields.Char(required=True)
    model_id = fields.Many2one(
        "ir.model",
        "Model",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_name = fields.Char(readonly=True)
    model_model = fields.Char(string="Technical Model Name", readonly=True)
    log_read = fields.Boolean("Log Reads")
    log_write = fields.Boolean("Log Writes", default=True)
    log_unlink = fields.Boolean("Log Deletes", default=True)
    log_create = fields.Boolean("Log Creates", default=True)
    log_type = fields.Selection(
        [("full", "Full log"), ("fast", "Fast log")],
        string="Type",
        required=True,
        default="full",
    )
    capture_record = fields.Boolean(help="Log record snapshot on unlink (full only)")
    users_to_exclude_ids = fields.Many2many(
        "res.users",
        string="Users to Exclude",
        context={"active_test": False},
    )
    fields_to_exclude_ids = fields.Many2many(
        "ir.model.fields",
        domain="[('model_id', '=', model_id)]",
        string="Fields to Exclude",
    )

    _sql_constraints = [
        ("model_uniq", "unique(model_id)", "A rule already exists for this model."),
    ]

    def _register_hook(self):
        super()._register_hook()
        if not hasattr(self.pool, "_g2p_chlog_field_cache"):
            self.pool._g2p_chlog_field_cache = {}
        if not hasattr(self.pool, "_g2p_chlog_model_cache"):
            self.pool._g2p_chlog_model_cache = {}
        rules = self.search([]) if not self else self
        updated = rules._patch_methods()
        if updated:
            self._update_registry()
        return updated

    def _patch_method(self, model, method_name, check_attr):
        result = new_method = False
        model_class = type(model)
        if method_name == "create":
            new_method = self._make_create()
        elif method_name == "read":
            new_method = self._make_read()
        elif method_name == "write":
            new_method = self._make_write()
        elif method_name == "unlink":
            new_method = self._make_unlink()
        if new_method:
            new_method.origin = getattr(model_class, method_name)
            setattr(model_class, method_name, new_method)
            setattr(type(model), check_attr, True)
            result = True
        return result

    def _patch_methods(self):
        updated = False
        model_cache = self.pool._g2p_chlog_model_cache
        for rule in self:
            model_name = rule.model_id.model or rule.model_model
            if not self.pool.get(model_name):
                continue
            model_cache[model_name] = rule.model_id.id
            model_model = self.env[model_name]
            if rule.log_create and not hasattr(model_model, "g2p_chlog_ruled_create"):
                updated = rule._patch_method(model_model, "create", "g2p_chlog_ruled_create") or updated
            if rule.log_read and not hasattr(model_model, "g2p_chlog_ruled_read"):
                updated = rule._patch_method(model_model, "read", "g2p_chlog_ruled_read") or updated
            if rule.log_write and not hasattr(model_model, "g2p_chlog_ruled_write"):
                updated = rule._patch_method(model_model, "write", "g2p_chlog_ruled_write") or updated
            if rule.log_unlink and not hasattr(model_model, "g2p_chlog_ruled_unlink"):
                updated = rule._patch_method(model_model, "unlink", "g2p_chlog_ruled_unlink") or updated
        return updated

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "model_id" not in vals or not vals["model_id"]:
                raise UserError(_("No model defined to create line."))
            if self.sudo().search([("model_id", "=", vals["model_id"])]):
                raise UserError(_("A rule already exists for this model."))
            model = self.env["ir.model"].sudo().browse(vals["model_id"])
            vals.update({"model_name": model.name, "model_model": model.model})
        records = super().create(vals_list)
        records._register_hook()
        return records

    def write(self, vals):
        if "model_id" in vals:
            if not vals["model_id"]:
                raise UserError(_("Field 'model_id' cannot be empty."))
            existing = self.sudo().search([("model_id", "=", vals["model_id"]), ("id", "not in", self.ids)])
            if existing:
                raise UserError(_("A rule already exists for this model."))
            model = self.env["ir.model"].sudo().browse(vals["model_id"])
            vals.update({"model_name": model.name, "model_model": model.model})
        res = super().write(vals)
        self._register_hook()
        return res

    def unlink(self):
        self._revert_methods()
        res = super().unlink()
        self._update_registry()
        return res

    def _revert_methods(self):
        updated = False
        for rule in self:
            model_model = self.env[rule.model_id.model or rule.model_model]
            for method in ["create", "read", "write", "unlink"]:
                attr = f"g2p_chlog_ruled_{method}"
                if hasattr(getattr(model_model, method), "origin"):
                    setattr(type(model_model), method, getattr(model_model, method).origin)
                    if hasattr(type(model_model), attr):
                        delattr(type(model_model), attr)
                    updated = True
        return updated

    @api.model
    def get_fields_to_log(self, model):
        return list(
            n
            for n, f in model._fields.items()
            if (not f.compute and not f.related) or f.store
        )

    def _make_create(self):
        self.ensure_one()
        log_type = self.log_type
        users_to_exclude = self.mapped("users_to_exclude_ids")

        @api.model_create_multi
        @api.returns("self", lambda value: value.id)
        def create_full(self, vals_list, **kwargs):
            self = self.with_context(auditlog_disabled=True)
            rule_model = self.env["g2p.change.log.rule"]
            vals_list = rule_model._update_vals_list(vals_list)
            vals_list2 = copy.deepcopy(vals_list)
            new_records = create_full.origin(self, vals_list, **kwargs)

            if self.env.user in users_to_exclude:
                return new_records

            fields_list = rule_model.get_fields_to_log(self)
            new_values = {}
            with ThrowAwayCache(self.env):
                for new_record in new_records.sudo():
                    new_values.setdefault(new_record.id, {})
                    for fname, field in new_record._fields.items():
                        if fname not in fields_list:
                            continue
                        new_values[new_record.id][fname] = field.convert_to_read(
                            new_record[fname], new_record
                        )

            rule_model.sudo().create_logs(
                self.env.uid,
                self._name,
                new_records.ids,
                "create",
                None,
                new_values,
                {"log_type": log_type},
            )
            return new_records

        @api.model_create_multi
        @api.returns("self", lambda value: value.id)
        def create_fast(self, vals_list, **kwargs):
            self = self.with_context(auditlog_disabled=True)
            rule_model = self.env["g2p.change.log.rule"]
            vals_list = rule_model._update_vals_list(vals_list)
            vals_list2 = copy.deepcopy(vals_list)
            new_records = create_fast.origin(self, vals_list, **kwargs)
            if self.env.user in users_to_exclude:
                return new_records
            new_values = {}
            for vals, new_record in zip(vals_list2, new_records, strict=True):
                new_values.setdefault(new_record.id, vals)
            rule_model.sudo().create_logs(
                self.env.uid,
                self._name,
                new_records.ids,
                "create",
                None,
                new_values,
                {"log_type": log_type},
            )
            return new_records

        return create_full if self.log_type == "full" else create_fast

    def _make_read(self):
        self.ensure_one()
        log_type = self.log_type
        users_to_exclude = self.mapped("users_to_exclude_ids")

        def read(self, fields=None, load="_classic_read", **kwargs):
            result = read.origin(self, fields, load, **kwargs)
            result2 = result if isinstance(result, list) else [result]
            read_values = {d["id"]: d for d in result2 if isinstance(d, dict) and "id" in d}
            if self.env.context.get("auditlog_disabled"):
                return result
            self = self.with_context(auditlog_disabled=True)
            rule_model = self.env["g2p.change.log.rule"]
            if self.env.user in users_to_exclude:
                return result
            rule_model.sudo().create_logs(
                self.env.uid,
                self._name,
                list(read_values.keys()),
                "read",
                read_values,
                None,
                {"log_type": log_type},
            )
            return result

        return read

    def _make_write(self):
        self.ensure_one()
        log_type = self.log_type
        users_to_exclude = self.mapped("users_to_exclude_ids")

        def write_full(self, vals, **kwargs):
            self = self.with_context(auditlog_disabled=True)
            rule_model = self.env["g2p.change.log.rule"]
            fields_list = rule_model.get_fields_to_log(self)
            records_write = (
                self.filtered(lambda r: not isinstance(r.id, models.NewId))
                .sudo()
                .with_context(prefetch_fields=False)
            )
            if not records_write:
                return write_full.origin(self, vals, **kwargs)

            with ThrowAwayCache(self.env):
                old_values = {d["id"]: d for d in records_write.read(fields_list)}

            result = write_full.origin(self, vals, **kwargs)
            self.flush_recordset()
            if self.env.user in users_to_exclude:
                return result

            with ThrowAwayCache(self.env):
                new_values = {d["id"]: d for d in records_write.read(fields_list)}

            rule_model.sudo().create_logs(
                self.env.uid,
                self._name,
                records_write.ids,
                "write",
                old_values,
                new_values,
                {"log_type": log_type},
            )
            return result

        def write_fast(self, vals, **kwargs):
            self = self.with_context(auditlog_disabled=True)
            rule_model = self.env["g2p.change.log.rule"]
            vals2 = dict(vals)
            old_vals2 = dict.fromkeys(list(vals2.keys()), False)
            old_values = {id_: old_vals2 for id_ in self.ids}
            new_values = {id_: vals2 for id_ in self.ids}
            result = write_fast.origin(self, vals, **kwargs)
            if self.env.user in users_to_exclude:
                return result
            rule_model.sudo().create_logs(
                self.env.uid,
                self._name,
                self.ids,
                "write",
                old_values,
                new_values,
                {"log_type": log_type},
            )
            return result

        return write_full if self.log_type == "full" else write_fast

    def _make_unlink(self):
        self.ensure_one()
        log_type = self.log_type
        users_to_exclude = self.mapped("users_to_exclude_ids")

        def unlink_full(self, **kwargs):
            self = self.with_context(auditlog_disabled=True)
            rule_model = self.env["g2p.change.log.rule"]
            fields_list = rule_model.get_fields_to_log(self)
            old_values = {
                d["id"]: d
                for d in self.sudo()
                .with_context(prefetch_fields=False)
                .read(fields_list)
            }
            if self.env.user in users_to_exclude:
                return unlink_full.origin(self, **kwargs)
            rule_model.sudo().create_logs(
                self.env.uid,
                self._name,
                self.ids,
                "unlink",
                old_values,
                None,
                {"log_type": log_type},
            )
            return unlink_full.origin(self, **kwargs)

        def unlink_fast(self, **kwargs):
            self = self.with_context(auditlog_disabled=True)
            rule_model = self.env["g2p.change.log.rule"]
            if self.env.user in users_to_exclude:
                return unlink_fast.origin(self, **kwargs)
            rule_model.sudo().create_logs(
                self.env.uid,
                self._name,
                self.ids,
                "unlink",
                None,
                None,
                {"log_type": log_type},
            )
            return unlink_fast.origin(self, **kwargs)

        return unlink_full if self.log_type == "full" else unlink_fast

    def create_logs(
        self,
        uid,
        res_model,
        res_ids,
        method,
        old_values=None,
        new_values=None,
        additional_log_values=None,
    ):
        if old_values is None:
            old_values = EMPTY_DICT
        if new_values is None:
            new_values = EMPTY_DICT
        log_model = self.env["g2p.change.log"]
        model_model = self.env[res_model]
        model_id = self.pool._g2p_chlog_model_cache.get(res_model)
        if not model_id:
            return
        rule = self.env["g2p.change.log.rule"].search([("model_id", "=", model_id)], limit=1)
        fields_to_exclude = rule.fields_to_exclude_ids.mapped("name") if rule else []
        for res_id in res_ids:
            res = model_model.browse(res_id)
            vals = {
                "name": res.display_name,
                "model_id": model_id,
                "res_id": res_id,
                "method": method,
                "user_id": uid,
            }
            vals.update(additional_log_values or {})
            diff = DictDiffer(
                new_values.get(res_id, EMPTY_DICT), old_values.get(res_id, EMPTY_DICT)
            )
            if method == "create":
                vals["line_ids"] = self._create_log_line_on_create(
                    vals, diff.added(), new_values, fields_to_exclude
                )
            elif method == "read":
                vals["line_ids"] = self._create_log_line_on_read(
                    vals,
                    list(old_values.get(res_id, EMPTY_DICT).keys()),
                    old_values,
                    fields_to_exclude,
                )
            elif method == "write":
                vals["line_ids"] = self._create_log_line_on_write(
                    vals, diff.changed(), old_values, new_values, fields_to_exclude
                )
            elif method == "unlink" and rule and rule.capture_record:
                vals["line_ids"] = self._create_log_line_on_read(
                    vals,
                    list(old_values.get(res_id, EMPTY_DICT).keys()),
                    old_values,
                    fields_to_exclude,
                )
            if method == "unlink" or vals.get("line_ids"):
                log_model.sudo().create(vals)

    def _get_field(self, model_id, field_name):
        model = self.env["ir.model"].sudo().browse(model_id)
        cache = self.pool._g2p_chlog_field_cache
        if field_name not in cache.get(model.model, {}):
            cache.setdefault(model.model, {})
            field_model = self.env["ir.model.fields"].sudo()
            all_model_ids = [model.id]
            all_model_ids.extend(model.inherited_model_ids.ids)
            field = field_model.search(
                [("model_id", "in", all_model_ids), ("name", "=", field_name)]
            )
            if not field:
                cache[model.model][field_name] = False
            else:
                field_data = field.read(load="_classic_write")[0]
                cache[model.model][field_name] = field_data
        return cache[model.model][field_name]

    def _create_log_line_on_read(
        self, log_vals, fields_list, read_values, fields_to_exclude
    ):
        fields_to_exclude = fields_to_exclude + FIELDS_BLACKLIST
        line_vals = []
        for field_name in fields_list:
            if field_name in fields_to_exclude:
                continue
            field = self._get_field(log_vals["model_id"], field_name)
            if field:
                line_vals.append(
                    Command.create(
                        self._prepare_log_line_vals_on_read(
                            log_vals, field, read_values
                        )
                    )
                )
        return line_vals

    def _prepare_log_line_vals_on_read(self, log_vals, field, read_values):
        vals = {
            "field_id": field["id"],
            "old_value": read_values[log_vals["res_id"]][field["name"]],
            "old_value_text": read_values[log_vals["res_id"]][field["name"]],
            "new_value": False,
            "new_value_text": False,
        }
        if field["relation"] and "2many" in field["ttype"]:
            vals["old_value_text"] = [
                (x.id, x.display_name)
                for x in self.env[field["relation"]].browse(vals["old_value"])
            ]
        return vals

    def _create_log_line_on_write(
        self, log_vals, fields_list, old_values, new_values, fields_to_exclude
    ):
        fields_to_exclude = fields_to_exclude + FIELDS_BLACKLIST
        line_vals = []
        for field_name in fields_list:
            if field_name in fields_to_exclude:
                continue
            field = self._get_field(log_vals["model_id"], field_name)
            if field:
                line_vals.append(
                    Command.create(
                        self._prepare_log_line_vals_on_write(
                            log_vals, field, old_values, new_values
                        )
                    )
                )
        return line_vals

    def _prepare_log_line_vals_on_write(self, log_vals, field, old_values, new_values):
        vals = {
            "field_id": field["id"],
            "old_value": old_values[log_vals["res_id"]][field["name"]],
            "old_value_text": old_values[log_vals["res_id"]][field["name"]],
            "new_value": new_values[log_vals["res_id"]][field["name"]],
            "new_value_text": new_values[log_vals["res_id"]][field["name"]],
        }
        if (
            log_vals.get("log_type") == "full"
            and field["relation"]
            and "2many" in field["ttype"]
        ):
            existing_ids = self.env[field["relation"]]._search(
                [("id", "in", vals["old_value"])]
            )
            old_value_text = []
            if existing_ids:
                old_value_text = [
                    (x.id, x.display_name)
                    for x in self.env[field["relation"]].browse(existing_ids)
                ]
            deleted_ids = set(vals["old_value"]) - set(existing_ids)
            for deleted_id in deleted_ids:
                old_value_text.append((deleted_id, "DELETED"))
            vals["old_value_text"] = old_value_text
            vals["new_value_text"] = [
                (x.id, x.display_name)
                for x in self.env[field["relation"]].browse(vals["new_value"])
            ]
        return vals

    def _create_log_line_on_create(
        self, log_vals, fields_list, new_values, fields_to_exclude
    ):
        fields_to_exclude = fields_to_exclude + FIELDS_BLACKLIST
        line_vals = []
        for field_name in fields_list:
            if field_name in fields_to_exclude:
                continue
            field = self._get_field(log_vals["model_id"], field_name)
            if field:
                line_vals.append(
                    Command.create(
                        self._prepare_log_line_vals_on_create(
                            log_vals, field, new_values
                        )
                    )
                )
        return line_vals

    def _prepare_log_line_vals_on_create(self, log_vals, field, new_values):
        vals = {
            "field_id": field["id"],
            "old_value": False,
            "old_value_text": False,
            "new_value": new_values[log_vals["res_id"]][field["name"]],
            "new_value_text": new_values[log_vals["res_id"]][field["name"]],
        }
        if (
            log_vals.get("log_type") == "full"
            and field["relation"]
            and "2many" in field["ttype"]
        ):
            vals["new_value_text"] = [
                (x.id, x.display_name)
                for x in self.env[field["relation"]].browse(vals["new_value"])
            ]
        return vals

    @api.model
    def _update_vals_list(self, vals_list):
        for vals in vals_list:
            for fieldname, fieldvalue in vals.items():
                if isinstance(fieldvalue, models.BaseModel) and not fieldvalue:
                    vals[fieldname] = False
        return vals_list

    def _update_registry(self):
        if self.env.registry.ready and not self.env.context.get("import_file"):
            self.env.registry.registry_invalidated = True
