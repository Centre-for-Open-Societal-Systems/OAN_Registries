import csv
import io
import base64
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class G2PLivestockImportBatch(models.Model):
    """LR-20: Batch Import Processing."""
    _name = 'g2p.livestock.import.batch'
    _description = 'Livestock Import Batch'
    _order = 'create_date desc'

    name = fields.Char(string='Batch ID', readonly=True, copy=False, default=lambda self: _('New'))

    source_system = fields.Selection([
        ('dovar', 'DOVAR'),
        ('lits', 'LITS'),
        ('case_book', 'Case Book'),
        ('alive', 'ALIVE / AgMIS'),
        ('manual', 'Manual Upload'),
    ], string='Source System', required=True, default='manual')

    import_file = fields.Binary(string='File (CSV or Excel)', attachment=True)
    import_filename = fields.Char(string='File Name')

    state = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], string='Status', default='pending', readonly=True, tracking=True)

    total_rows = fields.Integer(string='Total Rows', readonly=True)
    success_count = fields.Integer(string='Succeeded', readonly=True)
    failure_count = fields.Integer(string='Failed', readonly=True)
    conflict_count = fields.Integer(string='Conflicts', readonly=True)
    error_log = fields.Text(string='Error / Conflict Log', readonly=True)

    processed_by = fields.Many2one('res.users', string='Processed By', readonly=True)
    processing_date = fields.Datetime(string='Processed On', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('g2p.livestock.import.batch') or _('New')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # File reading
    # ------------------------------------------------------------------
    def _read_rows(self):
        self.ensure_one()
        raw = base64.b64decode(self.import_file)
        filename = (self.import_filename or '').lower()
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            return self._read_excel_rows(raw)
        return self._read_csv_rows(raw)

    def _read_csv_rows(self, raw):
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        return list(reader)

    def _read_excel_rows(self, raw):
        import openpyxl
        workbook = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
        sheet = workbook.active
        rows_iter = sheet.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration:
            return []
        headers = [str(h).strip() if h is not None else '' for h in header_row]
        rows = []
        for row_values in rows_iter:
            if row_values is None or all(v is None for v in row_values):
                continue
            row_dict = {}
            for i, header in enumerate(headers):
                if not header:
                    continue
                value = row_values[i] if i < len(row_values) else None
                if hasattr(value, 'strftime'):
                    value = value.strftime('%Y-%m-%d')
                row_dict[header] = '' if value is None else str(value).strip()
            rows.append(row_dict)
        return rows

    # ------------------------------------------------------------------
    # Main processing — Updated for species_id
    # ------------------------------------------------------------------
    def action_process_file(self):
        """Main import logic - now works with species_id (Many2one)"""
        self.ensure_one()
        if not self.import_file:
            raise UserError(_("Please upload a CSV or Excel file first."))

        self.write({'state': 'processing'})

        try:
            rows = self._read_rows()
        except Exception as e:
            self.write({'state': 'failed', 'error_log': _("Could not read file: %s") % e})
            return

        Registry = self.env['g2p.livestock.registry']
        Line = self.env['g2p.livestock.registry.line']
        Partner = self.env['res.partner']

        total = success = failure = conflict = 0
        errors = []
        registry_cache = {}  # farmer_id -> registry record

        for row_num, row in enumerate(rows, start=2):  # row 1 = header
            total += 1

            ear_tag = (row.get('ear_tag_id') or '').strip()
            species_str = (row.get('species') or '').strip().lower()  # Value from CSV/Excel
            farmer_id = (row.get('farmer_id') or '').strip()

            if not ear_tag or not species_str:
                failure += 1
                errors.append(_("Row %s: missing required field (ear_tag_id or species) — skipped.") % row_num)
                continue

            if not farmer_id:
                failure += 1
                errors.append(_("Row %s: missing required field (farmer_id) — skipped.") % row_num)
                continue

            # Find species record by name (case-insensitive)
            species_id = self.env['g2p.livestock.type'].search([
                ('name', '=ilike', species_str)
            ], limit=1)

            if not species_id:
                failure += 1
                errors.append(
                    _("Row %s: Species '%s' not found in Livestock Types — skipped.") % (row_num, species_str))
                continue

            try:
                with self.env.cr.savepoint():
                    owner = Partner.search([('farmer_id', '=', farmer_id)], limit=1)
                    if not owner:
                        failure += 1
                        errors.append(_("Row %s: Farmer ID '%s' not found — skipped.") % (row_num, farmer_id))
                        continue

                    if not owner.woreda:
                        failure += 1
                        errors.append(_("Row %s: Farmer '%s' has no Woreda set — skipped.") % (row_num, owner.name))
                        continue

                    # Find or create Registry
                    registry = registry_cache.get(farmer_id)
                    if not registry:
                        registry = Registry.search([('owner_id', '=', owner.id)], limit=1)
                        if not registry:
                            registry = Registry.create({
                                'farmer_id': farmer_id,
                                'owner_id': owner.id,
                                'region_id': owner.region.id if owner.region else False,
                                'zone_id': owner.zone.id if owner.zone else False,
                                'woreda_id': owner.woreda.id if owner.woreda else False,
                                'kebele_id': owner.kebele.id if owner.kebele else False,
                                'source_system': self.source_system,
                                'import_batch_id': self.id,
                            })
                        registry_cache[farmer_id] = registry

                    # Check for existing line using species_id
                    existing_lines = Line.search([
                        ('registry_id', '=', registry.id),
                        ('ear_tag_id', '=ilike', ear_tag),
                        ('species_id', '=', species_id.id),
                    ])

                    if len(existing_lines) > 1:
                        conflict += 1
                        errors.append(_("Row %s: Multiple animals match Ear Tag '%s' + Species — flagged for review.")
                                      % (row_num, ear_tag))
                        continue

                    line_vals = {
                        'ear_tag_id': ear_tag,
                        'species_id': species_id.id,  # ← Updated
                        'breed': row.get('breed') or '',
                        'owner_id': owner.id,
                    }

                    if row.get('registration_date'):
                        line_vals['registration_date'] = row['registration_date']
                    if row.get('date_of_birth'):
                        line_vals['date_of_birth'] = row['date_of_birth']
                    if row.get('weight'):
                        try:
                            line_vals['weight'] = float(row['weight'])
                        except (TypeError, ValueError):
                            pass

                    if existing_lines:
                        existing_lines.write(line_vals)
                    else:
                        line_vals['registry_id'] = registry.id
                        Line.create(line_vals)

                    success += 1

            except Exception as e:
                failure += 1
                errors.append(_("Row %s: unexpected error — %s") % (row_num, str(e)))
                _logger.warning("Import batch %s, row %s failed: %s", self.name, row_num, e)

        self.write({
            'state': 'completed',
            'total_rows': total,
            'success_count': success,
            'failure_count': failure,
            'conflict_count': conflict,
            'error_log': '\n'.join(errors) if errors else _('No errors.'),
            'processed_by': self.env.uid,
            'processing_date': fields.Datetime.now(),
        })