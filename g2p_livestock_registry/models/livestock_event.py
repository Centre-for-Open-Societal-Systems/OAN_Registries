import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


# Shared selection list used for the "Location" field across Health Events,
# Vital Events, and Breeding Events, so users pick from a fixed set of
# options instead of free-typing a location.
LOCATION_SELECTION = [
    ('home', 'Home / Farm'),
    ('veterinary', 'Hospital / Veterinary Clinic'),
    ('market', 'Market'),
    ('field', 'Field / Grazing Area'),
    ('quarantine_center', 'Quarantine Center'),
    ('other', 'Other'),
]


class G2PLivestockHealthEvent(models.Model):
    _name = 'g2p.livestock.health.event'
    _description = 'Health Event'
    _order = 'date_onset desc'

    livestock_id = fields.Many2one('g2p.livestock.registry', required=True, ondelete='cascade')

    # NEW FIELD — links to a specific animal line within the registry
    line_id = fields.Many2one(
        'g2p.livestock.registry.line',
        string='Animal (Ear Tag)',
        domain="[('registry_id', '=', livestock_id)]",
        ondelete='set null',
    )

    # Convenience readonly field to display the ear tag directly
    ear_tag_id = fields.Char(
        string='Ear Tag',
        related='line_id.ear_tag_id',
        readonly=True,
        store=True,
    )

    event_type = fields.Selection([
        ('disease', 'Disease'),
        ('injury', 'Injury'),
        ('treatment', 'Treatment'),
        ('recovery', 'Recovery'),
    ], required=True)

    disease_type = fields.Char(string='Disease Type')
    date_onset = fields.Date(string='Date of Onset')
    date_resolution = fields.Date(string='Date of Resolution')
    treatment = fields.Text(string='Treatment Administered')
    veterinarian_id = fields.Many2one('res.partner', string='Veterinarian / Officer')
    location = fields.Selection(LOCATION_SELECTION, string='Location')
    location_details = fields.Char(
        string='Location Details',
        help="Exact location (e.g. specific home/farm address, hospital/clinic name, "
             "market name). Fill in after choosing the Location category above."
    )
    notes = fields.Text()

    # LR-06: outbreak detection for notifiable diseases
    is_notifiable = fields.Boolean(string='Notifiable Disease', default=False)

    @api.constrains('event_type', 'disease_type')
    def _check_disease_type_required(self):
        """Disease Type / Diagnosis is only meaningful for 'Disease' events.
        Enforced at the model level too, not just hidden in the UI, so bulk
        imports and API ingestion (LR-16 to LR-19) can't bypass this."""
        for rec in self:
            if rec.event_type == 'disease' and not (rec.disease_type or '').strip():
                raise ValidationError(_(
                    "Disease Type / Diagnosis is required for a 'Disease' health event."
                ))

    @api.model_create_multi
    def create(self, vals_list):
        skip_dup_check = self.env.context.get('skip_vital_event_duplicate_check')
        if not skip_dup_check:
            seen_in_batch = set()
            for vals in vals_list:
                self._check_duplicate_health_event(vals, seen_in_batch)
        records = super().create(vals_list)
        records._sync_health_status()
        records._check_outbreak()
        return records

    def _check_duplicate_health_event(self, vals, seen_in_batch):
        line_id = vals.get('line_id')
        event_type = vals.get('event_type')
        disease_type = (vals.get('disease_type') or '').strip().lower()
        date_onset = vals.get('date_onset')
        if not (line_id and event_type):
            return

        batch_key = (line_id, event_type, disease_type, date_onset)
        if batch_key in seen_in_batch:
            raise ValidationError(_(
                "You're trying to add two identical '%(event)s' events (same Disease Type "
                "and Date of Onset) for this animal in the same save. Please remove the "
                "duplicate line."
            ) % {'event': event_type})

        seen_in_batch.add(batch_key)

        domain = [
            ('line_id', '=', line_id),
            ('event_type', '=', event_type),
            ('disease_type', '=ilike', disease_type),
            ('date_onset', '=', date_onset),
        ]
        if self.search_count(domain):
            raise ValidationError(_(
                "A '%(event)s' event with the same Disease Type ('%(disease)s') and Date of "
                "Onset already exists for this animal. Please check the existing entry instead "
                "of creating a duplicate."
            ) % {'event': event_type, 'disease': disease_type or _('(blank)')})

    def _sync_health_status(self):
        """LR-06 / LR-11: health status auto-updates from disease/injury/recovery events."""
        for rec in self:
            if not rec.line_id:
                continue
            if rec.event_type in ('disease', 'injury'):
                rec.line_id.health_status = 'sick'
            elif rec.event_type == 'recovery':
                rec.line_id.health_status = 'healthy'

    def _get_outbreak_alert_recipients(self):
        """Notify the Woreda Approver(s) for the affected woreda, plus any
        Regional Vet Officer(s) covering that region — matching the same
        location-scoping already used by the record rules."""
        self.ensure_one()
        registry = self.livestock_id
        recipients = self.env['res.users']

        woreda_group = self.env.ref(
            'g2p_livestock_registry.group_livestock_woreda_approver', raise_if_not_found=False)
        if woreda_group and registry.woreda_id:
            recipients |= woreda_group.users.filtered(
                lambda u: u.partner_id.woreda == registry.woreda_id and u.email
            )

        vet_group = self.env.ref(
            'g2p_livestock_registry.group_livestock_regional_vet', raise_if_not_found=False)
        if vet_group and registry.region_id:
            recipients |= vet_group.users.filtered(
                lambda u: u.partner_id.region == registry.region_id and u.email
            )

        return recipients

    def _check_outbreak(self):
        """LR-06/LR-11: flag a simple outbreak signal..."""
        for rec in self:
            if not (rec.is_notifiable and rec.disease_type and rec.livestock_id.woreda_id):
                continue
            window_start = fields.Date.subtract(rec.date_onset or fields.Date.today(), days=14)
            related = self.search([
                ('disease_type', '=', rec.disease_type),
                ('is_notifiable', '=', True),
                ('livestock_id.woreda_id', '=', rec.livestock_id.woreda_id.id),
                ('date_onset', '>=', window_start),
            ])
            if len(related) >= 3:
                self.env['mail.activity'].create({
                    'res_model_id': self.env['ir.model']._get_id('g2p.livestock.health.event'),
                    'res_id': rec.id,
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': _('Possible disease outbreak: %s in %s') % (
                        rec.disease_type, rec.livestock_id.woreda_id.name),
                    'note': _('%s notifiable disease cases recorded for "%s" in this woreda in the last 14 days.')
                            % (len(related), rec.disease_type),
                    'user_id': self.env.ref('base.user_admin').id if self.env.ref(
                        'base.user_admin', raise_if_not_found=False) else self.env.uid,
                })

                template = self.env.ref(
                    'g2p_livestock_registry.mail_template_outbreak_alert', raise_if_not_found=False)
                recipients = rec._get_outbreak_alert_recipients()
                if template and recipients:
                    template.send_mail(rec.id, force_send=True, email_values={
                        'email_to': ','.join(recipients.mapped('email')),
                    })


class G2PLivestockVaccination(models.Model):
    _name = 'g2p.livestock.vaccination'
    _description = 'Vaccination Record'
    _order = 'vaccination_date desc'

    livestock_id = fields.Many2one('g2p.livestock.registry', required=True, ondelete='cascade')

    line_id = fields.Many2one(
        'g2p.livestock.registry.line',
        string='Animal (Ear Tag)',
        domain="[('registry_id', '=', livestock_id)]",
        ondelete='set null',
    )

    ear_tag_id = fields.Char(
        string='Ear Tag',
        related='line_id.ear_tag_id',
        readonly=True,
        store=True,
    )

    # Updated: Now related to the new relational field
    line_species_id = fields.Many2one(
        'g2p.livestock.type',
        related='line_id.species_id',
        string='Species (internal)',
        readonly=True,
        store=True
    )

    vaccine_type = fields.Many2one('g2p.livestock.vaccine.schedule', string='Vaccine Type/Name', required=True,
                                   help="Pick from the configured Vaccine Schedule list...")

    vaccination_date = fields.Date(default=fields.Date.today, required=True)
    administering_user_id = fields.Many2one('res.users', default=lambda self: self.env.user,
                                            string='Administering Authority')
    batch_number = fields.Char(string='Batch/Lot Number')
    next_due_date = fields.Date(string='Next Due Date', store=True, readonly=True, copy=False)
    notes = fields.Text()

    # Reminder tracking — prevents sending the same email every day
    due_soon_reminder_sent = fields.Boolean(default=False, copy=False)
    overdue_reminder_sent = fields.Boolean(default=False, copy=False)

    _sql_constraints = [
        ('vaccination_uniq', 'unique(line_id, vaccination_date, vaccine_type)',
         'This animal already has a vaccination record with the same Vaccine Type on the same date.'),
    ]

    def _get_schedule_interval_days(self, vaccine_schedule, species_id):
        """Updated to work with species_id (Many2one)"""
        if not vaccine_schedule:
            return False
        # If schedule is species-specific
        if vaccine_schedule.species_id and vaccine_schedule.species_id == species_id:
            return vaccine_schedule.interval_days
        if not vaccine_schedule.species_id:
            matching = self.env['g2p.livestock.vaccine.schedule'].search([
                ('vaccine_name', '=', vaccine_schedule.vaccine_name),
                ('species_id', '=', species_id.id if species_id else False),
                ('active', '=', True),
            ], limit=1)
            return matching.interval_days if matching else vaccine_schedule.interval_days
        return vaccine_schedule.interval_days

    def _safe_add_days(self, value, days):
        if not value:
            return False
        if isinstance(value, str):
            value = fields.Date.to_date(value)
        return fields.Date.add(value, days=days)

    @api.onchange('vaccine_type', 'vaccination_date', 'line_id')
    def _onchange_compute_next_due_date(self):
        for rec in self:
            if rec.vaccination_date and rec.vaccine_type:
                species_id = rec.line_id.species_id if rec.line_id else False
                interval = rec._get_schedule_interval_days(rec.vaccine_type, species_id)
                rec.next_due_date = rec._safe_add_days(rec.vaccination_date, interval) if interval else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('vaccination_date') and vals.get('vaccine_type'):
                line = self.env['g2p.livestock.registry.line'].browse(vals.get('line_id'))
                schedule = self.env['g2p.livestock.vaccine.schedule'].browse(vals['vaccine_type'])
                interval = self._get_schedule_interval_days(schedule, line.species_id)
                if interval:
                    vals['next_due_date'] = self._safe_add_days(vals['vaccination_date'], interval)

        records = super().create(vals_list)
        for rec in records:
            if rec.line_id:
                rec.line_id.vaccination_status = 'up_to_date'
        return records

    def write(self, vals):
        res = super().write(vals)
        # If the due date moves (re-vaccinated, corrected, etc.), reset the
        # reminder flags so the new date gets its own due-soon/overdue email.
        if 'next_due_date' in vals or 'vaccination_date' in vals or 'vaccine_type' in vals:
            self.write({'due_soon_reminder_sent': False, 'overdue_reminder_sent': False})
        return res

    @api.model
    def _cron_flag_overdue_vaccinations(self):
        today = fields.Date.today()
        Line = self.env['g2p.livestock.registry.line']
        candidates = Line.search([
            ('vaccination_status', '=', 'up_to_date'),
            ('state', '!=', 'archived'),
        ])
        for line in candidates:
            last_vacc = self.search([('line_id', '=', line.id)],
                                    order='vaccination_date desc', limit=1)
            if last_vacc and last_vacc.next_due_date and last_vacc.next_due_date < today:
                line.vaccination_status = 'overdue'

    # =========================================================================
    # AUTOMATIC EMAIL REMINDERS (Vaccination Due / Overdue)
    # =========================================================================
    @api.model
    def _cron_send_vaccination_reminders(self, due_soon_window_days=3):
        """Daily cron: emails the user who logged the vaccination
        (administering_user_id) when it's coming due soon, and again once
        it becomes overdue. Each email is sent only once per due date,
        tracked via due_soon_reminder_sent / overdue_reminder_sent."""
        today = fields.Date.today()
        due_soon_cutoff = fields.Date.add(today, days=due_soon_window_days)

        due_soon_template = self.env.ref(
            'g2p_livestock_registry.mail_template_vaccination_due_soon', raise_if_not_found=False)
        overdue_template = self.env.ref(
            'g2p_livestock_registry.mail_template_vaccination_overdue', raise_if_not_found=False)

        # --- Due soon (next_due_date within the next N days, not yet due/overdue) ---
        due_soon_records = self.search([
            ('next_due_date', '>=', today),
            ('next_due_date', '<=', due_soon_cutoff),
            ('due_soon_reminder_sent', '=', False),
            ('administering_user_id.email', '!=', False),
        ])
        for rec in due_soon_records:
            if due_soon_template:
                due_soon_template.send_mail(rec.id, force_send=True, email_values={
                    'email_to': rec.administering_user_id.email,
                })
            rec.due_soon_reminder_sent = True

        # --- Overdue (next_due_date already in the past) ---
        overdue_records = self.search([
            ('next_due_date', '<', today),
            ('overdue_reminder_sent', '=', False),
            ('administering_user_id.email', '!=', False),
        ])
        for rec in overdue_records:
            if overdue_template:
                overdue_template.send_mail(rec.id, force_send=True, email_values={
                    'email_to': rec.administering_user_id.email,
                })
            rec.overdue_reminder_sent = True


class G2PLivestockVitalEvent(models.Model):
    _name = 'g2p.livestock.vital.event'
    _description = 'Vital Events'
    _order = 'date desc'

    livestock_id = fields.Many2one('g2p.livestock.registry', required=True, ondelete='cascade')

    line_id = fields.Many2one(
        'g2p.livestock.registry.line',
        string='Animal (Ear Tag)',
        domain="[('registry_id', '=', livestock_id)]",
        ondelete='set null',
    )

    ear_tag_id = fields.Char(
        string='Ear Tag',
        related='line_id.ear_tag_id',
        readonly=True,
        store=True,
    )

    event_type = fields.Selection([
        ('birth', 'Birth'), ('mortality', 'Mortality'), ('disease', 'Disease')
    ], required=True)

    date = fields.Date(required=True, default=fields.Date.today)
    cause = fields.Selection([
        ('disease', 'Disease'), ('accident', 'Accident'),
        ('predation', 'Predation'), ('slaughter', 'Slaughter'), ('unknown', 'Unknown'),
    ], string='Cause of Event')

    location = fields.Selection(LOCATION_SELECTION, string='Location')
    location_details = fields.Char(
        string='Location Details',
        help="Exact location (e.g. specific home/farm address, hospital/clinic name, "
             "market name). Fill in after choosing the Location category above."
    )
    notes = fields.Text()

    # --- Disease-event specific fields (mirrors Health Event, so a Disease
    # Vital Event captures the same clinical detail in one place) ---
    disease_type = fields.Char(string='Disease Type / Diagnosis')
    date_onset = fields.Date(string='Date of Onset')
    date_resolution = fields.Date(string='Date of Resolution')
    treatment = fields.Text(string='Treatment Administered')
    veterinarian_id = fields.Many2one('res.partner', string='Attending Veterinarian')
    is_notifiable = fields.Boolean(string='Notifiable Disease', default=False)

    # Internal link to the Health Event record auto-created for this
    # disease case, so both stay in sync and outbreak detection (which
    # runs off Health Events) still picks this up. Not shown on the form —
    # purely internal bookkeeping.
    linked_health_event_id = fields.Many2one(
        'g2p.livestock.health.event',
        string='Linked Health Event',
        readonly=True,
        copy=False,
    )

    # --- Birth-event specific fields ---
    offspring_count = fields.Integer(string='Number of Offspring', default=1)
    offspring_ear_tag_prefix = fields.Char(string='New Ear Tag(s) Prefix')
    created_offspring_ids = fields.Many2many('g2p.livestock.registry.line', string='Created Offspring Profiles',
                                             readonly=True, copy=False)
    reporting_officer_id = fields.Many2one('res.users', string='Reporting Officer',
                                           default=lambda self: self.env.user)

    @api.constrains('line_id', 'event_type', 'disease_type', 'date', 'date_onset')
    def _check_duplicate_vital_event(self):
        for rec in self:
            if not (rec.line_id and rec.event_type):
                continue
            if rec.event_type == 'mortality':
                conflicting = self.search([
                    ('id', '!=', rec.id),
                    ('line_id', '=', rec.line_id.id),
                    ('event_type', '=', 'mortality'),
                ])
                if conflicting:
                    raise ValidationError(_("A Mortality event already exists for this animal."))
            elif rec.event_type == 'disease':
                disease_type = (rec.disease_type or '').strip()
                onset = rec.date_onset or rec.date
                conflicting = self.search([
                    ('id', '!=', rec.id),
                    ('line_id', '=', rec.line_id.id),
                    ('event_type', '=', 'disease'),
                    ('disease_type', '=ilike', disease_type),
                    '|',
                        ('date_onset', '=', onset),
                        '&', ('date_onset', '=', False), ('date', '=', onset),
                ])
                if conflicting:
                    raise ValidationError(_(
                        "A Disease event with the same Disease Type ('%s') and Date of Onset "
                        "already exists for this animal.") % (disease_type or _('(blank)')))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.event_type == 'mortality' and rec.line_id:
                rec.line_id.health_status = 'deceased'
            elif rec.event_type == 'birth':
                rec._create_offspring_profiles()
            elif rec.event_type == 'disease' and rec.line_id:
                rec.line_id.health_status = 'sick'
                rec._sync_linked_health_event()
        return records

    def write(self, vals):
        res = super().write(vals)
        disease_relevant_fields = {
            'event_type', 'disease_type', 'date_onset', 'date_resolution',
            'treatment', 'veterinarian_id', 'location', 'location_details',
            'line_id', 'is_notifiable',
        }
        if disease_relevant_fields & set(vals.keys()):
            for rec in self:
                if rec.event_type == 'disease':
                    rec._sync_linked_health_event()
        return res

    def _sync_linked_health_event(self):
        """LR-06/LR-11 fix: a Vital Event of type 'Disease' must produce (or
        keep updated) a matching Health Event, so the case appears in the
        clinical history and is picked up by outbreak detection — instead
        of the two models tracking the same disease independently."""
        self.ensure_one()
        if self.event_type != 'disease' or not self.line_id:
            return

        health_vals = {
            'livestock_id': self.livestock_id.id,
            'line_id': self.line_id.id,
            'event_type': 'disease',
            'disease_type': self.disease_type,
            'date_onset': self.date_onset or self.date,
            'date_resolution': self.date_resolution,
            'treatment': self.treatment,
            'veterinarian_id': self.veterinarian_id.id if self.veterinarian_id else False,
            'location': self.location,
            'location_details': self.location_details,
            'is_notifiable': self.is_notifiable,
            'notes': _('Auto-synced from Vital Event #%s (Disease).') % self.id,
        }

        HealthEvent = self.env['g2p.livestock.health.event']
        if self.linked_health_event_id:
            # Write directly (bypass duplicate-check, since this is the
            # same case being kept in sync, not a new duplicate entry).
            self.linked_health_event_id.sudo().write(health_vals)
        else:
            health_event = HealthEvent.sudo().with_context(
                skip_vital_event_duplicate_check=True
            ).create(health_vals)
            self.linked_health_event_id = health_event.id

    def unlink(self):
        linked = self.mapped('linked_health_event_id')
        res = super().unlink()
        if linked:
            linked.sudo().unlink()
        return res

    def _generate_next_ear_tag(self, prefix=None, used_tags=None):
        """Build the next available Ear Tag ID in the required format:
        'ET' followed by exactly 10 digits (e.g. ET0000000013).

        Any prefix the user types (e.g. "ET") is normalized; only "ET" is
        a valid country code under the current standard, so it's forced
        to "ET" regardless of what was typed, and the numeric part is
        auto-generated so the result always passes the ear_tag_id format
        constraint on g2p.livestock.registry.line.
        """
        Line = self.env['g2p.livestock.registry.line']
        used_tags = used_tags or set()

        max_num = 0
        # Look at existing tags already in the database...
        existing_tags = Line.search([('ear_tag_id', 'like', 'ET')]).mapped('ear_tag_id')
        # ...plus any tags already generated earlier in this same batch
        # (not yet saved to the DB when creating multiple offspring at once).
        for tag in list(existing_tags) + list(used_tags):
            match = re.match(r'^ET(\d{10})$', (tag or '').strip().upper())
            if match:
                max_num = max(max_num, int(match.group(1)))

        return 'ET%s' % str(max_num + 1).zfill(10)

    def _create_offspring_profiles(self):
        self.ensure_one()
        if not self.line_id:
            raise ValidationError(_("This Birth event isn't linked to a specific animal (the mother)."))

        Line = self.env['g2p.livestock.registry.line']
        dam = self.line_id
        count = max(self.offspring_count or 1, 1)
        new_lines = self.env['g2p.livestock.registry.line']
        used_tags = set()

        for i in range(count):
            ear_tag = self._generate_next_ear_tag(self.offspring_ear_tag_prefix, used_tags)
            used_tags.add(ear_tag)

            vals = {
                'registry_id': dam.registry_id.id,
                'ear_tag_id': ear_tag,
                'species_id': dam.species_id.id,  # Updated
                'breed': dam.breed,
                'owner_id': dam.owner_id.id,
                'date_of_birth': self.date,
                'registration_date': self.date,
                'health_status': 'healthy',
                'vaccination_status': 'none',
                'state': 'draft',
            }
            new_lines |= Line.create(vals)

        self.created_offspring_ids = [(6, 0, new_lines.ids)]
        return new_lines


class G2PLivestockBreeding(models.Model):
    _name = 'g2p.livestock.breeding'
    _description = 'Breeding & Artificial Insemination Events'
    _order = 'breeding_date desc'

    livestock_id = fields.Many2one('g2p.livestock.registry', required=True, ondelete='cascade')

    line_id = fields.Many2one(
        'g2p.livestock.registry.line',
        string='Animal (Ear Tag)',
        domain="[('registry_id', '=', livestock_id), ('gender', '=', 'female')]",
        ondelete='set null',
        help="Only female animals are shown — Breeding/AI events are recorded "
             "against the dam. The sire is captured separately below.",
    )

    ear_tag_id = fields.Char(
        string='Ear Tag',
        related='line_id.ear_tag_id',
        readonly=True,
        store=True,
    )

    event_type = fields.Selection([
        ('natural', 'Natural Breeding'), ('ai', 'Artificial Insemination')
    ], required=True)

    # Natural breeding
    sire_or_semen_id = fields.Char(string='Sire / Semen Source')
    location = fields.Selection(LOCATION_SELECTION, string='Location')
    location_details = fields.Char(
        string='Location Details',
        help="Exact location (e.g. specific home/farm address, hospital/clinic name, "
             "market name). Fill in after choosing the Location category above."
    )

    # AI-specific
    ai_technician_id = fields.Many2one('res.partner', string='AI Technician')
    ai_technique = fields.Char(string='Technique Used')
    semen_batch_number = fields.Char(string='Semen Batch Number')

    breeding_date = fields.Date(required=True, default=fields.Date.today)
    expected_calving_date = fields.Date(
        string='Expected Calving Date',
        help="Enter manually based on the animal's species/breed gestation period. "
             "Not auto-calculated, since gestation length varies by species and breed.",
    )
    pregnancy_confirmed = fields.Boolean(string='Pregnancy Confirmed', default=False)
    pregnancy_confirmation_date = fields.Date(string='Pregnancy Confirmation Date')
    outcome = fields.Selection([
        ('pending', 'Pending'), ('successful', 'Successful'), ('failed', 'Failed')
    ], default='pending')
    notes = fields.Text()

    # Reminder tracking — prevents sending the same calving reminder every day
    calving_reminder_sent = fields.Boolean(default=False, copy=False)

    @api.constrains('line_id', 'breeding_date', 'event_type')
    def _check_duplicate_breeding_event(self):
        """LR-12/LR-13: prevent duplicate breeding events for the same animal
        within the same cycle — applies to both Natural Breeding and AI."""
        for rec in self:
            if not rec.line_id:
                continue
            window_start = fields.Date.subtract(rec.breeding_date, days=21)
            window_end = fields.Date.add(rec.breeding_date, days=21)
            conflicting = self.search([
                ('id', '!=', rec.id),
                ('line_id', '=', rec.line_id.id),
                ('event_type', '=', rec.event_type),
                ('breeding_date', '>=', window_start),
                ('breeding_date', '<=', window_end),
            ])
            if conflicting:
                label = _('AI') if rec.event_type == 'ai' else _('Natural Breeding')
                raise ValidationError(_(
                    "Another %(type)s event already exists for this animal within the same "
                    "breeding cycle (%(date)s)."
                ) % {'type': label, 'date': conflicting[0].breeding_date})

    def action_confirm_pregnancy(self):
        self.write({
            'pregnancy_confirmed': True,
            'pregnancy_confirmation_date': fields.Date.today(),
            'outcome': 'successful',
        })

    def action_mark_failed(self):
        self.write({'outcome': 'failed', 'pregnancy_confirmed': False})

    def write(self, vals):
        res = super().write(vals)
        # If the expected calving date moves or the outcome changes away
        # from "pending", reset the reminder flag so the reminder logic
        # re-evaluates cleanly (e.g. a corrected date gets its own reminder;
        # a resolved outcome stops being reminded about).
        if 'expected_calving_date' in vals or 'breeding_date' in vals or 'outcome' in vals:
            self.write({'calving_reminder_sent': False})
        return res

    # =====================================================================
    # AUTOMATIC EMAIL REMINDERS — Upcoming Calving
    # =====================================================================
    @api.model
    def _cron_send_calving_reminders(self, window_days=7):
        """Daily cron: emails the user who logged the breeding record when
        the expected calving date is coming up soon, so they can be ready
        to record the birth/mortality outcome. Only applies while the
        pregnancy outcome is still 'pending'."""
        today = fields.Date.today()
        cutoff = fields.Date.add(today, days=window_days)

        template = self.env.ref(
            'g2p_livestock_registry.mail_template_calving_reminder', raise_if_not_found=False)
        if not template:
            return

        due_soon = self.search([
            ('outcome', '=', 'pending'),
            ('expected_calving_date', '>=', today),
            ('expected_calving_date', '<=', cutoff),
            ('calving_reminder_sent', '=', False),
            ('create_uid.email', '!=', False),
        ])
        for rec in due_soon:
            template.send_mail(rec.id, force_send=True, email_values={
                'email_to': rec.create_uid.email,
            })
            rec.calving_reminder_sent = True
