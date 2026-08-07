import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class G2PLivestockRegistryLine(models.Model):
    _name = 'g2p.livestock.registry.line'
    _description = 'Livestock Registry Line'

    registry_id = fields.Many2one('g2p.livestock.registry', string='Registry')

    ear_tag_id = fields.Char(string='Animal Ear Tag')

    # Auto-populate owner from registry if not explicitly set
    owner_id = fields.Many2one(
        'res.partner',
        string='Owner',
        compute='_compute_owner_id',
        store=True,
        readonly=False
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
    ], string='Status', default='draft')

    name = fields.Char(string='Name', compute='_compute_name', store=True)

    # ==================== CHANGED TO RELATIONAL FIELD ====================
    species_id = fields.Many2one(
        'g2p.livestock.type',
        string='Species',
        required=True,
        tracking=True,
        ondelete='restrict'
    )
    # =====================================================================

    breed = fields.Char(string='Breed', tracking=True)

    gender = fields.Selection(
        [('male', 'Male'), ('female', 'Female')],
        string="Gender"
    )

    weight = fields.Float(string='Weight (kg)', tracking=True, help="Body weight of the animal, in kilograms.")

    health_status = fields.Selection([
        ('healthy', 'Healthy'),
        ('sick', 'Sick'),
        ('quarantined', 'Quarantined'),
        ('deceased', 'Deceased'),
    ], string='Health Status', required=True, default='healthy', tracking=True)

    vaccination_status = fields.Selection([
        ('up_to_date', 'Up-to-date'),
        ('overdue', 'Overdue'),
        ('none', 'None'),
    ], string='Vaccination Status', required=True, default='none', tracking=True)

    date_of_birth = fields.Date(string='Date of Birth')
    age = fields.Char(string='Age', compute='_compute_age', store=True)
    registration_date = fields.Date(default=fields.Date.today, required=True, tracking=True)

    @api.depends('registry_id', 'registry_id.owner_id', 'registry_id.farmer_id')
    def _compute_owner_id(self):
        """Auto-inherit owner from parent registry when creating new lines."""
        for rec in self:
            if not rec.owner_id and rec.registry_id:
                rec.owner_id = rec.registry_id.owner_id or rec.registry_id.farmer_id

    @api.depends('date_of_birth')
    def _compute_age(self):
        for rec in self:
            if rec.date_of_birth:
                delta = fields.Date.today() - rec.date_of_birth
                rec.age = _("%(years)s years, %(months)s months") % {
                    'years': delta.days // 365,
                    'months': (delta.days % 365) // 30,
                }
            else:
                rec.age = False

    @api.depends('ear_tag_id', 'species_id')
    def _compute_name(self):
        for rec in self:
            if rec.ear_tag_id:
                species_name = rec.species_id.name if rec.species_id else ''
                rec.name = f"{species_name} - {rec.ear_tag_id}"
            else:
                rec.name = rec.species_id.name if rec.species_id else ''

    # =========================================================================
    # CREATE / WRITE OVERRIDES
    # =========================================================================
    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            # Ensure owner_id is set from registry if missing
            if not vals.get('owner_id') and vals.get('registry_id'):
                registry = self.env['g2p.livestock.registry'].browse(vals['registry_id'])
                if registry.owner_id:
                    vals['owner_id'] = registry.owner_id.id
                elif registry.farmer_id:
                    vals['owner_id'] = registry.farmer_id.id

            self._validate_no_duplicate_ear_tag(vals)

        return super().create(vals_list)

    def write(self, vals):
        """Override write to validate duplicates when key fields are updated."""
        if any(key in vals for key in ['ear_tag_id', 'species_id', 'breed']):
            for rec in self:
                merged_vals = {
                    'ear_tag_id': vals.get('ear_tag_id', rec.ear_tag_id),
                    'species_id': vals.get('species_id', rec.species_id.id),
                    'breed': vals.get('breed', rec.breed),
                }
                self._validate_no_duplicate_ear_tag(merged_vals, exclude_id=rec.id)
        return super().write(vals)

    def _validate_no_duplicate_ear_tag(self, vals, exclude_id=None):
        """Validate uniqueness based on Ear Tag + Species + Breed"""
        ear_tag_id = vals.get('ear_tag_id')
        species_id = vals.get('species_id')
        breed = vals.get('breed')

        # Skip validation if required fields are missing
        if not ear_tag_id or not species_id or not breed:
            return

        # Normalize values
        normalized_tag = str(ear_tag_id).strip().upper()
        normalized_breed = str(breed).strip().lower()

        domain = [
            ('species_id', '=', species_id),
            ('breed', '=ilike', normalized_breed),
        ]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))

        existing_records = self.search(domain)

        for rec in existing_records:
            if rec.ear_tag_id and rec.ear_tag_id.strip().upper() == normalized_tag:
                species_name = rec.species_id.name if rec.species_id else ''
                raise ValidationError(
                    _("An animal with Ear Tag '%(tag)s', Species '%(species)s', "
                      "and Breed '%(breed)s' already exists (%(existing)s). "
                      "This combination must be unique.") % {
                        'tag': ear_tag_id,
                        'species': species_name,
                        'breed': breed,
                        'existing': rec.name or rec.ear_tag_id
                    }
                )

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================
    @api.constrains('ear_tag_id')
    def _check_ear_tag_format(self):
        for rec in self:
            tag = (rec.ear_tag_id or '').strip()
            if not tag:
                continue
            # Ethiopian Livestock Data Standard: alphabetic ISO country code
            # (ET) followed by exactly 10 digits, e.g. ET0000000013.
            normalized = re.sub(r'\s+', '', tag).upper()
            if not re.match(r'^ET\d{10}$', normalized):
                raise ValidationError(
                    _("Invalid Ear Tag ID '%(tag)s'!\n\n"
                      "Ear Tag ID must be in this exact format:\n"
                      "ET followed by exactly 10 digits.\n\n"
                      "Correct Example: ET0000000013") % {'tag': tag}
                )

    @api.constrains('ear_tag_id', 'species_id', 'breed')
    def _check_duplicate_ear_tag_constraint(self):
        """Fallback constraint for duplicate detection."""
        for rec in self:
            if not rec.ear_tag_id or not rec.species_id or not rec.breed:
                continue

            normalized_tag = rec.ear_tag_id.strip().upper()
            normalized_breed = rec.breed.strip().lower()

            siblings = self.search([
                ('id', '!=', rec.id),
                ('species_id', '=', rec.species_id.id),
                ('breed', '=ilike', normalized_breed),
            ])

            for sib in siblings:
                if sib.ear_tag_id and sib.ear_tag_id.strip().upper() == normalized_tag:
                    raise ValidationError(
                        _("An animal with Ear Tag '%(tag)s', Species '%(species)s', "
                          "and Breed '%(breed)s' already exists (%(existing)s).") % {
                            'tag': rec.ear_tag_id,
                            'species': rec.species_id.name,
                            'breed': rec.breed,
                            'existing': sib.name or sib.ear_tag_id
                        }
                    )

    CRITICAL_FIELDS = ('ear_tag_id', 'species_id')  # Updated

    _sql_constraints = [
        ('ear_tag_species_owner_uniq', 'unique(ear_tag_id, species_id, owner_id)',
         'Duplicate Ear Tag for this species and owner already exists!'),
    ]

    def action_bulk_export(self):
        """Export selected ANIMALS to Excel"""
        if not self:
            raise UserError(_("No animals selected to export."))

        import io
        import base64
        import xlsxwriter

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Animals Export')
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})

        headers = [
            'OAN ID', 'Ear Tag', 'Species', 'Breed', 'Gender', 'Weight (kg)', 'Owner', 'Woreda',
            'Health Status', 'Vaccination Status', 'Age', 'Registration Date',
        ]
        for col, title in enumerate(headers):
            sheet.write(0, col, title, header_format)

        for row, rec in enumerate(self, start=1):
            reg = rec.registry_id
            sheet.write(row, 0, reg.name or '')
            sheet.write(row, 1, rec.ear_tag_id or '')
            sheet.write(row, 2, rec.species_id.name if rec.species_id else '')  # Updated
            sheet.write(row, 3, rec.breed or '')
            sheet.write(row, 4, dict(rec._fields['gender'].selection).get(rec.gender, '') if rec.gender else '')
            sheet.write(row, 5, rec.weight or 0.0)
            sheet.write(row, 6, rec.owner_id.name or '')
            sheet.write(row, 7, reg.woreda_id.name or '')
            sheet.write(row, 8, dict(rec._fields['health_status'].selection).get(rec.health_status, ''))
            sheet.write(row, 9, dict(rec._fields['vaccination_status'].selection).get(rec.vaccination_status, ''))
            sheet.write(row, 10, rec.age or '')
            sheet.write(row, 11, str(rec.registration_date or ''))

        workbook.close()
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': 'Animals_Export_%s.xlsx' % fields.Datetime.now().strftime('%Y%m%d_%H%M%S'),
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'g2p.livestock.registry.line',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }