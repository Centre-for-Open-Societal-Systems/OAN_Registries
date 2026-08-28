import json
import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
import logging


class G2PLivestockRegistry(models.Model):
    _name = 'g2p.livestock.registry'
    _description = 'Livestock Registry'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'registration_date desc, id desc'

    name = fields.Char(
        string='OAN ID', readonly=True, copy=False, index=True, default=lambda self: _('New'),
        help="Auto-generated from the Farmer Code and Farmer's first name, e.g. "
             "FR-1234567890-ABEBE-001, with a running number per farmer."
    )
    ear_tag_id = fields.Char(string='Ear Tag ID', index=True, tracking=True)
    secondary_identifier = fields.Char(string='Secondary Identifier (Legacy)')

    species_id = fields.Many2one(
        'g2p.livestock.type',
        string='Species',
        tracking=True,
        ondelete='restrict'
    )

    breed = fields.Char(string='Breed', tracking=True)

    # Farmer selection: choose the farmer here (labeled "Farmer ID" to match
    # Crop Registry's selector — you pick by farmer name, and Farmer Code,
    # Fayda ID, Region/Zone/Woreda/Kebele all auto-generate below).
    owner_id = fields.Many2one(
        'res.partner',
        string='Farmer ID',
        required=True,
        tracking=True,
        ondelete='restrict',
        domain="[('is_farmer', '=', 'yes')]",
    )

    # Auto-filled from the selected farmer (owner_id) — not manually typed.
    farmer_id = fields.Char(
        string='Farmer Id',
        tracking=True,
        readonly=True,
        copy=False,
        help="Auto-filled from the selected Farmer. FR- followed by 10 digits.",
    )

    fayda_id = fields.Char(
        string='Fayda ID',
        tracking=True,
        readonly=True,
        copy=False,
        required=True,
        help="Auto-fetched from the Farmer's (Individual's) UID entry under "
             "Individuals > IDs. Not editable here. The selected Farmer must "
             "have a valid Fayda ID (FAN- followed by 16 digits) on file "
             "before a livestock record can be saved.",
    )

    line_ids = fields.One2many('g2p.livestock.registry.line', 'registry_id', string='Animals')

    region_id = fields.Many2one('g2p.region', string='Region', tracking=True, readonly=False)
    zone_id = fields.Many2one('g2p.zone', string='Zone', tracking=True, readonly=False)
    woreda_id = fields.Many2one('g2p.woreda', string='Woreda', required=False, tracking=True, readonly=False)
    kebele_id = fields.Many2one('g2p.kebele', string='Kebele', required=False, tracking=True, readonly=False)

    date_of_birth = fields.Date(string='Date of Birth')
    age = fields.Char(string='Age', compute='_compute_age', store=True)
    registration_date = fields.Date(default=fields.Date.today, required=True, tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('kebele_approved', 'Kebele Approved'),
        ('woreda_approved', 'Woreda Approved'),
        ('zone_approved', 'Zone Approved'),
        ('verified', 'Region Approved (Verified)'),
        ('archived', 'Archived'),
    ], string='Status', default='draft', tracking=True, copy=False, required=True)

    # Tracks when `state` last changed, so the approval-pending reminder
    # cron can tell how long a record has been stuck at the current level.
    state_date = fields.Date(
        string='Status Since', default=fields.Date.today, readonly=True, copy=False,
    )
    approval_reminder_sent = fields.Boolean(default=False, copy=False)

    notes = fields.Text(string='Notes')

    source_system = fields.Selection([
        ('manual', 'Manual Entry'),
        ('dovar', 'DOVAR'),
        ('lits', 'LITS'),
        ('casebook', 'Case Book'),
        ('alive', 'ALIVE / AgMIS'),
        ('offline', 'Offline Mobile Sync'),
    ], string='Source System', default='manual', tracking=True)

    import_batch_id = fields.Many2one('g2p.livestock.import.batch', string='Import Batch', readonly=True)

    sync_status = fields.Selection([
        ('synced', 'Synced'),
        ('pending', 'Pending Sync'),
        ('conflict', 'Conflict'),
        ('failed', 'Failed'),
    ], string='Sync Status', default='synced', tracking=True)

    health_event_ids = fields.One2many('g2p.livestock.health.event', 'livestock_id', string='Health Events')
    vaccination_ids = fields.One2many('g2p.livestock.vaccination', 'livestock_id', string='Vaccinations')
    vital_event_ids = fields.One2many('g2p.livestock.vital.event', 'livestock_id', string='Vital Events')
    breeding_ids = fields.One2many('g2p.livestock.breeding', 'livestock_id', string='Breeding Events')

    audit_log_ids = fields.One2many(
        'g2p.livestock.audit.log', 'res_id', string='Audit Logs',
        domain=[('res_model', '=', 'g2p.livestock.registry')]
    )

    count_measure = fields.Integer(string='Count', default=1)

    # =====================================================================
    # Farmer ID Format Validation (FR-10 digits)
    # =====================================================================
    @api.constrains('farmer_id')
    def _check_farmer_id_format(self):
        for rec in self:
            if not rec.farmer_id:
                continue
            fid = rec.farmer_id.strip().upper()
            if not re.match(r'^FR-\d{10}$', fid):
                raise ValidationError(
                    _("Invalid Farmer ID format!\n\n"
                      "Farmer ID must be in this exact format:\n"
                      "FR- followed by exactly 10 digits.\n\n"
                      "Correct Example: FR-1234567890")
                )

    # =====================================================================
    # Fayda ID Format Validation (FAN- + 16 digits) — same rule as Crop
    # Registry. Since fayda_id is required, an empty value is already
    # blocked by the field's "required" constraint; this only checks the
    # format once a value is present.
    # =====================================================================
    @api.constrains('fayda_id')
    def _check_fayda_id_format(self):
        for rec in self:
            if rec.fayda_id:
                if not re.match(r'^FAN-\d{16}$', rec.fayda_id):
                    raise ValidationError(
                        _("Fayda ID must be in this format: FAN-1234567890123456")
                    )

    # =====================================================================
    # Fayda ID — auto-fetched from the Farmer's (res.partner) UID ID line
    # =====================================================================
    @api.model
    def _get_fayda_id_for_partner(self, partner):
        """Look up the value of the 'UID' entry under the given farmer's
        (res.partner) IDs tab (model g2p.reg.id, e.g. ID Type = UID,
        ID Number = the Fayda ID) and return it. Returns False if the
        partner has no UID ID line, or if the ID registry model isn't
        installed for some reason."""
        if not partner:
            return False
        try:
            RegId = self.env['g2p.reg.id']
        except KeyError:
            return False

        # Prefer the partner's own o2m if it exists, otherwise search
        # g2p.reg.id directly by partner_id — either way we filter on
        # the ID Type's name being 'UID'.
        reg_ids = getattr(partner, 'reg_ids', None)
        if reg_ids is not None:
            uid_line = reg_ids.filtered(
                lambda r: r.id_type and (r.id_type.name or '').strip().upper() == 'UID'
            )[:1]
        else:
            uid_line = RegId.sudo().search([
                ('partner_id', '=', partner.id),
                ('id_type.name', '=', 'UID'),
            ], limit=1)

        return uid_line.value if uid_line else False

    # =====================================================================
    # OAN ID Generation — Farmer Code + Farmer Name based
    # =====================================================================
    @staticmethod
    def _slugify(text):
        """Turn a free-text name into an uppercase, hyphen-separated token
        safe for use inside a record reference (e.g. 'Abebe Kebede' ->
        'ABEBE-KEBEDE')."""
        text = (text or '').strip().upper()
        text = re.sub(r'[^A-Z0-9]+', '-', text)
        text = re.sub(r'-{2,}', '-', text).strip('-')
        return text or 'FARMER'

    def _generate_oan_id(self, vals, batch_counters):
        """Build the OAN ID from the Farmer Code (Farmer ID) and Farmer's
        FIRST NAME only, e.g. FR-1234567890-ABEBE-001, instead of a plain
        running sequence. Falls back to the old OAN-<year>-###### sequence
        only if no farmer information is available on the record yet.

        NOTE (shortened per demo feedback): previously the FULL farmer
        name was slugified into the ID (e.g. FR-1234567890-ABEBE-KEBEDE-001,
        or FR-1234567890-MESSI-MESSI-002 when first/last name repeat).
        Only the first name is now used, to keep the OAN ID shorter while
        still tying it back to the farmer code. If the team prefers
        initials instead (e.g. FR-1234567890-AK-001) or wants the name
        dropped entirely (e.g. FR-1234567890-001), update the
        `first_name_token` line below.
        """
        farmer_code = (vals.get('farmer_id') or '').strip().upper()

        farmer_name = False
        if vals.get('owner_id'):
            partner = self.env['res.partner'].browse(vals['owner_id'])
            farmer_name = partner.name
        elif farmer_code:
            partner = self.env['res.partner'].search(
                [('farmer_id', '=', farmer_code)], limit=1
            )
            farmer_name = partner.name if partner else False

        if not (farmer_code and farmer_name):
            return self.env['ir.sequence'].next_by_code(
                'g2p.livestock.registry'
            ) or _('New')

        first_name_token = (farmer_name or '').strip().split(' ')[0]
        base = "%s-%s" % (farmer_code, self._slugify(first_name_token))

        # How many records already exist (or were already generated earlier
        # in this same batch) for this farmer, so each animal gets its own
        # running number: ...-001, ...-002, etc.
        existing = self.search_count([('name', 'like', base + '-%')])
        seq = batch_counters.get(base, existing) + 1
        batch_counters[base] = seq

        return "%s-%03d" % (base, seq)

    # =====================================================================
    # Display Name
    # =====================================================================
    @api.depends('name', 'ear_tag_id', 'species_id', 'breed', 'owner_id')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.name or _('New')]
            if rec.ear_tag_id:
                parts.append(rec.ear_tag_id)
            if rec.species_id:
                parts.append(rec.species_id.name)
            if rec.breed:
                parts.append(rec.breed)
            label = ' - '.join(parts)
            if rec.owner_id:
                label += _(' (Owner: %s)') % rec.owner_id.name
            rec.display_name = label

    # =====================================================================
    # Onchange Methods
    # =====================================================================
    @api.onchange('farmer_id')
    def _onchange_farmer_id(self):
        if not self.farmer_id:
            self.owner_id = False
            self.region_id = self.zone_id = self.woreda_id = self.kebele_id = False
            return

        # Auto-format
        fid = self.farmer_id.strip().upper()
        if not fid.startswith('FR-'):
            fid = 'FR-' + re.sub(r'\D', '', fid)
            self.farmer_id = fid

        partner = self.env['res.partner'].search(
            [('farmer_id', '=', fid)], limit=1
        )

        if partner:
            self.owner_id = partner
            self.region_id = partner.region
            self.zone_id = partner.zone
            self.woreda_id = partner.woreda
            self.kebele_id = partner.kebele
            self.fayda_id = self._get_fayda_id_for_partner(partner)
        else:
            self.owner_id = False
            self.region_id = self.zone_id = self.woreda_id = self.kebele_id = False
            self.fayda_id = False
            return {
                'warning': {
                    'title': _('Partner Not Found'),
                    'message': _('No farmer found with Farmer ID %s.') % fid,
                }
            }

    @api.onchange('owner_id')
    def _onchange_owner_id(self):
        if self.owner_id:
            self.farmer_id = self.owner_id.farmer_id
            self.region_id = self.owner_id.region
            self.zone_id = self.owner_id.zone
            self.woreda_id = self.owner_id.woreda
            self.kebele_id = self.owner_id.kebele
            self.fayda_id = self._get_fayda_id_for_partner(self.owner_id)
        else:
            self.region_id = self.zone_id = self.woreda_id = self.kebele_id = False
            self.fayda_id = False

    # =====================================================================
    # Constraints & CRUD
    # =====================================================================
    CRITICAL_FIELDS = ('ear_tag_id', 'species_id')

    _sql_constraints = [
        ('ear_tag_species_owner_uniq', 'unique(ear_tag_id, species_id, owner_id)',
         'Duplicate Ear Tag for this species and owner already exists!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        # Track how many OAN IDs we've generated per farmer within this same
        # create() call, so a multi-record batch save doesn't produce
        # duplicate sequence numbers before earlier records are committed.
        batch_counters = {}

        for vals in vals_list:
            # Farmer ID logic (resolved first, so name generation below has
            # the farmer name/code available)
            if vals.get('farmer_id'):
                partner = self.env['res.partner'].search(
                    [('farmer_id', '=', vals['farmer_id'].strip())], limit=1
                )
                if partner:
                    vals['owner_id'] = partner.id
                    vals['region_id'] = partner.region.id if partner.region else False
                    vals['zone_id'] = partner.zone.id if partner.zone else False
                    vals['woreda_id'] = partner.woreda.id if partner.woreda else False
                    vals['kebele_id'] = partner.kebele.id if partner.kebele else False
                    vals['fayda_id'] = self._get_fayda_id_for_partner(partner)
            elif vals.get('owner_id'):
                partner = self.env['res.partner'].browse(vals['owner_id'])
                if partner.farmer_id:
                    vals['farmer_id'] = partner.farmer_id
                vals['region_id'] = partner.region.id if partner.region else False
                vals['zone_id'] = partner.zone.id if partner.zone else False
                vals['woreda_id'] = partner.woreda.id if partner.woreda else False
                vals['kebele_id'] = partner.kebele.id if partner.kebele else False
                vals['fayda_id'] = self._get_fayda_id_for_partner(partner)

            if not vals.get('name') or vals.get('name') == _('New'):
                vals['name'] = self._generate_oan_id(vals, batch_counters)

            if 'count_measure' not in vals:
                vals['count_measure'] = 1

        records = super().create(vals_list)

        # Safe audit log call
        for rec in records or []:  # <-- Added safety
            try:
                rec._create_audit_log('create', {})
            except Exception:
                pass  # Don't let audit log break the save

        return records

    def write(self, vals):
        self._check_rbac_write(vals)
        self._check_critical_field_lock(vals)

        # Farmer ID logic
        if vals.get('farmer_id'):
            partner = self.env['res.partner'].search(
                [('farmer_id', '=', vals['farmer_id'].strip())], limit=1
            )
            if partner:
                vals['owner_id'] = partner.id
                vals.update({
                    'region_id': partner.region.id if partner.region else False,
                    'zone_id': partner.zone.id if partner.zone else False,
                    'woreda_id': partner.woreda.id if partner.woreda else False,
                    'kebele_id': partner.kebele.id if partner.kebele else False,
                    'fayda_id': self._get_fayda_id_for_partner(partner),
                })
            else:
                vals.update({
                    'owner_id': False,
                    'region_id': False,
                    'zone_id': False,
                    'woreda_id': False,
                    'kebele_id': False,
                    'fayda_id': False,
                })
        elif vals.get('owner_id'):
            partner = self.env['res.partner'].browse(vals['owner_id'])
            if partner.farmer_id:
                vals['farmer_id'] = partner.farmer_id
            vals.update({
                'region_id': partner.region.id if partner.region else False,
                'zone_id': partner.zone.id if partner.zone else False,
                'woreda_id': partner.woreda.id if partner.woreda else False,
                'kebele_id': partner.kebele.id if partner.kebele else False,
                'fayda_id': self._get_fayda_id_for_partner(partner),
            })
        elif 'owner_id' in vals and not vals.get('owner_id'):
            vals.update({
                'farmer_id': False,
                'region_id': False,
                'zone_id': False,
                'woreda_id': False,
                'kebele_id': False,
                'fayda_id': False,
            })

        if vals.get('state'):
            vals['state_date'] = fields.Date.today()
            vals['approval_reminder_sent'] = False

        res = super().write(vals)

        # Safe audit log
        for rec in self or []:  # <-- Added safety
            try:
                rec._create_audit_log('update', vals)
            except Exception:
                pass

        return res

    def unlink(self):
        is_federal_admin = self.env.user.has_group('g2p_livestock_registry.group_livestock_federal_admin')
        if not is_federal_admin:
            raise AccessError(_("Only Federal Admin may permanently delete livestock records. Use Archive instead."))
        for rec in self:
            rec._create_audit_log('delete', {'name': rec.name, 'ear_tag_id': rec.ear_tag_id})
        return super().unlink()

    def _check_rbac_write(self, vals):
        if self.env.su:
            return

        user = self.env.user
        if user.has_group('g2p_livestock_registry.group_livestock_federal_admin'):
            return
        is_regional_vet = user.has_group('g2p_livestock_registry.group_livestock_regional_vet')
        is_field_officer = user.has_group('g2p_livestock_registry.group_livestock_field_officer')
        if not (is_regional_vet or is_field_officer):
            raise AccessError(_("You do not have permission to modify livestock records."))

    def _check_critical_field_lock(self, vals):
        touched_critical = [f for f in self.CRITICAL_FIELDS if f in vals]
        if not touched_critical:
            return
        is_federal_admin = self.env.user.has_group('g2p_livestock_registry.group_livestock_federal_admin')
        if is_federal_admin:
            return
        for rec in self:
            if rec.state == 'verified':
                raise ValidationError(
                    _("Cannot change %(fields)s on a verified record (%(name)s) without Federal Admin authorization.") % {
                        'fields': ', '.join(touched_critical),
                        'name': rec.name,
                    })

    # =====================================================================
    # Hierarchical Approval Workflow — Kebele -> Woreda -> Zone -> Region
    # =====================================================================
    # Each level must approve in order before the next level can act. The
    # approving user must (a) belong to the security group for that level,
    # and (b) have their own location (on their linked res.partner, the
    # same 'region'/'zone'/'woreda'/'kebele' fields used elsewhere in this
    # module for RBAC) match the record's location at that level — unless
    # they are Federal Admin, who can approve at any level/location.
    _APPROVAL_LEVELS = {
        # level: (record field, partner field, group xmlid, next state, label)
        'kebele': ('kebele_id', 'kebele',
                   'g2p_livestock_registry.group_livestock_kebele_approver',
                   'kebele_approved', 'Kebele'),
        'woreda': ('woreda_id', 'woreda',
                   'g2p_livestock_registry.group_livestock_woreda_approver',
                   'woreda_approved', 'Woreda'),
        'zone': ('zone_id', 'zone',
                 'g2p_livestock_registry.group_livestock_zone_approver',
                 'zone_approved', 'Zone'),
        'region': ('region_id', 'region',
                   'g2p_livestock_registry.group_livestock_region_approver',
                   'verified', 'Region'),
    }

    _APPROVAL_ORDER = ['kebele', 'woreda', 'zone', 'region']
    # The state a record must currently be in for each level to act on it.
    _APPROVAL_REQUIRED_STATE = {
        'kebele': 'draft',
        'woreda': 'kebele_approved',
        'zone': 'woreda_approved',
        'region': 'zone_approved',
    }

    def _check_approver(self, level):
        rec_field, partner_field, group_xmlid, _next_state, label = self._APPROVAL_LEVELS[level]
        user = self.env.user
        if user.has_group('g2p_livestock_registry.group_livestock_federal_admin'):
            return
        if not user.has_group(group_xmlid):
            raise AccessError(_("You do not have permission to give %s approval.") % label)
        user_partner = user.partner_id
        user_location = user_partner[partner_field] if user_partner else False
        for rec in self:
            rec_location = rec[rec_field]
            if user_location and rec_location and user_location != rec_location:
                raise AccessError(
                    _("You may only give %(level)s approval for records within your own assigned %(level)s.")
                    % {'level': label}
                )

    def _action_approve_level(self, level):
        rec_field, partner_field, group_xmlid, next_state, label = self._APPROVAL_LEVELS[level]
        required_state = self._APPROVAL_REQUIRED_STATE[level]
        for rec in self:
            if rec.state != required_state:
                raise UserError(
                    _("This record must be in '%(required)s' status before it can receive %(level)s approval "
                      "(currently: '%(current)s').") % {
                        'required': dict(rec._fields['state'].selection).get(required_state),
                        'level': label,
                        'current': dict(rec._fields['state'].selection).get(rec.state),
                    }
                )
        self._check_approver(level)
        self.write({'state': next_state})

    def action_approve_kebele(self):
        self._action_approve_level('kebele')

    def action_approve_woreda(self):
        self._action_approve_level('woreda')

    def action_approve_zone(self):
        self._action_approve_level('zone')

    def action_approve_region(self):
        """Final level of approval — moves the record to 'verified'."""
        self._action_approve_level('region')

    def action_reject_to_draft(self):
        """Send a record back to Draft from any approval stage, e.g. if a
        higher level finds an issue. Available to Federal Admin and to any
        of the 4 approver groups."""
        user = self.env.user
        allowed_groups = [
            'g2p_livestock_registry.group_livestock_federal_admin',
            'g2p_livestock_registry.group_livestock_kebele_approver',
            'g2p_livestock_registry.group_livestock_woreda_approver',
            'g2p_livestock_registry.group_livestock_zone_approver',
            'g2p_livestock_registry.group_livestock_region_approver',
        ]
        if not any(user.has_group(g) for g in allowed_groups):
            raise AccessError(_("You do not have permission to reject this record back to Draft."))
        self.write({'state': 'draft'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_archive_record(self):
        self.write({'state': 'archived'})

    def action_unarchive_record(self):
        self.write({'state': 'draft'})

    # =====================================================================
    # AUTOMATIC EMAIL REMINDERS — Approval Pending Too Long
    # =====================================================================
    # Maps the CURRENT state to the group/location-field that should approve
    # it NEXT, so we know who to notify when a record has been sitting there
    # too long. Mirrors the scoping already used in livestock_record_rules.xml.
    _APPROVAL_REMINDER_MAP = {
        'draft': ('group_livestock_kebele_approver', 'kebele_id', 'kebele'),
        'kebele_approved': ('group_livestock_woreda_approver', 'woreda_id', 'woreda'),
        'woreda_approved': ('group_livestock_zone_approver', 'zone_id', 'zone'),
        'zone_approved': ('group_livestock_region_approver', 'region_id', 'region'),
    }

    def _get_pending_approval_recipients(self):
        """Return the res.users recordset who can approve this record at its
        CURRENT stage, scoped to the same kebele/woreda/zone/region as the
        record (falls back to nobody if the record or the approver's
        location isn't set, since that's exactly how the record rules scope
        access too)."""
        self.ensure_one()
        mapping = self._APPROVAL_REMINDER_MAP.get(self.state)
        if not mapping:
            return self.env['res.users']
        group_xmlid, location_field, partner_location_field = mapping
        location = self[location_field]
        if not location:
            return self.env['res.users']

        group = self.env.ref('g2p_livestock_registry.%s' % group_xmlid, raise_if_not_found=False)
        if not group:
            return self.env['res.users']

        return group.users.filtered(
            lambda u: u.partner_id[partner_location_field] == location and u.email
        )

    @api.model
    def _cron_send_approval_pending_reminders(self, stuck_after_days=3):
        """Daily cron: emails the appropriate approver (Kebele/Woreda/Zone/
        Region, matched by location) when a record has been sitting at the
        same approval stage for too long without moving forward."""
        today = fields.Date.today()
        cutoff = fields.Date.subtract(today, days=stuck_after_days)

        template = self.env.ref(
            'g2p_livestock_registry.mail_template_approval_pending', raise_if_not_found=False)
        if not template:
            return

        stuck_records = self.search([
            ('state', 'in', list(self._APPROVAL_REMINDER_MAP.keys())),
            ('state_date', '<=', cutoff),
            ('approval_reminder_sent', '=', False),
        ])

        for rec in stuck_records:
            recipients = rec._get_pending_approval_recipients()
            if recipients:
                template.send_mail(rec.id, force_send=True, email_values={
                    'email_to': ','.join(recipients.mapped('email')),
                })
            rec.sudo().approval_reminder_sent = True

    # =====================================================================
    # Audit Logging
    # =====================================================================
    def _create_audit_log(self, action_type, vals):
        if not self or (not vals and action_type not in ('create', 'delete')):
            return

        AuditModel = self.env['g2p.livestock.audit.log']

        for rec in self:
            changes = {}
            if action_type == 'update':
                for field_name, new_value in list(vals.items()):
                    old_value = rec[field_name] if hasattr(rec, field_name) else False
                    if old_value != new_value:
                        changes[field_name] = {'old': str(old_value), 'new': str(new_value)}

            if changes or action_type in ('create', 'delete'):
                AuditModel.sudo().create({
                    'res_model': 'g2p.livestock.registry',
                    'res_id': rec.id,
                    'user_id': self.env.uid,
                    'user_role': self._get_user_role_label(),
                    'action_type': action_type,
                    'changes': json.dumps(changes, default=str),
                    'timestamp': fields.Datetime.now(),
                    'ip_address': self.env.context.get('ip_address', ''),
                    'session_id': self.env.context.get('session_id', ''),
                })

    def _get_user_role_label(self):
        user = self.env.user
        if user.has_group('g2p_livestock_registry.group_livestock_federal_admin'):
            return 'Federal Admin'
        if user.has_group('g2p_livestock_registry.group_livestock_regional_vet'):
            return 'Regional Vet Officer'
        if user.has_group('g2p_livestock_registry.group_livestock_field_officer'):
            return 'Field Officer'
        if user.has_group('g2p_livestock_registry.group_livestock_data_entry_clerk'):
            return 'Data Entry Clerk'
        if user.has_group('g2p_livestock_registry.group_livestock_auditor'):
            return 'Auditor'
        return 'Unknown'


class ResPartner(models.Model):
    _inherit = 'res.partner'



    livestock_registry_ids = fields.One2many(
        'g2p.livestock.registry',
        'owner_id',
        string='Livestock Registries'
    )
