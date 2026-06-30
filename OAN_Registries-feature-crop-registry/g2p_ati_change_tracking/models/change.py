import logging
from collections import OrderedDict
from datetime import date, datetime, time, timedelta

from odoo import _, api, fields, models
from odoo import fields as odoo_fields
from odoo.exceptions import UserError
from odoo.osv import expression
import traceback


_logger = logging.getLogger(__name__)


def _flatten_export_value(value, import_compat=False):
    if isinstance(value, tuple):
        if import_compat:
            return value[0]
        return value[1] if len(value) > 1 else value[0]
    if isinstance(value, list):
        flattened = [_flatten_export_value(item, import_compat=import_compat) for item in value]
        return ", ".join(str(item) for item in flattened if item not in (False, None, ""))
    if value in (False, None):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def _normalize_domain_value(value):
    if isinstance(value, tuple) and value:
        return value[0]
    if isinstance(value, list):
        if value and isinstance(value[0], (list, tuple)):
            return value
        if len(value) == 2:
            return value[0]
    return value


def _domain_truthy_sql(value):
    return "TRUE" if value else "FALSE"


def _compile_sql_domain(domain, leaf_builder):
    tokens = list(domain or [])
    params = {}
    param_counter = 0

    def add_param(value):
        nonlocal param_counter
        param_name = f"param_{param_counter}"
        param_counter += 1
        params[param_name] = value
        return f"%({param_name})s"

    def parse_term(index):
        token = tokens[index]
        if token == "&":
            left_sql, next_index = parse_term(index + 1)
            right_sql, next_index = parse_term(next_index)
            return f"({left_sql} AND {right_sql})", next_index
        if token == "|":
            left_sql, next_index = parse_term(index + 1)
            right_sql, next_index = parse_term(next_index)
            return f"({left_sql} OR {right_sql})", next_index
        if token == "!":
            inner_sql, next_index = parse_term(index + 1)
            return f"(NOT ({inner_sql}))", next_index
        if isinstance(token, (list, tuple)) and len(token) >= 3:
            leaf_sql = leaf_builder(token[0], token[1], token[2], add_param)
            return leaf_sql or "TRUE", index + 1
        return "TRUE", index + 1

    expressions = []
    index = 0
    while index < len(tokens):
        expr_sql, index = parse_term(index)
        if expr_sql:
            expressions.append(expr_sql)

    where_clause = "WHERE " + " AND ".join(f"({expr})" for expr in expressions) if expressions else ""
    return where_clause, params


def _build_sql_order_clause(order, field_map, default_sql):
    if not order:
        return f"ORDER BY {default_sql}"

    order_terms = []
    for raw_term in order.split(","):
        raw_term = raw_term.strip()
        if not raw_term:
            continue
        parts = raw_term.split()
        field_name = parts[0].split(":")[0]
        sql_field = field_map.get(field_name)
        if not sql_field:
            continue
        direction = parts[1].upper() if len(parts) > 1 and parts[1].upper() in {"ASC", "DESC"} else "ASC"
        order_terms.append(f"{sql_field} {direction}")

    return f"ORDER BY {', '.join(order_terms)}" if order_terms else f"ORDER BY {default_sql}"


def _period_start(dt_value, granularity):
    if granularity == "year":
        return dt_value.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    if granularity == "quarter":
        first_month = ((dt_value.month - 1) // 3) * 3 + 1
        return dt_value.replace(month=first_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    if granularity == "month":
        return dt_value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if granularity == "week":
        start = dt_value - timedelta(days=dt_value.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt_value.replace(hour=0, minute=0, second=0, microsecond=0)


def _period_end(start_value, granularity):
    if granularity == "year":
        return start_value.replace(year=start_value.year + 1)
    if granularity == "quarter":
        month = start_value.month + 3
        year = start_value.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        return start_value.replace(year=year, month=month)
    if granularity == "month":
        month = start_value.month + 1
        year = start_value.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        return start_value.replace(year=year, month=month)
    if granularity == "week":
        return start_value + timedelta(days=7)
    return start_value + timedelta(days=1)


def _format_period_label(start_value, granularity):
    if granularity == "year":
        return start_value.strftime("%Y")
    if granularity == "quarter":
        quarter = ((start_value.month - 1) // 3) + 1
        return f"Q{quarter} {start_value.year}"
    if granularity == "month":
        return start_value.strftime("%B %Y")
    if granularity == "week":
        return f"Week of {start_value.strftime('%Y-%m-%d')}"
    return start_value.strftime("%Y-%m-%d")


class G2PChangeLog(models.Model):
    _name = "g2p.change.log"
    _description = "G2P Change Log"
    _rec_name = "create_date"
    _order = "create_date desc"
    _method_flag_map = {
        "create": "log_create",
        "write": "log_write",
        "unlink": "log_unlink",
        "read": "log_read",
    }

    name = fields.Char("Resource Name")
    model_id = fields.Many2one(
        "ir.model", string="Model", index=True, ondelete="set null"
    )
    model_name = fields.Char(readonly=True)
    model_model = fields.Char(string="Technical Model Name", readonly=True)
    res_id = fields.Integer("Resource ID")
    user_id = fields.Many2one("res.users", string="User")
    method = fields.Char(size=64)
    line_ids = fields.One2many("g2p.change.log.line", "log_id", string="Fields updated")
    http_session_id = fields.Integer("HTTP Session")
    http_request_id = fields.Integer("HTTP Request")
    log_type = fields.Selection(
        [("full", "Full log"), ("fast", "Fast log")], string="Type"
    )

    # External database reference
    external_audit_id = fields.Integer("External Audit ID", readonly=True)

    def _get_audit_db_manager(self):
        """Get audit database manager"""
        return self.env['g2p.change.log.database.manager']

    def _rule_allows(self, model_id, method):
        """Return True when logging is permitted for a model/method.

        - If no rule exists, default to logging (backward-compatible).
        - If method is missing/unknown, default to logging.
        - If a rule exists, honor the per-method flag.
        """
        if not model_id:
            return True

        method = (method or "").lower()
        flag_field = self._method_flag_map.get(method)

        rule = self.env["g2p.change.log.rule"].sudo().search(
            [("model_id", "=", model_id)],
            limit=1,
        )
        if not rule:
            # No rule configured: log by default
            return True

        if not flag_field:
            # Unknown method: do not block
            return True

        return getattr(rule, flag_field, False)

    @api.model_create_multi
    def create(self, vals_list):
        """Store audit logs ONLY in external database, not in Odoo database."""
        # print("🔧🔧🔧 CUSTOM CREATE METHOD CALLED 🔧🔧🔧")
        # print(f"🔧 vals_list type: {type(vals_list)}")
        # print(f"🔧 vals_list length: {len(vals_list)}")
        # print(f"🔧 vals_list content: {vals_list}")
        try:
            # print("🔧 Inside try block")
            # _logger.info(f"🔧 AuditlogLog.create() called with {len(vals_list)} records")

            # Store all records in external database only
            external_ids = []

            for i, vals in enumerate(vals_list):
                # print(f"🔧 Processing record {i+1}/{len(vals_list)}: {vals.get('model_model', 'unknown')}")
                # _logger.info(f"🔧 Processing record {i+1}/{len(vals_list)}: {vals.get('model_model', 'unknown')}")
                if not vals.get("model_id"):
                    # print("❌ No model_id in vals")
                    raise UserError(_("No model defined to create log."))
                # print(f"🔧 Getting model for ID: {vals.get('model_id')}")
                model = self.env["ir.model"].sudo().browse(vals["model_id"])
                vals.update({"model_name": model.name, "model_model": model.model})
                # print(f"🔧 Updated vals with model info: {model.name} ({model.model})")

                # Check rule
                if not self._rule_allows(vals.get("model_id"), vals.get("method")):
                    # _logger.info("⏭️ Skip log creation: rule disallows or model missing")
                    continue

                # Extract line_ids for separate processing
                line_ids_commands = vals.pop('line_ids', [])

                # Store ONLY in external audit database
                try:
                    # print(f"🔧 Creating audit log in external DB for model: {vals.get('model_model')}")
                    # _logger.info(f"🔧 Creating audit log in external DB for model: {vals.get('model_model')}")
                    external_id = self._create_in_external_db(vals)
                    # print(f"🔧 External ID returned: {external_id}")
                    if external_id:
                        external_ids.append(external_id)
                        # print(f"🔧 Created external record with ID: {external_id}")
                        # _logger.info(f"🔧 Created external record with ID: {external_id}")

                        # Process line_ids commands and create log lines in external DB
                        if line_ids_commands:
                            self._create_log_lines_in_external_db(external_id, line_ids_commands)
                    else:
                        # print("❌ Failed to create audit log in external DB: No ID returned")
                        # _logger.error("Failed to create audit log in external DB: No ID returned")
                        # For audit logs, we don't want fallback to local storage
                        # Just log the error and continue
                        external_ids.append(0)  # Placeholder
                except Exception as e:
                    # print(f"❌ Failed to create audit log in external DB: {e}")
                    # _logger.error(f"Failed to create audit log in external DB: {e}")
                    # For audit logs, we don't want fallback to local storage
                    # Just log the error and continue
                    external_ids.append(0)  # Placeholder

            # _logger.info(f"🔧 Created {len(external_ids)} external records: {external_ids}")

            # Return empty recordset since we don't store anything locally
            # This prevents the "Expected singleton" error
            return self.env['g2p.change.log']
        except Exception as e:
            # print(f"❌❌❌ EXCEPTION IN CUSTOM CREATE: {e}")
            # _logger.error(f"Exception in custom create: {e}")
            # Fallback to original create method
            return super(G2PChangeLog, self).create(vals_list)

    def _create_in_external_db(self, vals):
        """Create audit log record in external database"""
        # print(f"🔧🔧🔧 _create_in_external_db START 🔧🔧🔧")
        # print(f"🔧 _create_in_external_db called with vals: {vals}")
        # print(f"🔧 About to get database manager...")
        db_manager = self._get_audit_db_manager()
        # print(f"🔧 Got database manager: {db_manager}")
        # print(f"🔧 Database manager type: {type(db_manager)}")

        # Prepare data for external database
        external_vals = {
            'name': vals.get('name'),
            'model_id': vals.get('model_id'),
            'model_name': vals.get('model_name'),
            'model_model': vals.get('model_model'),
            'res_id': vals.get('res_id'),
            'user_id': vals.get('user_id'),
            'method': vals.get('method'),
            'log_type': vals.get('log_type'),
            'http_session_id': vals.get('http_session_id'),
            'http_request_id': vals.get('http_request_id'),
            'create_uid': self.env.uid,
            'write_uid': self.env.uid,
        }

        # Insert into external database
        query = """
            INSERT INTO g2p_change_log
            (name, model_id, model_name, model_model, res_id, user_id, method,
             log_type, http_session_id, http_request_id, create_uid, write_uid)
            VALUES (%(name)s, %(model_id)s, %(model_name)s, %(model_model)s,
                   %(res_id)s, %(user_id)s, %(method)s, %(log_type)s,
                   %(http_session_id)s, %(http_request_id)s, %(create_uid)s, %(write_uid)s)
            RETURNING id
        """

        # print(f"🔧 About to execute query with db_manager: {db_manager}")
        result = db_manager.execute_audit_query(query, external_vals, fetch=True)
        return result[0]['id'] if result else None

    def _create_log_lines_in_external_db(self, log_id, line_ids_commands):
        """Create audit log lines in external database"""
        db_manager = self._get_audit_db_manager()
        field_model = self.env["ir.model.fields"].sudo()

        for command in line_ids_commands:
            if command[0] == 0:  # Command.create()
                line_vals = command[2]  # The actual values dict
                field_id = line_vals.get("field_id")
                field_name = line_vals.get("field_name")
                field_description = line_vals.get("field_description")

                if field_id and (not field_name or not field_description):
                    field = field_model.browse(field_id)
                    if field.exists():
                        field_name = field_name or field.name
                        field_description = field_description or field.field_description

                # Prepare data for external database
                external_line_vals = {
                    'log_id': log_id,
                    'field_id': field_id,
                    'field_name': field_name,
                    'field_description': field_description,
                    'old_value': line_vals.get('old_value'),
                    'new_value': line_vals.get('new_value'),
                    'old_value_text': line_vals.get('old_value_text'),
                    'new_value_text': line_vals.get('new_value_text'),
                    'create_uid': self.env.uid,
                    'write_uid': self.env.uid,
                }

                # Insert into external database
                query = """
                    INSERT INTO g2p_change_log_line
                    (log_id, field_id, field_name, field_description, old_value, new_value,
                     old_value_text, new_value_text, create_uid, write_uid)
                    VALUES (%(log_id)s, %(field_id)s, %(field_name)s, %(field_description)s,
                           %(old_value)s, %(new_value)s, %(old_value_text)s, %(new_value_text)s,
                           %(create_uid)s, %(write_uid)s)
                """

                try:
                    db_manager.execute_audit_query(query, external_line_vals)
                except Exception as e:
                    # pass
                    _logger.error(f"Failed to create audit log line in external DB: {e}")

    def _cache_external_record(self, virtual_id, vals, external_id):
        """Cache external record data for virtual record"""
        if not hasattr(self.env, '_external_audit_cache'):
            self.env._external_audit_cache = {}

        # Store cached data with all necessary fields
        cached_data = {
            'id': virtual_id,
            'external_id': external_id,
            'name': vals.get('name'),
            'model_id': vals.get('model_id'),
            'model_name': vals.get('model_name'),
            'model_model': vals.get('model_model'),
            'res_id': vals.get('res_id'),
            'user_id': vals.get('user_id'),
            'method': vals.get('method'),
            'log_type': vals.get('log_type'),
            'http_session_id': vals.get('http_session_id'),
            'http_request_id': vals.get('http_request_id'),
            'create_uid': vals.get('create_uid', self.env.uid),
            'write_uid': vals.get('write_uid', self.env.uid),
            'create_date': fields.Datetime.now(),
            'write_date': fields.Datetime.now(),
        }

        self.env._external_audit_cache[virtual_id] = cached_data

    def read(self, fields=None, load='_classic_read'):
        """Override read to fetch data from external database for virtual records"""
        result = []

        for record in self:
            if record.id < 0:  # Virtual record (negative ID)
                # Check cache first
                if hasattr(self.env, '_external_audit_cache') and record.id in self.env._external_audit_cache:
                    cached_data = self.env._external_audit_cache[record.id]
                    if fields:
                        filtered_data = {k: v for k, v in cached_data.items() if k in fields or k == 'id'}
                        result.append(filtered_data)
                    else:
                        result.append(cached_data)
                else:
                    # Fetch from external database
                    external_data = self._fetch_external_record(-record.id)
                    if external_data:
                        if fields:
                            filtered_data = {k: v for k, v in external_data.items() if k in fields or k == 'id'}
                            result.append(filtered_data)
                        else:
                            result.append(external_data)
            else:
                # Regular record, use standard read
                regular_result = super(G2PChangeLog, record).read(fields, load)
                if regular_result:
                    result.extend(regular_result)

        return result

    @api.model
    def search(self, domain, offset=0, limit=None, order=None, count=False):
        """Override search to fetch data from external database"""
        try:
            return self._search_from_external_db(domain, offset, limit, order, count)
        except Exception as e:
            _logger.error(f"Failed to search external audit DB, falling back to local: {e}")
            return super().search(domain, offset, limit, order, count)

    def _search_from_external_db(self, domain, offset=0, limit=None, order=None, count=False):
        """Search audit logs from external database"""
        db_manager = self._get_audit_db_manager()

        # Build WHERE clause from domain
        where_clause, params = self._domain_to_sql(domain)

        if count:
            query = f"SELECT COUNT(*) as count FROM g2p_change_log {where_clause}"
            result = db_manager.execute_audit_query(query, params, fetch=True)
            return result[0]['count'] if result else 0

        # Build ORDER BY clause
        order_clause = ""
        if order:
            order_clause = f"ORDER BY {self._order_to_sql(order)}"
        else:
            order_clause = "ORDER BY create_date DESC"

        # Build LIMIT and OFFSET
        limit_clause = ""
        if limit:
            limit_clause = f"LIMIT {limit}"
        if offset:
            limit_clause += f" OFFSET {offset}"

        query = f"""
            SELECT * FROM g2p_change_log
            {where_clause} {order_clause} {limit_clause}
        """

        external_records = db_manager.execute_audit_query(query, params, fetch=True)

        # Convert external records to Odoo recordset
        return self._external_records_to_recordset(external_records)

    def _domain_to_sql(self, domain):
        """Convert Odoo domain to SQL WHERE clause"""
        if not domain:
            return "", {}

        where_parts = []
        params = {}
        param_counter = 0

        for clause in domain:
            if len(clause) == 3:
                field, operator, value = clause
                param_name = f"param_{param_counter}"
                param_counter += 1

                if operator == '=':
                    where_parts.append(f"{field} = %({param_name})s")
                elif operator == '!=':
                    where_parts.append(f"{field} != %({param_name})s")
                elif operator == 'like':
                    where_parts.append(f"{field} LIKE %({param_name})s")
                elif operator == 'ilike':
                    where_parts.append(f"{field} ILIKE %({param_name})s")
                elif operator == 'in':
                    where_parts.append(f"{field} = ANY(%({param_name})s)")
                elif operator == '>':
                    where_parts.append(f"{field} > %({param_name})s")
                elif operator == '<':
                    where_parts.append(f"{field} < %({param_name})s")
                elif operator == '>=':
                    where_parts.append(f"{field} >= %({param_name})s")
                elif operator == '<=':
                    where_parts.append(f"{field} <= %({param_name})s")

                params[param_name] = value

        where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""
        return where_clause, params

    def _order_to_sql(self, order, query=None):
        """Convert Odoo order to SQL ORDER BY clause"""
        if not order:
            return "create_date DESC"

        order_parts = []
        for part in order.split(','):
            part = part.strip()
            if ' desc' in part.lower():
                field = part.replace(' desc', '').replace(' DESC', '').strip()
                order_parts.append(f"{field} DESC")
            elif ' asc' in part.lower():
                field = part.replace(' asc', '').replace(' ASC', '').strip()
                order_parts.append(f"{field} ASC")
            else:
                order_parts.append(f"{part} ASC")

        return ", ".join(order_parts)

    def _external_records_to_recordset(self, external_records):
        """Convert external database records to Odoo recordset"""
        if not external_records:
            return self.browse([])

        # Use negative IDs to create virtual records that don't exist in local DB
        virtual_ids = []
        for ext_record in external_records:
            # Use negative external ID as virtual Odoo ID
            virtual_id = -ext_record.get('id', 0)
            virtual_ids.append(virtual_id)

            # Store external data in cache for later retrieval
            self._cache_external_record(virtual_id, ext_record)

        return self.browse(virtual_ids)

    def _cache_external_record(self, virtual_id, ext_record):
        """Cache external record data for virtual record"""
        if not hasattr(self.env, '_external_audit_cache'):
            self.env._external_audit_cache = {}

        # Convert external record to Odoo field format
        cached_data = {
            'id': virtual_id,
            'name': ext_record.get('name', ''),
            'model_id': ext_record.get('model_id'),
            'model_name': ext_record.get('model_name', ''),
            'model_model': ext_record.get('model_model', ''),
            'res_id': ext_record.get('res_id'),
            'user_id': ext_record.get('user_id'),
            'method': ext_record.get('method', ''),
            'log_type': ext_record.get('log_type', 'full'),
            'http_session_id': ext_record.get('http_session_id'),
            'http_request_id': ext_record.get('http_request_id'),
            'create_date': ext_record.get('create_date'),
            'write_date': ext_record.get('write_date'),
            'create_uid': ext_record.get('create_uid'),
            'write_uid': ext_record.get('write_uid'),
        }

        self.env._external_audit_cache[virtual_id] = cached_data

    def read(self, fields=None, load='_classic_read'):
        """Override read to fetch data from external database for virtual records"""
        result = []

        for record in self:
            if record.id < 0:  # Virtual record from external DB
                if hasattr(self.env, '_external_audit_cache') and record.id in self.env._external_audit_cache:
                    cached_data = self.env._external_audit_cache[record.id]
                    if fields:
                        filtered_data = {k: v for k, v in cached_data.items() if k in fields or k == 'id'}
                        result.append(filtered_data)
                    else:
                        result.append(cached_data)
                else:
                    # Fetch from external DB if not in cache
                    external_data = self._fetch_external_record(-record.id)
                    if external_data:
                        if fields:
                            filtered_data = {k: v for k, v in external_data.items() if k in fields or k == 'id'}
                            result.append(filtered_data)
                        else:
                            result.append(external_data)
            else:
                # Regular local record
                local_result = super(G2PChangeLog, record).read(fields, load)
                result.extend(local_result)

        return result

    def _fetch_external_record(self, external_id):
        """Fetch single record from external database"""
        try:
            db_manager = self._get_audit_db_manager()
            query = "SELECT * FROM g2p_change_log WHERE id = %(id)s"
            result = db_manager.execute_audit_query(query, {'id': external_id}, fetch=True)

            if result:
                ext_record = result[0]
                return {
                    'id': -external_id,  # Convert back to virtual ID
                    'name': ext_record.get('name', ''),
                    'model_id': ext_record.get('model_id'),
                    'model_name': ext_record.get('model_name', ''),
                    'model_model': ext_record.get('model_model', ''),
                    'res_id': ext_record.get('res_id'),
                    'user_id': ext_record.get('user_id'),
                    'method': ext_record.get('method', ''),
                    'log_type': ext_record.get('log_type', 'full'),
                    'http_session_id': ext_record.get('http_session_id'),
                    'http_request_id': ext_record.get('http_request_id'),
                    'create_date': ext_record.get('create_date'),
                    'write_date': ext_record.get('write_date'),
                    'create_uid': ext_record.get('create_uid'),
                    'write_uid': ext_record.get('write_uid'),
                }
        except Exception as e:
            _logger.error(f"Failed to fetch external audit record {external_id}: {e}")

        return None

    def write(self, vals):
        """Update model_name and model_model field values to reflect model_id
        changes."""
        if "model_id" in vals:
            if not vals["model_id"]:
                raise UserError(_("The field 'model_id' cannot be empty."))
            model = self.env["ir.model"].sudo().browse(vals["model_id"])
            vals.update({"model_name": model.name, "model_model": model.model})
        return super().write(vals)


class G2PChangeLogLine(models.Model):
    _name = "g2p.change.log.line"
    _description = "G2P Change Log Line (fields updated)"
    _rec_name = "create_date"

    field_id = fields.Many2one(
        "ir.model.fields", ondelete="set null", string="Field", index=True
    )
    log_id = fields.Many2one(
        "g2p.change.log", string="Log", ondelete="cascade", index=True
    )
    old_value = fields.Text()
    new_value = fields.Text()
    old_value_text = fields.Text(string="Previous")
    new_value_text = fields.Text(string="Changed To")
    field_name = fields.Char(readonly=True)
    field_description = fields.Char("Description", readonly=True)

    # External database reference
    external_audit_line_id = fields.Integer("External Audit Line ID", readonly=True)

    def _get_audit_db_manager(self):
        """Get audit database manager"""
        return self.env['g2p.change.log.database.manager']

    @api.model_create_multi
    def create(self, vals_list):
        """Store audit log lines ONLY in external database, not in Odoo database."""
        created_ids = []

        for vals in vals_list:
            if not vals.get("field_id"):
                raise UserError(_("No field defined to create line."))
            field = self.env["ir.model.fields"].sudo().browse(vals["field_id"])
            vals.update(
                {"field_name": field.name, "field_description": field.field_description}
            )

            # Store ONLY in external audit database
            try:
                external_id = self._create_line_in_external_db(vals)
                if external_id:
                    # Use negative external ID as virtual Odoo ID
                    virtual_id = -external_id
                    created_ids.append(virtual_id)
                else:
                    # _logger.error("Failed to create audit log line in external DB: No ID returned")
                    # Fallback to local storage only if external completely fails
                    local_record = super(G2PChangeLogLine, self).create([vals])
                    created_ids.append(local_record.id)
            except Exception as e:
                _logger.error(f"Failed to create audit log line in external DB: {e}")
                # Fallback to local storage only if external completely fails
                local_record = super(G2PChangeLogLine, self).create([vals])
                created_ids.append(local_record.id)

        return self.browse(created_ids)

    def _create_line_in_external_db(self, vals):
        """Create audit log line record in external database"""
        db_manager = self._get_audit_db_manager()

        # Get external log_id from the parent log record
        log_record = self.env['g2p.change.log'].browse(vals.get('log_id'))
        external_log_id = log_record.external_audit_id if log_record else vals.get('log_id')

        # Prepare data for external database
        external_vals = {
            'log_id': external_log_id,
            'field_id': vals.get('field_id'),
            'field_name': vals.get('field_name'),
            'field_description': vals.get('field_description'),
            'old_value': vals.get('old_value'),
            'new_value': vals.get('new_value'),
            'old_value_text': vals.get('old_value_text'),
            'new_value_text': vals.get('new_value_text'),
            'create_uid': self.env.uid,
            'write_uid': self.env.uid,
        }

        # Insert into external database
        query = """
            INSERT INTO g2p_change_log_line
            (log_id, field_id, field_name, field_description, old_value, new_value,
             old_value_text, new_value_text, create_uid, write_uid)
            VALUES (%(log_id)s, %(field_id)s, %(field_name)s, %(field_description)s,
                   %(old_value)s, %(new_value)s, %(old_value_text)s, %(new_value_text)s,
                   %(create_uid)s, %(write_uid)s)
            RETURNING id
        """

        result = db_manager.execute_audit_query(query, external_vals, fetch=True)
        return result[0]['id'] if result else None


class G2PChangeLogView(models.Model):
    _name = 'g2p.change.log.view'
    _description = 'Change Log View (External DB)'
    _rec_name = "create_date"
    _auto = False
    _order = 'create_date desc'


    # ---------------------------------------
    # FIELDS
    # ---------------------------------------
    id = fields.Integer(readonly=True)
    name = fields.Char(readonly=True)
    model_id = fields.Many2one('ir.model', readonly=True)
    model_name = fields.Char(readonly=True)
    model_model = fields.Char(readonly=True)
    res_id = fields.Integer(readonly=True)
    user_id = fields.Many2one('res.users', readonly=True)
    method = fields.Char(readonly=True)
    log_type = fields.Selection([('full','Full'), ('fast','Fast')], readonly=True)
    http_session_id = fields.Integer(readonly=True)
    http_request_id = fields.Integer(readonly=True)
    create_date = fields.Datetime(readonly=True)
    create_uid = fields.Many2one('res.users', readonly=True)
    write_date = fields.Datetime(readonly=True)
    write_uid = fields.Many2one('res.users', readonly=True)

    line_count = fields.Integer(readonly=True)
    http_session_id = fields.Char()
    http_request_id = fields.Char()

    # Relationship to log lines - computed field since virtual models can't have real One2many
    line_ids = fields.One2many('g2p.change.log.line.view', 'log_id', string='Log Lines', readonly=True)

    def __getattribute__(self, name):
        """Override to log all method calls"""
        attr = super().__getattribute__(name)
        if callable(attr) and name.startswith(('read', 'web_', 'search', 'browse', 'load')):
            _logger.info(f"🔍 METHOD CALL: {name} on {self}")
        return attr

    def name_get(self):
        """Return a lightweight display name without touching the database"""
        names = []
        for record in self:
            display = record.name
            if not display and record.create_date:
                display = odoo_fields.Datetime.to_string(record.create_date)
            if not display:
                display = f"Log {record.id}"
            names.append((record.id, display))
        return names

    @api.model
    def browse(self, ids=None):
        """Override browse to handle external IDs properly"""
        # _logger.info(f"🔍 BROWSE called with ids={ids}")
        if ids is None:
            ids = self.ids

        # If we get real integer IDs, store them for later use
        if isinstance(ids, (list, tuple)) and ids and isinstance(ids[0], int):
            # _logger.info(f"🔍 BROWSE: Got real integer IDs: {ids}")
            # Store the real IDs in the context for later retrieval
            self = self.with_context(real_browse_ids=ids)
        elif isinstance(ids, int):
            # _logger.info(f"🔍 BROWSE: Got single integer ID: {ids}")
            self = self.with_context(real_browse_ids=[ids])

        result = super().browse(ids)
        # _logger.info(f"🔍 BROWSE returning: {result}")
        return result


    # ---------------------------------------
    # UTIL
    # ---------------------------------------
    def _db(self):
        return self.env['g2p.change.log.database.manager']

    def _sql_field_map(self):
        return {
            "id": "al.id",
            "name": "al.name",
            "model_id": "al.model_id",
            "model_name": "al.model_name",
            "model_model": "al.model_model",
            "res_id": "al.res_id",
            "user_id": "al.user_id",
            "method": "al.method",
            "log_type": "al.log_type",
            "http_session_id": "al.http_session_id",
            "http_request_id": "al.http_request_id",
            "create_date": "al.create_date",
            "create_uid": "al.create_uid",
            "write_date": "al.write_date",
            "write_uid": "al.write_uid",
        }

    def _sql_text_condition(self, expressions, operator, value, add_param):
        text_value = "" if value in (False, None) else str(value)
        if operator in {"like", "ilike", "not like", "not ilike"}:
            text_value = f"%{text_value}%"
        comparator = {
            "=": "=",
            "!=": "!=",
            "like": "LIKE",
            "ilike": "ILIKE",
            "not like": "NOT LIKE",
            "not ilike": "NOT ILIKE",
            "=like": "LIKE",
            "=ilike": "ILIKE",
        }.get(operator)
        if not comparator:
            return None
        placeholder = add_param(text_value)
        joiner = " OR " if not comparator.startswith("NOT ") else " AND "
        return "(" + joiner.join(f"{expr} {comparator} {placeholder}" for expr in expressions) + ")"

    def _user_ids_for_text_search(self, value):
        return self.env["res.users"].sudo().search(
            ["|", ("name", "ilike", value), ("login", "ilike", value)]
        ).ids

    def _domain_leaf_to_sql(self, field, operator, value, add_param):
        field = (field or "").split(".")[0]
        value = _normalize_domain_value(value)
        field_map = self._sql_field_map()

        if field == "display_name":
            return self._sql_text_condition(["al.name", "al.model_name", "al.model_model"], "ilike", value, add_param)

        if field == "model_id" and isinstance(value, str) and operator in {"like", "ilike", "not like", "not ilike", "=like", "=ilike"}:
            return self._sql_text_condition(["al.model_name", "al.model_model"], operator, value, add_param)

        if field in {"user_id", "create_uid", "write_uid"} and isinstance(value, str) and operator in {
            "like", "ilike", "not like", "not ilike", "=like", "=ilike"
        }:
            user_ids = self._user_ids_for_text_search(value)
            positive = operator in {"like", "ilike", "=like", "=ilike"}
            if not user_ids:
                return _domain_truthy_sql(not positive)
            placeholder = add_param(user_ids)
            return f"({field_map[field]} = ANY({placeholder}))" if positive else f"(NOT ({field_map[field]} = ANY({placeholder})))"

        sql_field = field_map.get(field)
        if not sql_field:
            return None

        if operator == "=?":
            return "TRUE" if value in (False, None, "") else f"({sql_field} = {add_param(value)})"

        if operator in {"=", "!="} and value in (False, None):
            return f"({sql_field} IS {'NOT ' if operator == '!=' else ''}NULL)"

        if operator in {"in", "not in"}:
            values = value or []
            values = [_normalize_domain_value(item) for item in values]
            if not values:
                return _domain_truthy_sql(operator == "not in")
            placeholder = add_param(values)
            comparator = "!= ALL" if operator == "not in" else "= ANY"
            return f"({sql_field} {comparator}({placeholder}))"

        if operator in {"like", "ilike", "not like", "not ilike", "=like", "=ilike"}:
            if field in {"id", "model_id", "res_id", "user_id", "create_uid", "write_uid"}:
                cast_field = f"CAST({sql_field} AS TEXT)"
                return self._sql_text_condition([cast_field], operator, value, add_param)
            return self._sql_text_condition([sql_field], operator, value, add_param)

        comparator = {
            "=": "=",
            "!=": "!=",
            ">": ">",
            "<": "<",
            ">=": ">=",
            "<=": "<=",
        }.get(operator)
        if comparator:
            return f"({sql_field} {comparator} {add_param(value)})"
        return None

    def _domain_to_sql(self, domain):
        return _compile_sql_domain(domain, self._domain_leaf_to_sql)

    def _normalize_groupby(self, groupby, lazy=True):
        annoted_groupby = self._read_group_get_annoted_groupby(groupby, lazy=lazy)
        return list(annoted_groupby.items())

    def _get_groupby_value(self, row, original_spec, normalized_spec):
        field_name = normalized_spec.split(":")[0]
        granularity = normalized_spec.split(":")[1] if ":" in normalized_spec else None
        field = self._fields[field_name]
        raw_value = row.get(field_name)

        if field.type == "many2one":
            value_id = raw_value[0] if isinstance(raw_value, tuple) else raw_value
            value_label = raw_value[1] if isinstance(raw_value, tuple) and len(raw_value) > 1 else self._get_many2one_display_name(field_name, value_id) if value_id else False
            return {
                "result_key": original_spec,
                "result_value": (value_id, value_label) if value_id else False,
                "domain": [(field_name, "=", value_id or False)],
                "sort_key": value_label or "",
            }

        if field.type in {"date", "datetime"}:
            if not raw_value:
                return {
                    "result_key": original_spec,
                    "result_value": False,
                    "domain": [(field_name, "=", False)],
                    "range": {},
                    "sort_key": "",
                }
            dt_value = fields.Datetime.to_datetime(raw_value) if isinstance(raw_value, str) else raw_value
            dt_value = dt_value if isinstance(dt_value, datetime) else datetime.combine(dt_value, time.min)
            start_value = _period_start(dt_value, granularity or "month")
            end_value = _period_end(start_value, granularity or "month")
            db_format = "%Y-%m-%d %H:%M:%S" if field.type == "datetime" else "%Y-%m-%d"
            return {
                "result_key": original_spec,
                "result_value": _format_period_label(start_value, granularity or "month"),
                "domain": [(field_name, ">=", start_value.strftime(db_format)), (field_name, "<", end_value.strftime(db_format))],
                "range": {
                    original_spec: {
                        "from": start_value.strftime(db_format),
                        "to": end_value.strftime(db_format),
                    }
                },
                "sort_key": start_value,
            }

        return {
            "result_key": original_spec,
            "result_value": raw_value,
            "domain": [(field_name, "=", raw_value or False)],
            "sort_key": raw_value if raw_value is not False else "",
        }

    def _read_group_external(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        groupby = [groupby] if isinstance(groupby, str) else (groupby or [])
        group_specs = self._normalize_groupby(groupby, lazy=lazy)
        if not group_specs:
            return [], 0

        needed_fields = list({spec.split(":")[0] for _, spec in group_specs})
        rows = self.search_read(domain or [], needed_fields, 0, None, orderby)

        groups = OrderedDict()
        for row in rows:
            key_parts = []
            group_payload = []
            for original_spec, normalized_spec in group_specs:
                payload = self._get_groupby_value(row, original_spec, normalized_spec)
                key_parts.append(payload["sort_key"])
                group_payload.append(payload)
            key = tuple(key_parts)
            if key not in groups:
                group_row = {payload["result_key"]: payload["result_value"] for payload in group_payload}
                group_row["__domain"] = expression.AND([domain or [], sum((payload["domain"] for payload in group_payload), [])])
                group_row["__context"] = {"group_by": groupby[1:]} if lazy and len(groupby) > 1 else {}
                if any(payload.get("range") for payload in group_payload):
                    combined_range = {}
                    for payload in group_payload:
                        combined_range.update(payload.get("range") or {})
                    group_row["__range"] = combined_range
                group_row["__count"] = 0
                if len(group_payload) == 1:
                    group_row[f"{group_payload[0]['result_key'].split(':')[0]}_count"] = 0
                groups[key] = group_row
            groups[key]["__count"] += 1
            if len(group_payload) == 1:
                count_key = f"{group_payload[0]['result_key'].split(':')[0]}_count"
                groups[key][count_key] = groups[key]["__count"]

        grouped_rows = list(groups.values())
        total_length = len(grouped_rows)
        if offset:
            grouped_rows = grouped_rows[offset:]
        if limit:
            grouped_rows = grouped_rows[:limit]
        return grouped_rows, total_length

    def _table_query(self):
        """Return empty query since we handle data fetching manually"""
        return """
            SELECT
                0 as id,
                '' as name,
                0 as model_id,
                '' as model_name,
                '' as model_model,
                0 as res_id,
                0 as user_id,
                '' as method,
                'full' as log_type,
                '' as http_session_id,
                '' as http_request_id,
                NOW() as create_date,
                0 as create_uid,
                NOW() as write_date,
                0 as write_uid,
                0 as line_count
            WHERE FALSE
        """

    @api.model
    def _read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        groups, _total = self._read_group_external(domain, [], groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        return groups

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        groups, _total = self._read_group_external(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        return groups

    @api.model
    def web_read_group(self, domain, fields, groupby, limit=None, offset=0, orderby=False, lazy=True):
        groups, total = self._read_group_external(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        return {"groups": groups, "length": total}

    # ---------------------------------------
    # WEB INTERFACE METHODS
    # ---------------------------------------
    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        """Override web_search_read specifically for web interface"""
        # _logger.info(f"🌐 WEB web_search_read called with domain={domain}, specification={specification}")

        # Extract field names from specification
        fields = list(specification.keys()) if specification else None
        # _logger.info(f"🌐 WEB extracted fields: {fields}")

        try:
            # Get records using our custom search_read
            records = self.search_read(domain, fields, offset, limit, order)
            total_count = self.search_count(domain)

            # Format the result as expected by web interface
            result = {
                'length': total_count,
                'records': records,
            }

            # Handle count_limit if specified
            if count_limit and result['length'] > count_limit:
                result['length'] = count_limit

            # _logger.info(f"🌐 WEB returning result with {len(records)} records, length={result['length']}")
            return result

        except Exception as e:
            _logger.error(f"❌ web_search_read failed: {e}")
            _logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return {'length': 0, 'records': []}

    def export_data(self, fields_to_export):
        if not (self.env.is_admin() or self.env.user.has_group('base.group_allow_export')):
            raise UserError(_("You don't have the rights to export data. Please contact an Administrator."))

        import_compat = self.env.context.get("import_compat", False)
        rows = self.read(fields_to_export)
        return {
            "datas": [
                [
                    _flatten_export_value(
                        row.get("id") if field_name in (".id", "id") else row.get(field_name),
                        import_compat=import_compat,
                    )
                    for field_name in fields_to_export
                ]
                for row in rows
            ]
        }

    # ---------------------------------------
    # SEARCH + READ COMBINED
    # ---------------------------------------
    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        # _logger.info(f"🌐 WEB search_read called with domain={domain}, fields={fields}, offset={offset}, limit={limit}, order={order}")

        db = self._db()

        where_clause, params = self._domain_to_sql(domain or [])

        order_clause = _build_sql_order_clause(order, self._sql_field_map(), "al.create_date DESC")

        # MAIN SQL
        sql = f"""
            SELECT
                al.id,
                al.name,
                al.model_id,
                al.model_name,
                al.model_model,
                al.res_id,
                al.user_id,
                al.method,
                al.log_type,
                al.http_session_id,
                al.http_request_id,
                al.create_date,
                al.create_uid,
                al.write_date,
                al.write_uid,
                COUNT(l.id) AS line_count
            FROM g2p_change_log al
            LEFT JOIN g2p_change_log_line l ON l.log_id = al.id
            {where_clause}
            GROUP BY al.id
            {order_clause}
        """

        if limit:
            sql += f" LIMIT {limit}"
        if offset:
            sql += f" OFFSET {offset}"

        # _logger.info(f"🔍 Executing query: {sql}")
        # _logger.info(f"🔍 With params: {params}")

        rows = db.execute_audit_query(sql, params, fetch=True)
        # _logger.info(f"🔍 Query result count: {len(rows) if rows else 0}")

        result = self._convert_rows(rows, fields)
        # _logger.info(f"🌐 WEB Returning {len(result)} records to web interface")
        if result:
            # _logger.info(f"🌐 WEB First record: {result[0]}")

            # Store the ID mapping in the registry for later use
            id_mapping = {}
            for pos, raw_row in enumerate(rows or []):
                raw_dict = dict(raw_row)
                if 'id' in raw_dict and raw_dict['id'] is not None:
                    id_mapping[pos] = raw_dict['id']

            # Store in registry (global cache)
            self.env.registry._change_log_id_mapping = id_mapping
            # _logger.info(f"🌐 WEB Stored ID mapping: {id_mapping}")

        return result

    # ---------------------------------------
    # SEARCH
    # ---------------------------------------
    @api.model
    def search(self, domain=None, offset=0, limit=None, order=None, count=False):
        """Override search to return record IDs from external database"""
        # _logger.info(f"🔍 SEARCH called with domain={domain}, count={count}")
        try:
            if count:
                return self.search_count(domain)

            db = self._db()

            # Build WHERE clause from domain
            where_clause, params = self._domain_to_sql(domain or [])

            order_clause = _build_sql_order_clause(order, self._sql_field_map(), "al.create_date DESC")

            # Build the query
            query = f"""
                SELECT al.id
                FROM g2p_change_log al
                {where_clause}
                {order_clause}
            """

            if limit:
                query += f" LIMIT {limit}"
            if offset:
                query += f" OFFSET {offset}"

            result = db.execute_audit_query(query, params, fetch=True)
            ids = [row['id'] for row in result] if result else []

            # _logger.info(f"🔍 SEARCH returning {len(ids)} IDs: {ids}")
            return self.browse(ids)

        except Exception as e:
            _logger.error(f"❌ Failed to search external audit logs: {e}")
            return self.browse([])

    # ---------------------------------------
    # COUNT
    # ---------------------------------------
    @api.model
    def search_count(self, domain=None):
        db = self._db()

        where_clause, params = self._domain_to_sql(domain or [])

        sql = f"SELECT COUNT(*) AS cnt FROM g2p_change_log al {where_clause}"
        rows = db.execute_audit_query(sql, params, fetch=True)
        return rows[0]['cnt'] if rows else 0

    # ---------------------------------------
    # MAP ROWS TO ODOO EXPECTED OUTPUT
    # ---------------------------------------
    def _convert_rows(self, rows, fields):
        # _logger.info(f"📊 _convert_rows called with {len(rows) if rows else 0} rows, fields={fields}")
        final = []
        fields = fields or self._fields.keys()
        # _logger.info(f"📊 _convert_rows using fields: {list(fields)[:10]}...")  # Show first 10 fields

        for i, row in enumerate(rows):
            # _logger.info(f"📊 _convert_rows processing row {i}: {dict(list(row.items())[:5])}")
            r = {}

            # Always include the ID field first
            row_id = row.get('id') if hasattr(row, 'get') else dict(row).get('id')
            if row_id is not None:
                r['id'] = row_id
                # _logger.info(f"📊 _convert_rows added ID: {row_id}")
            else:
                _logger.warning("📊 _convert_rows could not find 'id' in row")

            for field in fields:
                if field == 'display_name':
                    name_val = row.get('name')
                    if not name_val and row.get('create_date'):
                        name_val = odoo_fields.Datetime.to_string(row.get('create_date'))
                    if not name_val and row.get('model_name') and row.get('res_id'):
                        name_val = f"{row.get('model_name')} {row.get('res_id')}"
                    if not name_val:
                        name_val = f"Log {row_id}" if row_id is not None else ""
                    r[field] = name_val
                    continue
                if field in row:
                    value = row[field]
                    # _logger.info(f"📊 _convert_rows field '{field}': {value} (type: {type(value)})")

                    # Convert Many2one IDs to real tuples with proper names
                    if field in self._fields and self._fields[field].type == 'many2one' and value:
                        # Get the display name for the related record
                        display_name = self._get_many2one_display_name(field, value)
                        r[field] = (value, display_name)
                        # _logger.info(f"📊 _convert_rows many2one '{field}': ({value}, '{display_name}')")
                    else:
                        r[field] = value
                else:
                    _logger.info(f"📊 _convert_rows field '{field}' not in row, skipping")

            # _logger.info(f"📊 _convert_rows row {i} result: {dict(list(r.items())[:5])}")
            final.append(r)

        # _logger.info(f"📊 _convert_rows returning {len(final)} records")
        return final

    def _get_many2one_display_name(self, field_name, record_id):
        """Get display name for many2one fields"""
        try:
            if field_name == 'model_id':
                # Get model name from ir.model
                model_record = self.env['ir.model'].browse(record_id)
                return model_record.name if model_record.exists() else f"Model {record_id}"
            elif field_name == 'user_id':
                # Get user name from res.users
                user_record = self.env['res.users'].browse(record_id)
                return user_record.name if user_record.exists() else f"User {record_id}"
            elif field_name == 'create_uid' or field_name == 'write_uid':
                # Get user name for create/write uid
                user_record = self.env['res.users'].browse(record_id)
                return user_record.name if user_record.exists() else f"User {record_id}"
            else:
                return f"Record {record_id}"
        except Exception as e:
            _logger.error(f"❌ Failed to get display name for {field_name}={record_id}: {e}")
            return f"Record {record_id}"

    def read(self, fields=None, load='_classic_read'):
        """Override read to fetch individual records from external database"""
        # _logger.info(f"📖 READ called for IDs {self.ids} with fields={fields}")
        # _logger.info(f"📖 READ self={self}, len(self)={len(self)}")

        # Handle NewId objects - extract real IDs from the recordset
        real_ids = []

        # First, try to get the active_id from context (this is set when clicking on a record)
        if self.env.context.get('active_id'):
            active_id = self.env.context.get('active_id')
            # _logger.info(f"📖 READ: Found active_id in context: {active_id}")
            if isinstance(active_id, int) and active_id > 0:
                real_ids.append(active_id)

        # If no active_id, try to extract from recordset
        if not real_ids:
            for record in self:
                if hasattr(record, '_origin') and record._origin:
                    # Get the origin record ID
                    real_ids.append(record._origin.id)
                    # _logger.info(f"📖 READ: Found origin ID {record._origin.id} for NewId {record.id}")
                elif hasattr(record, 'id') and isinstance(record.id, int) and record.id > 0:
                    # Regular integer ID
                    real_ids.append(record.id)
                    # _logger.info(f"📖 READ: Found regular ID {record.id}")
                else:
                    _logger.warning(f"📖 READ: Could not extract ID from record {record}, id={record.id}, type={type(record.id)}")

        # _logger.info(f"📖 READ: Extracted real IDs: {real_ids}")

        # If no real IDs found, check context for browse IDs
        if not real_ids and self.env.context.get('real_browse_ids'):
            real_ids = self.env.context.get('real_browse_ids')
            # _logger.info(f"📖 READ: Found real IDs in context: {real_ids}")

        # If still no real IDs, try to get from the stored mapping
        if not real_ids and hasattr(self.env.registry, '_change_log_id_mapping'):
            mapping = getattr(self.env.registry, '_change_log_id_mapping', {}) or {}
            # _logger.info(f"📖 READ: Checking stored ID mapping: {mapping}")

            mapped_ids = []
            for idx, record in enumerate(self):
                candidate_keys = []
                if isinstance(record.id, int):
                    candidate_keys.append(record.id)
                candidate_keys.append(idx)

                for key in candidate_keys:
                    if key in mapping:
                        mapped_ids.append(mapping[key])
                        # _logger.info(f"📖 READ: Mapped placeholder {key} to real ID {mapping[key]}")
                        break

            if not mapped_ids and mapping:
                mapped_ids = list(mapping.values())
                # _logger.info(f"📖 READ: No direct match, using all mapped IDs {mapped_ids}")

            real_ids = mapped_ids

        if not real_ids:
            # _logger.warning(f"📖 READ: No real IDs extracted, returning empty list")
            return []

        try:
            db = self._db()
            # _logger.info(f"📖 READ: Got database manager: {db}")

            # Build the query for specific IDs
            ids_placeholder = ','.join(['%s'] * len(real_ids))
            query = f"""
                SELECT
                    al.id,
                    al.name,
                    al.model_id,
                    al.model_name,
                    al.model_model,
                    al.res_id,
                    al.user_id,
                    al.method,
                    al.log_type,
                    al.http_session_id,
                    al.http_request_id,
                    al.create_date,
                    al.create_uid,
                    al.write_date,
                    al.write_uid,
                    COUNT(l.id) AS line_count
                FROM g2p_change_log al
                LEFT JOIN g2p_change_log_line l ON l.log_id = al.id
                WHERE al.id IN ({ids_placeholder})
                GROUP BY al.id
                ORDER BY al.create_date DESC
            """

            # _logger.info(f"📖 READ: Executing query with real IDs: {real_ids}")
            # _logger.info(f"📖 READ: Query: {query}")

            rows = db.execute_audit_query(query, real_ids, fetch=True)
            # _logger.info(f"📖 READ query returned {len(rows) if rows else 0} rows")
           
            # if rows:
                # _logger.info(f"📖 READ first row keys: {list(rows[0].keys())}")
                # _logger.info(f"📖 READ first row values: {dict(rows[0])}")
            # else:
                # _logger.error(f"📖 READ: ❌ No rows found for IDs {self.ids}")
                # _logger.error(f"📖 READ: ❌ Query was: {query}")
                # _logger.error(f"📖 READ: ❌ Parameters were: {self.ids}")


            result = self._convert_rows(rows, fields)
            # _logger.info(f"📖 READ: _convert_rows returned {len(result)} records")

            # If line_ids is requested, fetch the related log lines
            if fields and 'line_ids' in fields:
                # _logger.info(f"📖 READ: Processing line_ids for {len(result)} records")
                for record_data in result:
                    log_id = record_data.get('id')
                    if log_id:
                        # _logger.info(f"📖 READ: Fetching line_ids for log_id={log_id}")
                        # Search for log lines with this log_id
                        line_model = self.env['g2p.change.log.line.view']
                        line_ids = line_model.search([('log_id', '=', log_id)])
                        record_data['line_ids'] = line_ids.ids
                        # _logger.info(f"📖 READ: Found {len(line_ids.ids)} line_ids for log {log_id}: {line_ids.ids}")
                    else:
                        _logger.warning("📖 READ: record_data missing id; cannot fetch line_ids")

            # _logger.info(f"📖 READ returning {len(result)} records")
            if result:
                _logger.info(f"📖 READ First record keys: {list(result[0].keys())}")
                _logger.info(f"📖 READ First record sample: {dict(list(result[0].items())[:5])}")
            else:
                _logger.error(f"📖 READ: ❌ Final result is empty!")
            return result

        except Exception as e:
            _logger.error(f"❌ READ Failed to read external audit logs: {e}")
            _logger.error(f"❌ READ Traceback: {traceback.format_exc()}")
            return []


    @api.model
    def web_read(self, ids, specification):
        """Override web_read for form view compatibility"""
        # _logger.info(f"📖 WEB_READ called for IDs {ids} with specification={specification}")

        # Browse the records with the provided IDs
        records = self.browse(ids)
        # _logger.info(f"📖 WEB_READ records={records}, len(records)={len(records)}")

        fields = list(specification.keys()) if specification else []
        # _logger.info(f"📖 WEB_READ extracted fields: {fields}")
        # _logger.info(f"📖 WEB_READ fields count: {len(fields)}")

        # Use the provided IDs directly
        if not ids:
            # _logger.warning("📖 WEB_READ: No IDs provided")
            return []

        try:
            # Fetch real data using the records we browsed
            # _logger.info(f"📖 WEB_READ: Calling records.read() with fields={fields}")
            result = records.read(fields)
            # _logger.info(f"📖 WEB_READ: records.read() returned {len(result)} records")

            # If read returns empty, return a minimal record
            if not result:
                # _logger.error("📖 WEB_READ: records.read() returned empty, creating minimal record")
                minimal = {'id': ids[0] if ids else 0}
                for f in fields:
                    minimal[f] = False
                # _logger.info(f"📖 WEB_READ: Returning minimal record: {minimal}")
                return [minimal]

            # Ensure every record has 'id' and requested fields
            # _logger.info(f"📖 WEB_READ: Processing {len(result)} records")
            processed = []
            for i, rec in enumerate(result):
                # _logger.info(f"📖 WEB_READ: Record {i} before processing (truncated): {dict(list(rec.items())[:5])}")
                rec_out = {}

                # Ensure line_ids populated even if backend missed it
                line_ids_val = False
                if 'line_ids' in fields:
                    log_id_val = rec.get('id')
                    line_ids_val = self.env['g2p.change.log.line.view'].search([('log_id', '=', log_id_val)]).ids if log_id_val else []
                    # _logger.info(f"📖 WEB_READ: Injected line_ids for log {log_id_val}: {line_ids_val}")

                    # If nested spec is provided, inline line records
                    line_spec = specification.get('line_ids', {}) if specification else {}
                    line_fields = list(line_spec.get('fields', {}).keys()) if line_spec else []
                    line_limit = line_spec.get('limit')
                    line_order = line_spec.get('order')

                    if line_fields:
                        line_domain = [('log_id', '=', log_id_val)] if log_id_val else []
                        line_records = self.env['g2p.change.log.line.view'].search_read(
                            domain=line_domain,
                            fields=line_fields,
                            limit=line_limit,
                            order=line_order,
                        )
                        # _logger.info(f"📖 WEB_READ: Inlined {len(line_records)} line records for log {log_id_val}")
                        line_ids_val = line_records

                # Copy only requested fields, defaulting to False
                for f in fields:
                    if f == 'line_ids':
                        rec_out[f] = line_ids_val
                    else:
                        rec_out[f] = rec.get(f, False)

                # Ensure ID present
                if 'id' not in rec_out and ids:
                    rec_out['id'] = ids[i] if i < len(ids) else ids[0]

                processed.append(rec_out)
                # _logger.info(f"📖 WEB_READ: Record {i} after processing full: {rec_out}")

            # _logger.info(f"📖 WEB_READ: ✅ Returning {len(processed)} records successfully")
            return processed

        except Exception as e:
            _logger.error(f"❌ WEB_READ Failed web_read: {e}")
            _logger.error(f"❌ WEB_READ Traceback: {traceback.format_exc()}")

            minimal = {'id': ids[0] if ids else 0}
            for f in fields:
                minimal[f] = False
            return [minimal]

    @api.model
    @api.model
    def load_views(self, views, options=None):
        """Override load_views to log form view loading"""
        # _logger.info(f"🔍 LOAD_VIEWS called with views={views}, options={options}")
        result = super().load_views(views, options)
        # _logger.info(f"🔍 LOAD_VIEWS returning: {type(result)}")
        return result

    @api.model
    def get_views(self, views, options=None):
        """Override get_views to log view loading"""
        # _logger.info(f"🔍 GET_VIEWS called with views={views}, options={options}")
        result = super().get_views(views, options)
        # _logger.info(f"🔍 GET_VIEWS returning: {type(result)}")
        return result

    def open_record(self):
        """Custom method to open a record with proper ID handling"""
        # _logger.info(f"🔍 OPEN_RECORD called on {self}")

        # Get the real ID from the current record
        real_id = None
        if self.ids:
            # Try to get from search_read results stored in cache
            db = self._db()
            query = """
                SELECT id FROM g2p_change_log
                ORDER BY create_date DESC
                LIMIT 10
            """
            rows = db.execute_audit_query(query, {}, fetch=True)
            if rows:
                # Map the position in the list to the actual ID
                record_index = 0  # This would need to be determined from context
                if record_index < len(rows):
                    real_id = rows[record_index]['id']

        if real_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Audit Log',
                'res_model': 'g2p.change.log.view',
                'res_id': real_id,
                'view_mode': 'form',
                'view_type': 'form',
                'context': {'active_id': real_id, 'real_record_id': real_id},
                'target': 'current',
            }
        else:
            return {'type': 'ir.actions.act_window_close'}


class G2PChangeLogLineView(models.Model):
    _name = "g2p.change.log.line.view"
    _description = "G2P Change Log Line (External DB)"
    _auto = False
    _order = 'create_date desc'

    # FIELDS – same as your external DB columns
    id = fields.Integer(readonly=True)
    field_id = fields.Many2one('ir.model.fields', readonly=True)
    create_date = fields.Datetime(readonly=True)
    field_description = fields.Char(readonly=True)
    old_value_text = fields.Text(readonly=True)
    new_value_text = fields.Text(readonly=True)
    log_id = fields.Many2one('g2p.change.log.view', readonly=True)  # Link to virtual log view
    field_name = fields.Char(readonly=True)
    old_value = fields.Text(readonly=True)
    new_value = fields.Text(readonly=True)

    def _get_audit_db_manager(self):
        """Get audit database manager"""
        return self.env['g2p.change.log.database.manager']

    def _hydrate_field_metadata(self, row):
        row_dict = dict(row)
        field_id = row_dict.get("field_id")
        if field_id and (not row_dict.get("field_name") or not row_dict.get("field_description")):
            field_record = self.env["ir.model.fields"].browse(field_id)
            if field_record.exists():
                row_dict["field_name"] = row_dict.get("field_name") or field_record.name
                row_dict["field_description"] = (
                    row_dict.get("field_description") or field_record.field_description
                )
        return row_dict

    def _sql_field_map(self):
        return {
            "id": "ll.id",
            "log_id": "ll.log_id",
            "field_id": "ll.field_id",
            "field_name": "ll.field_name",
            "field_description": "ll.field_description",
            "old_value": "ll.old_value",
            "new_value": "ll.new_value",
            "old_value_text": "ll.old_value_text",
            "new_value_text": "ll.new_value_text",
            "create_date": "ll.create_date",
        }

    def _field_ids_for_text_search(self, value):
        return self.env["ir.model.fields"].sudo().search(
            ["|", ("name", "ilike", value), ("field_description", "ilike", value)]
        ).ids

    def _log_ids_for_text_search(self, value):
        query = """
            SELECT id
            FROM g2p_change_log
            WHERE name ILIKE %(term)s
               OR model_name ILIKE %(term)s
               OR model_model ILIKE %(term)s
        """
        rows = self._get_audit_db_manager().execute_audit_query(query, {"term": f"%{value}%"}, fetch=True)
        return [row["id"] for row in rows] if rows else []

    def _domain_leaf_to_sql(self, field, operator, value, add_param):
        field = (field or "").split(".")[0]
        value = _normalize_domain_value(value)
        field_map = self._sql_field_map()

        if field == "display_name":
            return f"(ll.field_description ILIKE {add_param(f'%{value}%')})"

        if field == "log_id" and isinstance(value, str) and operator in {"like", "ilike", "not like", "not ilike", "=like", "=ilike"}:
            log_ids = self._log_ids_for_text_search(value)
            positive = operator in {"like", "ilike", "=like", "=ilike"}
            if not log_ids:
                return _domain_truthy_sql(not positive)
            placeholder = add_param(log_ids)
            return f"(ll.log_id = ANY({placeholder}))" if positive else f"(NOT (ll.log_id = ANY({placeholder})))"

        if field == "field_id" and isinstance(value, str) and operator in {"like", "ilike", "not like", "not ilike", "=like", "=ilike"}:
            field_ids = self._field_ids_for_text_search(value)
            positive = operator in {"like", "ilike", "=like", "=ilike"}
            if not field_ids:
                return _domain_truthy_sql(not positive)
            placeholder = add_param(field_ids)
            return f"(ll.field_id = ANY({placeholder}))" if positive else f"(NOT (ll.field_id = ANY({placeholder})))"

        sql_field = field_map.get(field)
        if not sql_field:
            return None

        if operator == "=?":
            return "TRUE" if value in (False, None, "") else f"({sql_field} = {add_param(value)})"

        if operator in {"=", "!="} and value in (False, None):
            return f"({sql_field} IS {'NOT ' if operator == '!=' else ''}NULL)"

        if operator in {"in", "not in"}:
            values = value or []
            values = [_normalize_domain_value(item) for item in values]
            if not values:
                return _domain_truthy_sql(operator == "not in")
            placeholder = add_param(values)
            comparator = "!= ALL" if operator == "not in" else "= ANY"
            return f"({sql_field} {comparator}({placeholder}))"

        if operator in {"like", "ilike", "not like", "not ilike", "=like", "=ilike"}:
            comparator = {
                "like": "LIKE",
                "ilike": "ILIKE",
                "not like": "NOT LIKE",
                "not ilike": "NOT ILIKE",
                "=like": "LIKE",
                "=ilike": "ILIKE",
            }[operator]
            placeholder = add_param(str(value) if operator in {"=like", "=ilike"} else f"%{value}%")
            joiner = " OR " if not comparator.startswith("NOT ") else " AND "
            expression_sql = f"CAST({sql_field} AS TEXT)" if field in {"id", "log_id", "field_id"} else sql_field
            return "(" + joiner.join([f"{expression_sql} {comparator} {placeholder}"]) + ")"

        comparator = {
            "=": "=",
            "!=": "!=",
            ">": ">",
            "<": "<",
            ">=": ">=",
            "<=": "<=",
        }.get(operator)
        if comparator:
            return f"({sql_field} {comparator} {add_param(value)})"
        return None

    def _domain_to_sql(self, domain):
        return _compile_sql_domain(domain, self._domain_leaf_to_sql)

    def _normalize_groupby(self, groupby, lazy=True):
        annoted_groupby = self._read_group_get_annoted_groupby(groupby, lazy=lazy)
        return list(annoted_groupby.items())

    def _get_groupby_value(self, row, original_spec, normalized_spec):
        field_name = normalized_spec.split(":")[0]
        granularity = normalized_spec.split(":")[1] if ":" in normalized_spec else None
        field = self._fields[field_name]
        raw_value = row.get(field_name)

        if field.type == "many2one":
            value_id = raw_value[0] if isinstance(raw_value, tuple) else raw_value
            value_label = raw_value[1] if isinstance(raw_value, tuple) and len(raw_value) > 1 else self._get_many2one_display_name(field_name, value_id) if value_id else False
            return {
                "result_key": original_spec,
                "result_value": (value_id, value_label) if value_id else False,
                "domain": [(field_name, "=", value_id or False)],
                "sort_key": value_label or "",
            }

        if field.type in {"date", "datetime"}:
            if not raw_value:
                return {
                    "result_key": original_spec,
                    "result_value": False,
                    "domain": [(field_name, "=", False)],
                    "range": {},
                    "sort_key": "",
                }
            dt_value = fields.Datetime.to_datetime(raw_value) if isinstance(raw_value, str) else raw_value
            dt_value = dt_value if isinstance(dt_value, datetime) else datetime.combine(dt_value, time.min)
            start_value = _period_start(dt_value, granularity or "month")
            end_value = _period_end(start_value, granularity or "month")
            db_format = "%Y-%m-%d %H:%M:%S" if field.type == "datetime" else "%Y-%m-%d"
            return {
                "result_key": original_spec,
                "result_value": _format_period_label(start_value, granularity or "month"),
                "domain": [(field_name, ">=", start_value.strftime(db_format)), (field_name, "<", end_value.strftime(db_format))],
                "range": {
                    original_spec: {
                        "from": start_value.strftime(db_format),
                        "to": end_value.strftime(db_format),
                    }
                },
                "sort_key": start_value,
            }

        return {
            "result_key": original_spec,
            "result_value": raw_value,
            "domain": [(field_name, "=", raw_value or False)],
            "sort_key": raw_value if raw_value is not False else "",
        }

    def _read_group_external(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        groupby = [groupby] if isinstance(groupby, str) else (groupby or [])
        log_id = self._extract_log_id(domain)
        if log_id:
            domain = expression.AND([domain or [], [("log_id", "=", log_id)]])

        group_specs = self._normalize_groupby(groupby, lazy=lazy)
        if not group_specs:
            return [], 0

        needed_fields = list({spec.split(":")[0] for _, spec in group_specs})
        rows = self.search_read(domain or [], needed_fields, 0, None, orderby)

        groups = OrderedDict()
        for row in rows:
            key_parts = []
            group_payload = []
            for original_spec, normalized_spec in group_specs:
                payload = self._get_groupby_value(row, original_spec, normalized_spec)
                key_parts.append(payload["sort_key"])
                group_payload.append(payload)
            key = tuple(key_parts)
            if key not in groups:
                group_row = {payload["result_key"]: payload["result_value"] for payload in group_payload}
                group_row["__domain"] = expression.AND([domain or [], sum((payload["domain"] for payload in group_payload), [])])
                group_row["__context"] = {"group_by": groupby[1:]} if lazy and len(groupby) > 1 else {}
                if any(payload.get("range") for payload in group_payload):
                    combined_range = {}
                    for payload in group_payload:
                        combined_range.update(payload.get("range") or {})
                    group_row["__range"] = combined_range
                group_row["__count"] = 0
                if len(group_payload) == 1:
                    group_row[f"{group_payload[0]['result_key'].split(':')[0]}_count"] = 0
                groups[key] = group_row
            groups[key]["__count"] += 1
            if len(group_payload) == 1:
                count_key = f"{group_payload[0]['result_key'].split(':')[0]}_count"
                groups[key][count_key] = groups[key]["__count"]

        grouped_rows = list(groups.values())
        total_length = len(grouped_rows)
        if offset:
            grouped_rows = grouped_rows[offset:]
        if limit:
            grouped_rows = grouped_rows[:limit]
        return grouped_rows, total_length

    def _table_query(self):
        """Return empty query since we handle data fetching manually"""
        return """
            SELECT
                0 as id,
                0 as log_id,
                0 as field_id,
                '' as field_name,
                '' as field_description,
                '' as old_value,
                '' as new_value,
                '' as old_value_text,
                '' as new_value_text,
                NOW() as create_date
            WHERE FALSE
        """

    @api.model
    def _read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        groups, _total = self._read_group_external(domain, [], groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        return groups

    # ---------------------------------------
    # SEARCH
    # ---------------------------------------
    @api.model
    def search(self, domain=None, offset=0, limit=None, order=None, count=False):
        # _logger.info(f"🔍 Line SEARCH called with domain={domain}, count={count}")
        db = self._get_audit_db_manager()

        where_clause, params = self._domain_to_sql(domain or [])

        if count:
            query = f"SELECT COUNT(*) AS cnt FROM g2p_change_log_line {where_clause}"
            rows = db.execute_audit_query(query, params, fetch=True)
            cnt = rows[0]['cnt'] if rows else 0
            # _logger.info(f"🔍 Line SEARCH count={cnt}")
            return cnt

        order_clause = _build_sql_order_clause(order, self._sql_field_map(), "ll.create_date DESC")

        query = f"""
            SELECT ll.id
            FROM g2p_change_log_line ll
            {where_clause}
            {order_clause}
        """

        if limit:
            query += f" LIMIT {limit}"
        if offset:
            query += f" OFFSET {offset}"

        rows = db.execute_audit_query(query, params, fetch=True)
        ids = [row['id'] for row in rows] if rows else []
        # _logger.info(f"🔍 Line SEARCH returning ids: {ids}")
        return self.browse(ids)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        groups, _total = self._read_group_external(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        return groups

    @api.model
    def web_read_group(self, domain, fields, groupby, limit=None, offset=0, orderby=False, lazy=True):
        groups, total = self._read_group_external(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        return {"groups": groups, "length": total}

    def _extract_log_id(self, domain):
        """Get log_id from context or domain"""
        ctx = self.env.context or {}
        candidates = [
            ctx.get('active_id'),
            ctx.get('log_id'),
            ctx.get('default_log_id'),
            ctx.get('parent_id'),
            ctx.get('default_parent_id'),
        ]
        for clause in domain or []:
            if isinstance(clause, (list, tuple)) and len(clause) >= 3 and clause[0] == 'log_id':
                candidates.append(clause[2])
        for val in candidates:
            if isinstance(val, int) and val > 0:
                # _logger.info(f"🔎 LineView: extracted log_id={val} from context/domain")
                return val
        # _logger.info("🔎 LineView: no log_id found in context/domain")
        return None

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Override search_read to fetch from external database"""
        # _logger.info(f"🌐 WEB search_read called with domain={domain}, fields={fields}, offset={offset}, limit={limit}, order={order}, ctx={self.env.context}")
        try:
            # Enforce log_id scoping from context/domain
            log_id = self._extract_log_id(domain)
            if log_id:
                domain = expression.AND([domain or [], [('log_id', '=', log_id)]])
            # _logger.info(f"🌐 WEB search_read effective domain={domain}")

            db_manager = self._get_audit_db_manager()

            # Build WHERE clause from domain
            where_clause, params = self._domain_to_sql(domain or [])

            # Build ORDER BY clause - simple approach
            order_clause = _build_sql_order_clause(order, self._sql_field_map(), "ll.create_date DESC")

            # Build the query
            query = f"""
                SELECT
                    ll.id, ll.log_id, ll.field_id, ll.field_name, ll.field_description,
                    ll.old_value, ll.new_value, ll.old_value_text, ll.new_value_text,
                    ll.create_date
                FROM g2p_change_log_line ll
                {where_clause}
                {order_clause}
            """

            if limit:
                query += f" LIMIT {limit}"
            if offset:
                query += f" OFFSET {offset}"

            # _logger.info(f"🔍 Executing query: {query}")
            # _logger.info(f"🔍 With params: {params}")

            result = db_manager.execute_audit_query(query, params, fetch=True)
            # _logger.info(f"🔍 Query result count: {len(result) if result else 0}")
            # if result:
            #     _logger.info(f"🔍 First line row: {dict(list(result[0].items())[:5])}")

            # Convert result to match Odoo's expected format
            records = []
            for row in result:
                row = self._hydrate_field_metadata(row)
                record = {'id': row.get('id')}
                # Add all requested fields
                for field_name in (fields or ['id', 'log_id', 'field_name', 'field_description', 'old_value_text', 'new_value_text', 'create_date']):
                    if field_name in row:
                        value = row[field_name]
                        # Handle datetime conversion
                        if field_name == 'create_date' and value:
                            record[field_name] = value.strftime('%Y-%m-%d %H:%M:%S') if hasattr(value, 'strftime') else str(value)
                        # Handle Many2one fields
                        elif field_name in ['log_id', 'field_id'] and value:
                            display_name = self._get_many2one_display_name(field_name, value)
                            record[field_name] = (value, display_name)
                        else:
                            record[field_name] = value
                    else:
                        record[field_name] = False
                records.append(record)

            # _logger.info(f"🌐 WEB Returning {len(records)} records to web interface")
            if records:
                _logger.info(f"🌐 WEB First record: {records[0]}")
            return records

        except Exception as e:
            _logger.error(f"❌ Failed to search external audit log lines: {e}")
            _logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return []

    # ---------------------------------------
    # READ
    # ---------------------------------------
    def _convert_rows(self, rows, fields):
        """Convert DB rows to read() output"""
        fields = fields or self._fields.keys()
        final = []

        for row in rows or []:
            r = {}
            row_dict = self._hydrate_field_metadata(row)

            row_id = row_dict.get('id')
            if row_id is not None:
                r['id'] = row_id

            for field in fields:
                if field in row_dict:
                    value = row_dict[field]
                    if field in ['log_id', 'field_id'] and value:
                        display_name = self._get_many2one_display_name(field, value)
                        r[field] = (value, display_name)
                    elif field == 'create_date' and value:
                        r[field] = value.strftime('%Y-%m-%d %H:%M:%S') if hasattr(value, 'strftime') else value
                    else:
                        r[field] = value
                else:
                    r[field] = False

            final.append(r)

        return final

    def _get_many2one_display_name(self, field_name, record_id):
        try:
            if field_name == 'field_id':
                rec = self.env['ir.model.fields'].browse(record_id)
                return rec.name if rec.exists() else f"Field {record_id}"
            if field_name == 'log_id':
                return f"Log {record_id}"
        except Exception as e:
            _logger.error(f"❌ Failed to get display name for {field_name}={record_id}: {e}")
        return f"Record {record_id}"

    def read(self, fields=None, load='_classic_read'):
        """Fetch line records from external DB for given IDs"""
        # _logger.info(f"📖 Line READ called for IDs {self.ids} with fields={fields}")
        if not self.ids:
            return []

        try:
            db = self._get_audit_db_manager()
            ids_placeholder = ','.join(['%s'] * len(self.ids))
            query = f"""
                SELECT
                    id,
                    log_id,
                    field_id,
                    field_name,
                    field_description,
                    old_value,
                    new_value,
                    old_value_text,
                    new_value_text,
                    create_date
                FROM g2p_change_log_line
                WHERE id IN ({ids_placeholder})
                ORDER BY create_date DESC
            """

            rows = db.execute_audit_query(query, self.ids, fetch=True)
            # _logger.info(f"📖 Line READ fetched {len(rows) if rows else 0} rows for ids={self.ids}")
            return self._convert_rows(rows, fields)

        except Exception as e:
            _logger.error(f"❌ Line READ failed: {e}")
            _logger.error(f"❌ Line READ traceback: {traceback.format_exc()}")
            return []

    @api.model
    def web_read(self, ids, specification):
        """web_read wrapper to make one2many load work from external DB"""
        # _logger.info(f"📖 Line WEB_READ called for IDs {ids} with specification={specification}")
        fields = list(specification.keys()) if specification else []
        records = self.browse(ids)
        res = records.read(fields)
        # _logger.info(f"📖 Line WEB_READ returning {len(res)} records")
        return res

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        """Override web_search_read specifically for web interface"""
        # _logger.info(f"🌐 WEB web_search_read called with domain={domain}, specification={specification}")

        # Extract field names from specification
        fields = list(specification.keys()) if specification else None
        # _logger.info(f"🌐 WEB extracted fields: {fields}")

        # Ensure log_id scoping
        log_id = self._extract_log_id(domain)
        if log_id:
            domain = expression.AND([domain or [], [('log_id', '=', log_id)]])
        # _logger.info(f"🌐 WEB web_search_read effective domain={domain}")

        try:
            # Get records using our custom search_read
            records = self.search_read(domain, fields, offset, limit, order)
            total_count = self.search_count(domain)

            # Format the result as expected by web interface
            result = {
                'length': total_count,
                'records': records,
            }

            # Handle count_limit if specified
            if count_limit and result['length'] > count_limit:
                result['length'] = count_limit

            # _logger.info(f"🌐 WEB returning result with {len(records)} records, length={result['length']}")
            return result

        except Exception as e:
            _logger.error(f"❌ web_search_read failed: {e}")
            _logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return {'length': 0, 'records': []}

    def export_data(self, fields_to_export):
        if not (self.env.is_admin() or self.env.user.has_group('base.group_allow_export')):
            raise UserError(_("You don't have the rights to export data. Please contact an Administrator."))

        import_compat = self.env.context.get("import_compat", False)
        rows = self.read(fields_to_export)
        return {
            "datas": [
                [
                    _flatten_export_value(
                        row.get("id") if field_name in (".id", "id") else row.get(field_name),
                        import_compat=import_compat,
                    )
                    for field_name in fields_to_export
                ]
                for row in rows
            ]
        }

    # @api.model
    # def search(self, domain=None, offset=0, limit=None, order=None, count=False):
    #     """Override search to return record IDs from external database"""
    #     # _logger.info(f"🔍 SEARCH called with domain={domain}, count={count}")
    #     try:
    #         if count:
    #             return self.search_count(domain)

    #         db_manager = self._get_audit_db_manager()

    #         # Build WHERE clause from domain
    #         where_clause, params = self._domain_to_sql(domain or [])

    #         # Build ORDER BY clause
    #         order_clause = ""
    #         if order:
    #             order_parts = order.split(',')[0].strip().split()
    #             if len(order_parts) >= 1:
    #                 field = order_parts[0]
    #                 direction = "DESC" if len(order_parts) > 1 and order_parts[1].upper() == "DESC" else "ASC"
    #                 order_clause = f"ORDER BY {field} {direction}"
    #         else:
    #             order_clause = "ORDER BY id ASC"

    #         # Build the query
    #         query = f"""
    #             SELECT id
    #             FROM g2p_change_log_line
    #             {where_clause}
    #             {order_clause}
    #         """

    #         if limit:
    #             query += f" LIMIT {limit}"
    #         if offset:
    #             query += f" OFFSET {offset}"

    #         result = db_manager.execute_audit_query(query, params, fetch=True)
    #         ids = [row['id'] for row in result] if result else []

    #         # _logger.info(f"🔍 SEARCH returning {len(ids)} IDs: {ids}")
    #         return self.browse(ids)

    #     except Exception as e:
    #         _logger.error(f"❌ Failed to search external audit log lines: {e}")
    #         return self.browse([])

    # def read(self, fields=None, load='_classic_read'):
    #     """Override read to fetch data from external database"""
    #     # _logger.info(f"📖 READ called for IDs {self.ids} with fields={fields}")
    #     try:
    #         if not self.ids:
    #             return []

    #         db_manager = self._get_audit_db_manager()

    #         # Build the query
    #         query = """
    #             SELECT
    #                 id, log_id, field_id, field_name, field_description,
    #                 old_value, new_value, old_value_text, new_value_text,
    #                 create_date
    #             FROM g2p_change_log_line
    #             WHERE id = ANY(%(ids)s)
    #             ORDER BY id ASC
    #         """

    #         result = db_manager.execute_audit_query(query, {'ids': self.ids}, fetch=True)

    #         # Convert result to match Odoo's expected format
    #         records = []
    #         for row in result:
    #             record = {'id': row.get('id')}
    #             # Add all requested fields
    #             for field_name in (fields or ['id', 'log_id', 'field_name', 'field_description', 'old_value_text', 'new_value_text', 'create_date']):
    #                 if field_name in row:
    #                     value = row[field_name]
    #                     # Handle datetime conversion
    #                     if field_name == 'create_date' and value:
    #                         record[field_name] = value.strftime('%Y-%m-%d %H:%M:%S') if hasattr(value, 'strftime') else str(value)
    #                     else:
    #                         record[field_name] = value
    #                 else:
    #                     record[field_name] = False
    #             records.append(record)

    #         # _logger.info(f"📖 READ returning {len(records)} records")
    #         return records

    #     except Exception as e:
    #         _logger.error(f"❌ Failed to read external audit log lines: {e}")
    #         _logger.error(f"❌ Traceback: {traceback.format_exc()}")
    #         return []

    def _get_many2one_display_name(self, field_name, record_id):
        """Get display name for many2one fields"""
        try:
            if field_name == 'log_id':
                rows = self._get_audit_db_manager().execute_audit_query(
                    """
                        SELECT name, model_name, res_id
                        FROM g2p_change_log
                        WHERE id = %(log_id)s
                        LIMIT 1
                    """,
                    {"log_id": record_id},
                    fetch=True,
                )
                if rows:
                    row = rows[0]
                    return row.get("name") or (
                        f"{row.get('model_name')} {row.get('res_id')}"
                        if row.get("model_name") and row.get("res_id")
                        else f"Log {record_id}"
                    )
                return f"Log {record_id}"
            elif field_name == 'field_id':
                # Get field name from ir.model.fields
                field_record = self.env['ir.model.fields'].browse(record_id)
                return field_record.field_description if field_record.exists() else f"Field {record_id}"
            else:
                return f"Record {record_id}"
        except Exception as e:
            _logger.error(f"❌ Failed to get display name for {field_name}={record_id}: {e}")
            return f"Record {record_id}"

    # def web_read(self, specification):
    #     """Override web_read for form view compatibility"""
    #     # _logger.info(f"📖 WEB_READ called for IDs {self.ids} with specification={specification}")

    #     if not self.ids:
    #         return []

    #     try:
    #         # Extract field names from specification
    #         fields = list(specification.keys()) if specification else None

    #         # Use our custom read method
    #         result = self.read(fields)

    #         # _logger.info(f"📖 WEB_READ returning {len(result)} records")
    #         if result:
    #             _logger.info(f"📖 WEB_READ First record: {result[0]}")
    #         return result

    #     except Exception as e:
    #         _logger.error(f"❌ Failed to web_read external audit log lines: {e}")
    #         _logger.error(f"❌ Traceback: {traceback.format_exc()}")
    #         return []

    @api.model
    def search_count(self, domain=None):
        """Override search_count to count from external database"""
        try:
            db_manager = self._get_audit_db_manager()

            # Build WHERE clause from domain
            where_clause, params = self._domain_to_sql(domain or [])

            # Build the query
            query = f"""
                SELECT COUNT(*) as count
                FROM g2p_change_log_line ll
                {where_clause}
            """

            result = db_manager.execute_audit_query(query, params, fetch=True)
            return result[0]['count'] if result else 0

        except Exception as e:
            _logger.error(f"Failed to count external audit log lines: {e}")
            return 0
