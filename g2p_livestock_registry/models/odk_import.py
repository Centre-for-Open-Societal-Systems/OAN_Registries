from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import jq
import logging
import traceback

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JQ Mapping: flattens ODK nested repeats into registry-level keys.
# Events carry `ear_tag_id` as a string reference so we can resolve
# it to a `line_id` (Many2one) AFTER the animal lines exist in Odoo.
# ---------------------------------------------------------------------------
LIVESTOCK_MAPPING_QUERY = """
{
  "fayda_id": .fayda_id,
  "owner_id": .owner_id,
  "region_id": .region_id,
  "zone_id": .zone_id,
  "woreda_id": .woreda_id,
  "kebele_id": .kebele_id,
  "line_ids": (
    .livestock // []
    | map({
        "ear_tag_id": .ear_tag_id,
        "species_id": .species_id,
        "breed": .breed,
        "gender": .gender,
        "weight": .weight,
        "health_status": .health_status,
        "vaccination_status": .vaccination_status,
        "date_of_birth": .date_of_birth,
        "registration_date": .registration_date
    })
  ),
  "health_event_ids": (
    (
      [ .livestock[]? | .ear_tag_id as $ear | (.health_events // .health_tab // .health // .disease_details // .health_event // [])[]? | {
          "ear_tag_id": (.ear_tag_id // $ear),
          "event_type": (.health_event_type // .event_type // .type),
          "disease_type": (.disease_type // .disease // .illness),
          "date_onset": (.date_onset // .date_of_onset // .date),
          "date_resolution": (.date_resolution // .date_of_resolution),
          "is_notifiable": ((.is_notifiable // null) == "yes"),
          "treatment": (.treatment // .treatment_administered),
          "veterinarian_id": (.veterinarian_id // .veterinarian // .officer_id // .officer),
          "location": .location,
          "location_details": .location_details,
          "notes": (.health_event_notes // .notes // .details)
      } ]
    ) + (
      [ (.health_events // .health_tab // .health // .health_event // .health_events_repeat // [])[]? | {
          "ear_tag_id": (.ear_tag_id // .animal_tag // .animal_ear_tag // .ear_tag // .tag),
          "event_type": (.health_event_type // .event_type // .type),
          "disease_type": (.disease_type // .disease // .illness),
          "date_onset": (.date_onset // .date_of_onset // .date),
          "date_resolution": (.date_resolution // .date_of_resolution),
          "is_notifiable": ((.is_notifiable // null) == "yes"),
          "treatment": (.treatment // .treatment_administered),
          "veterinarian_id": (.veterinarian_id // .veterinarian // .officer_id // .officer),
          "location": .location,
          "location_details": .location_details,
          "notes": (.health_event_notes // .notes // .details)
      } ]
    )
  ),
  "vaccination_ids": (
    (
      [ .livestock[]? | .ear_tag_id as $ear | .species_id as $species | (.vaccinations // .vaccination_tab // .vaccine_tab // [])[]? | {
          "ear_tag_id": (.ear_tag_id // $ear),
          "species_id": $species,
          "vaccination_date": (.vaccination_date // .date),
          "batch_number": .batch_number,
          "notes": (.vaccination_notes // .notes // .details)
      } ]
    ) + (
      [ (.vaccinations // .vaccination_tab // .vaccine_tab // [])[]? | {
          "ear_tag_id": (.ear_tag_id // .animal_tag // .animal_ear_tag // .ear_tag // .tag),
          "species_id": .species_id,
          "vaccination_date": (.vaccination_date // .date),
          "batch_number": .batch_number,
          "notes": (.vaccination_notes // .notes // .details)
      } ]
    )
  ),
  "vital_event_ids": (
    (
      [ .livestock[]? | .ear_tag_id as $ear | (.vital_events // .vital_tab // .vitals // [])[]? | {
          "ear_tag_id": (.ear_tag_id // $ear),
          "event_type": (.vital_event_type // .event_type // .type),
          "date": (.date // .vital_event_date // .event_date),
          "location": .location,
          "location_details": .location_details,
          "reporting_officer_id": (.reporting_officer_id // .reporting_officer // .officer_id // .officer),
          "notes": (.vital_event_details // .notes // .details),
          "offspring_count": (.birth_details.offspring_count // .offspring_count),
          "offspring_ear_tag_prefix": (.birth_details.offspring_ear_tag_prefix // .offspring_ear_tag_prefix),
          "disease_type": (.disease_details.disease_type // null),
          "treatment": (.disease_details.treatment // null),
          "veterinarian_id": (.disease_details.veterinarian_id // null),
          "is_notifiable": ((.disease_details.is_notifiable // null) == "yes"),
          "cause": .cause
      } ]
    ) + (
      [ (.vital_events // .vital_tab // .vitals // [])[]? | {
          "ear_tag_id": (.ear_tag_id // .animal_tag // .animal_ear_tag // .ear_tag // .tag),
          "event_type": (.vital_event_type // .event_type // .type),
          "date": (.date // .vital_event_date // .event_date),
          "location": .location,
          "location_details": .location_details,
          "reporting_officer_id": (.reporting_officer_id // .reporting_officer // .officer_id // .officer),
          "notes": (.vital_event_details // .notes // .details),
          "offspring_count": (.birth_details.offspring_count // .offspring_count),
          "offspring_ear_tag_prefix": (.birth_details.offspring_ear_tag_prefix // .offspring_ear_tag_prefix),
          "disease_type": (.disease_details.disease_type // null),
          "treatment": (.disease_details.treatment // null),
          "veterinarian_id": (.disease_details.veterinarian_id // null),
          "is_notifiable": ((.disease_details.is_notifiable // null) == "yes"),
          "cause": .cause
      } ]
    )
  ),
  "breeding_ids": (
    (
      [ .livestock[]? | .ear_tag_id as $ear | (.breeding_events // .breeding_tab // .breeding // .breeding_event // [])[]? | {
          "ear_tag_id": (.ear_tag_id // $ear),
          "event_type": (.breeding_event_type // .breeding_type // .event_type // .type),
          "breeding_date": (.breeding_date // .date),
          "location": .location,
          "location_details": .location_details,
          "sire_or_semen_id": (.sire_or_semen_id // .artificial_insemination_tab.semen_batch_number // .sire_id),
          "expected_calving_date": (.expected_calving_date // .expected_calving_date_calc),
          "notes": (.breeding_notes // .notes),
          "ai_technician_id": (.artificial_insemination_tab.ai_technician_id // .ai_technician_id // .veterinarian_id // null),
          "ai_technique": (.artificial_insemination_tab.ai_technique // .ai_technique // null),
          "semen_batch_number": (.artificial_insemination_tab.semen_batch_number // .semen_batch_number // null)
      } ]
    ) + (
      [ (.breeding_events // .breeding_tab // .breeding // .breeding_event // [])[]? | {
          "ear_tag_id": (.ear_tag_id // .animal_tag // .animal_ear_tag // .ear_tag // .tag),
          "event_type": (.breeding_event_type // .breeding_type // .event_type // .type),
          "breeding_date": (.breeding_date // .date),
          "location": .location,
          "location_details": .location_details,
          "sire_or_semen_id": (.sire_or_semen_id // .artificial_insemination_tab.semen_batch_number // .sire_id),
          "expected_calving_date": (.expected_calving_date // .expected_calving_date_calc),
          "notes": (.breeding_notes // .notes),
          "ai_technician_id": (.artificial_insemination_tab.ai_technician_id // .ai_technician_id // .veterinarian_id // null),
          "ai_technique": (.artificial_insemination_tab.ai_technique // .ai_technique // null),
          "semen_batch_number": (.artificial_insemination_tab.semen_batch_number // .semen_batch_number // null)
      } ]
    )
  ),
  "notes": (
    [ .livestock[]? | (.notes_tab // .notes // [])[]? | .notes ] | join("\\n")
  )
}
"""


class OdkImport(models.Model):
    _inherit = 'odk.import'

    target_registry = fields.Selection(
        selection_add=[
            ('g2p.livestock.registry', 'Livestock Registry'),
        ],
        ondelete={
            'g2p.livestock.registry': 'cascade',
        },
    )

    def process_records(self, instance_id=None, last_sync_time=None):
        """
        Main entry point for ODK imports.
        Overrides the base odk.import to process livestock registry records.
        """
        if self.target_registry == 'g2p.livestock.registry':
            _logger.info("Processing Livestock Registry records for target: %s", self.target_registry)
            return self._process_livestock_registry_records(instance_id, last_sync_time)
        else:
            return super().process_records(instance_id=instance_id, last_sync_time=last_sync_time)

    # =====================================================================
    # MAIN IMPORT PIPELINE
    # =====================================================================
    def _process_livestock_registry_records(self, instance_id=None, last_sync_time=None):
        """
        Two-pass import pipeline:
          Pass 1  – Create/update registry + animal lines (line_ids).
          Pass 2  – Resolve ear_tag_id → line_id for each event, auto-match
                    vaccine_type by species, then write events to the registry.
        """
        if not self.odk_config:
            raise ValidationError(_("Please configure the ODK."))

        data = self.odk_config.download_records(instance_id=instance_id, last_sync_time=last_sync_time)
        if not data or "value" not in data:
            _logger.warning("No data returned from ODK for Livestock Registry")
            return {}

        success_count = 0
        failed_count = 0

        EVENT_FIELDS = ['health_event_ids', 'vaccination_ids', 'vital_event_ids', 'breeding_ids']

        for member in data["value"]:
            try:
                with self.env.cr.savepoint():
                    # ---- 1. JQ mapping ----
                    mapped_json = jq.compile(LIVESTOCK_MAPPING_QUERY).input(member).first()
                    mapped_json = self._clean_odk_data(mapped_json)

                    _logger.info("=== ODK RAW MEMBER ===: %s", member)
                    _logger.info("=== JQ MAPPED JSON ===: %s", mapped_json)

                    if not mapped_json:
                        continue

                    # ---- 2. Farmer resolution ----
                    mapped_json = self._resolve_farmer(mapped_json)

                    # ---- 3. Separate events from registry+lines ----
                    events_data = {}
                    for ef in EVENT_FIELDS:
                        events_data[ef] = mapped_json.pop(ef, []) or []
                    notes_text = mapped_json.pop('notes', '')

                    # ---- PASS 1: Registry + Animal Lines ----
                    registry = self._pass1_registry_and_lines(mapped_json)
                    _logger.info("PASS 1 complete — registry id=%s, lines=%s",
                                 registry.id, registry.line_ids.mapped('ear_tag_id'))

                    # ---- PASS 2: Events (health, vaccination, vital, breeding, notes) ----
                    self._pass2_events(registry, events_data, notes_text)
                    _logger.info("PASS 2 complete — events written for registry id=%s", registry.id)

                    self.env.flush_all()
                    success_count += 1

            except Exception as e:
                _logger.error(
                    "Failed to process livestock record %s: %s\n%s",
                    member.get('instanceId', 'Unknown'), str(e), traceback.format_exc()
                )
                failed_count += 1

        data.update({
            "partner_count": success_count,
            "skipped_count": failed_count,
            "form_updated": bool(success_count > 0)
        })
        return data

    # =====================================================================
    # PASS 1 — Registry + Animal Lines
    # =====================================================================
    def _pass1_registry_and_lines(self, mapped_json):
        """Create or update the livestock registry and its animal lines."""
        line_data = mapped_json.pop('line_ids', []) or []

        # Resolve M2O string values (region_id, zone_id, etc.) on the registry
        registry_vals = self._map_m2o_fields_recursive('g2p.livestock.registry', dict(mapped_json))

        # Remove keys that are not actual model fields
        for key in list(registry_vals.keys()):
            if key not in self.env['g2p.livestock.registry']._fields:
                registry_vals.pop(key)

        owner_id = registry_vals.get('owner_id')
        if owner_id:
            owner = self.env['res.partner'].sudo().browse(owner_id)
            if owner.exists():
                loc_updates = {}
                if registry_vals.get('region_id') and not owner.region:
                    loc_updates['region'] = registry_vals['region_id']
                if registry_vals.get('zone_id') and not owner.zone:
                    loc_updates['zone'] = registry_vals['zone_id']
                if registry_vals.get('woreda_id') and not owner.woreda:
                    loc_updates['woreda'] = registry_vals['woreda_id']
                if registry_vals.get('kebele_id'):
                    loc_updates['kebele'] = registry_vals['kebele_id']
                if loc_updates:
                    owner.write(loc_updates)
                    _logger.info("Updated partner %s location fields: %s", owner.name, loc_updates)

        RegistryModel = self.env['g2p.livestock.registry'].sudo()
        registry = RegistryModel.search([('owner_id', '=', owner_id)], limit=1)

        if not registry:
            registry = RegistryModel.create(registry_vals)
            _logger.info("Created new registry id=%s for owner_id=%s", registry.id, owner_id)
        else:
            # Update registry-level fields (region, zone, kebele, etc.) but not lines yet
            safe_vals = {k: v for k, v in registry_vals.items() if k != 'owner_id'}
            if safe_vals:
                registry.write(safe_vals)
            _logger.info("Updated existing registry id=%s", registry.id)

        # Force write kebele_id explicitly in case model overrides cleared it
        if registry_vals.get('kebele_id') and registry.kebele_id.id != registry_vals['kebele_id']:
            registry.write({'kebele_id': registry_vals['kebele_id']})

        # --- Create/update animal lines ---
        LineModel = self.env['g2p.livestock.registry.line'].sudo()
        for line_dict in line_data:
            if not isinstance(line_dict, dict):
                continue

            # Resolve M2O fields on the line (species_id string → integer ID)
            line_dict = self._map_m2o_fields_recursive('g2p.livestock.registry.line', dict(line_dict))

            ear_tag = line_dict.get('ear_tag_id')
            if not ear_tag:
                _logger.warning("Skipping animal line with no ear_tag_id")
                continue

            # Remove invalid keys that aren't actual model fields
            clean_vals = {}
            for k, v in line_dict.items():
                if k in LineModel._fields:
                    clean_vals[k] = v

            # Search GLOBALLY for existing line by ear_tag_id (matches the
            # unique constraint ear_tag_species_owner_uniq on ear_tag + species + owner).
            # The animal may already exist in another registry for the same farmer.
            search_domain = [('ear_tag_id', '=ilike', ear_tag)]
            species_id = clean_vals.get('species_id')
            if species_id:
                search_domain.append(('species_id', '=', species_id))

            existing_line = LineModel.search(search_domain, limit=1)

            if existing_line:
                # If the line exists but in a different registry, move it here
                if existing_line.registry_id.id != registry.id:
                    existing_line.write({'registry_id': registry.id})
                    _logger.info("Moved existing animal line id=%s ear_tag=%s to registry id=%s",
                                 existing_line.id, ear_tag, registry.id)

                clean_vals.pop('ear_tag_id', None)  # don't update the tag itself
                clean_vals.pop('registry_id', None)
                if clean_vals:
                    existing_line.write(clean_vals)
                _logger.info("Updated existing animal line id=%s ear_tag=%s", existing_line.id, ear_tag)
            else:
                clean_vals['registry_id'] = registry.id
                LineModel.create(clean_vals)
                _logger.info("Created new animal line ear_tag=%s in registry id=%s", ear_tag, registry.id)

        return registry

    # =====================================================================
    # PASS 2 — Events (Health, Vaccination, Vital, Breeding, Notes)
    # =====================================================================
    def _pass2_events(self, registry, events_data, notes_text):
        """
        For each event list, resolve ear_tag_id → line_id, then create the
        event records directly (not via registry.write) to avoid issues with
        related/readonly fields.
        """
        # Build a lookup map: ear_tag_id (upper) → line record
        tag_to_line = {}
        for line in registry.line_ids:
            if line.ear_tag_id:
                tag_to_line[line.ear_tag_id.strip().upper()] = line

        _logger.info("ear_tag lookup map: %s", {k: v.id for k, v in tag_to_line.items()})

        # --- Health Events ---
        self._create_events_for_model(
            model_name='g2p.livestock.health.event',
            events=events_data.get('health_event_ids', []),
            registry=registry,
            tag_to_line=tag_to_line,
        )

        # --- Vaccinations ---
        self._create_vaccination_events(
            events=events_data.get('vaccination_ids', []),
            registry=registry,
            tag_to_line=tag_to_line,
        )

        # --- Vital Events ---
        self._create_events_for_model(
            model_name='g2p.livestock.vital.event',
            events=events_data.get('vital_event_ids', []),
            registry=registry,
            tag_to_line=tag_to_line,
        )

        # --- Breeding Events ---
        self._create_events_for_model(
            model_name='g2p.livestock.breeding',
            events=events_data.get('breeding_ids', []),
            registry=registry,
            tag_to_line=tag_to_line,
        )

        # --- Notes ---
        if notes_text and str(notes_text).strip():
            existing_notes = registry.notes or ''
            if notes_text.strip() not in existing_notes:
                registry.write({'notes': (existing_notes + '\n' + notes_text).strip()})

    # =====================================================================
    # Generic event creator (Health, Vital, Breeding)
    # =====================================================================
    def _create_events_for_model(self, model_name, events, registry, tag_to_line):
        """Create event records, resolving ear_tag_id → line_id."""
        if not events:
            return

        Model = self.env[model_name].sudo()

        for evt in events:
            if not isinstance(evt, dict):
                continue

            try:
                with self.env.cr.savepoint():
                    # Resolve ear_tag_id → line_id
                    ear_tag = evt.pop('ear_tag_id', None)
                    line = self._resolve_line_from_ear_tag(ear_tag, tag_to_line)

                    if not line:
                        _logger.warning(
                            "Skipping %s event: no animal line found for ear_tag=%s in registry %s",
                            model_name, ear_tag, registry.id
                        )
                        continue

                    # --- Normalize event_type for specific event models ---
                    if model_name == 'g2p.livestock.breeding':
                        evt_type = str(evt.get('event_type', '')).lower().strip()
                        if 'ai' in evt_type or 'artificial' in evt_type or 'insemination' in evt_type:
                            evt['event_type'] = 'ai'
                        elif 'natural' in evt_type or 'breeding' in evt_type:
                            evt['event_type'] = 'natural'
                        elif not evt_type or evt_type in ('none', 'false', 'null', ''):
                            if evt.get('ai_technician_id') or evt.get('semen_batch_number') or evt.get('ai_technique'):
                                evt['event_type'] = 'ai'
                            else:
                                evt['event_type'] = 'natural'

                    elif model_name == 'g2p.livestock.vital.event':
                        evt_type = str(evt.get('event_type', '')).lower().strip()
                        if 'calv' in evt_type or 'birth' in evt_type:
                            evt['event_type'] = 'birth'
                        elif 'mort' in evt_type or 'death' in evt_type or 'die' in evt_type:
                            evt['event_type'] = 'mortality'
                        elif 'slaught' in evt_type:
                            evt['event_type'] = 'slaughter'
                        elif 'sale' in evt_type or 'transf' in evt_type:
                            evt['event_type'] = 'sale'
                        elif 'stray' in evt_type or 'lost' in evt_type:
                            evt['event_type'] = 'stray'

                    elif model_name == 'g2p.livestock.health.event':
                        evt_type = str(evt.get('event_type', '')).lower().strip()
                        if 'treat' in evt_type:
                            evt['event_type'] = 'treatment'
                        elif 'injur' in evt_type:
                            evt['event_type'] = 'injury'
                        elif 'recov' in evt_type:
                            evt['event_type'] = 'recovery'
                        elif 'diseas' in evt_type or 'ill' in evt_type:
                            evt['event_type'] = 'disease'
                        else:
                            if evt.get('treatment'):
                                evt['event_type'] = 'treatment'
                            else:
                                evt['event_type'] = 'disease'

                        if evt.get('event_type') == 'disease' and not (evt.get('disease_type') or '').strip():
                            evt['disease_type'] = 'General Illness'
                        
                        if not evt.get('date_onset'):
                            evt['date_onset'] = fields.Date.today()

                    # Clean the values
                    evt = self._map_m2o_fields_recursive(model_name, dict(evt))
                    clean_vals = {}
                    for k, v in evt.items():
                        if k in Model._fields and Model._fields[k].type != 'one2many':
                            # Skip related/computed readonly fields
                            field = Model._fields[k]
                            if getattr(field, 'related', None):
                                continue
                            clean_vals[k] = v

                    clean_vals['livestock_id'] = registry.id
                    clean_vals['line_id'] = line.id

                    # Validate location selection key
                    if 'location' in clean_vals and clean_vals['location'] not in ('home', 'veterinary', 'market', 'field', 'quarantine_center', 'other'):
                        clean_vals['location'] = 'field' if clean_vals['location'] else False

                    # Check if event record already exists for this animal line (upsert pattern)
                    existing = False
                    if model_name == 'g2p.livestock.vital.event':
                        domain = [('livestock_id', '=', registry.id), ('line_id', '=', line.id), ('event_type', '=', clean_vals.get('event_type'))]
                        if clean_vals.get('date'):
                            domain.append(('date', '=', clean_vals.get('date')))
                        existing = Model.search(domain, limit=1)
                    elif model_name == 'g2p.livestock.health.event':
                        domain = [('livestock_id', '=', registry.id), ('line_id', '=', line.id), ('event_type', '=', clean_vals.get('event_type'))]
                        if clean_vals.get('date_onset'):
                            domain.append(('date_onset', '=', clean_vals.get('date_onset')))
                        existing = Model.search(domain, limit=1)
                    elif model_name == 'g2p.livestock.breeding':
                        domain = [('livestock_id', '=', registry.id), ('line_id', '=', line.id), ('event_type', '=', clean_vals.get('event_type'))]
                        if clean_vals.get('breeding_date'):
                            domain.append(('breeding_date', '=', clean_vals.get('breeding_date')))
                        existing = Model.search(domain, limit=1)

                    if existing:
                        _logger.info("Updating existing %s id=%s: %s", model_name, existing.id, clean_vals)
                        existing.with_context(skip_vital_event_duplicate_check=True, skip_breeding_duplicate_check=True).write(clean_vals)
                    else:
                        _logger.info("Creating %s: %s", model_name, clean_vals)
                        Model.with_context(skip_vital_event_duplicate_check=True, skip_breeding_duplicate_check=True).create(clean_vals)

            except Exception as e:
                _logger.error(
                    "Failed to create %s event (ear_tag=%s): %s\n%s",
                    model_name, ear_tag, str(e), traceback.format_exc()
                )

    # =====================================================================
    # Vaccination-specific creator (auto-matches vaccine_type by species)
    # =====================================================================
    def _create_vaccination_events(self, events, registry, tag_to_line):
        """
        Create vaccination records. Automatically matches vaccine_type from
        existing Vaccine Schedules by looking up the animal's species.
        """
        if not events:
            return

        VaccModel = self.env['g2p.livestock.vaccination'].sudo()
        ScheduleModel = self.env['g2p.livestock.vaccine.schedule'].sudo()

        for evt in events:
            if not isinstance(evt, dict):
                continue

            try:
                with self.env.cr.savepoint():
                    # Resolve ear_tag_id → line_id
                    ear_tag = evt.pop('ear_tag_id', None)
                    # Remove species_id from event dict (it was only used for vaccine matching)
                    species_str = evt.pop('species_id', None)

                    line = self._resolve_line_from_ear_tag(ear_tag, tag_to_line)

                    if not line:
                        _logger.warning(
                            "Skipping vaccination: no animal line for ear_tag=%s in registry %s",
                            ear_tag, registry.id
                        )
                        continue

                    # Auto-match vaccine_type from Vaccine Schedules by the animal's species
                    species_id = line.species_id
                    vaccine_schedule = False
                    if species_id:
                        vaccine_schedule = ScheduleModel.search([
                            ('species_id', '=', species_id.id),
                            ('active', '=', True),
                        ], limit=1)

                    if not vaccine_schedule:
                        # Fallback: search for a generic (no species) schedule
                        vaccine_schedule = ScheduleModel.search([
                            ('species_id', '=', False),
                            ('active', '=', True),
                        ], limit=1)

                    if not vaccine_schedule:
                        # Last resort: create a generic "Unknown / ODK" schedule
                        vaccine_schedule = ScheduleModel.search([('vaccine_name', '=', 'Unknown / ODK')], limit=1)
                        if not vaccine_schedule:
                            vaccine_schedule = ScheduleModel.create({
                                'vaccine_name': 'Unknown / ODK',
                                'interval_days': 365,
                            })

                    _logger.info(
                        "Vaccination for ear_tag=%s (species=%s): matched vaccine_type=%s (%s)",
                        ear_tag, species_id.name if species_id else 'N/A',
                        vaccine_schedule.id, vaccine_schedule.vaccine_name
                    )

                    # Clean event vals
                    clean_vals = {}
                    for k, v in evt.items():
                        if k in VaccModel._fields:
                            field = VaccModel._fields[k]
                            if getattr(field, 'related', None):
                                continue
                            clean_vals[k] = v

                    clean_vals['livestock_id'] = registry.id
                    clean_vals['line_id'] = line.id
                    clean_vals['vaccine_type'] = vaccine_schedule.id

                    # Prevent duplicate key error if vaccination already exists for line+date+vaccine_type
                    v_date = clean_vals.get('vaccination_date')
                    existing_v = VaccModel.search([
                        ('line_id', '=', line.id),
                        ('vaccine_type', '=', vaccine_schedule.id),
                        ('vaccination_date', '=', v_date),
                    ], limit=1)
                    if existing_v:
                        _logger.info("Vaccination already exists for line_id=%s, updating record id=%s", line.id, existing_v.id)
                        existing_v.write(clean_vals)
                    else:
                        _logger.info("Creating vaccination: %s", clean_vals)
                        VaccModel.create(clean_vals)

            except Exception as e:
                _logger.error(
                    "Failed to create vaccination (ear_tag=%s): %s\n%s",
                    ear_tag, str(e), traceback.format_exc()
                )

    # =====================================================================
    # HELPERS
    # =====================================================================
    def _resolve_line_from_ear_tag(self, ear_tag, tag_to_line):
        """Look up an animal line from the tag_to_line map with fallback matching."""
        if not tag_to_line:
            return False

        if not ear_tag:
            if len(tag_to_line) == 1:
                return list(tag_to_line.values())[0]
            return False

        tag_str = str(ear_tag).strip().upper()
        if tag_str in tag_to_line:
            return tag_to_line[tag_str]

        for k, line_rec in tag_to_line.items():
            if tag_str in k or k in tag_str:
                return line_rec

        if len(tag_to_line) == 1:
            return list(tag_to_line.values())[0]

        return False

    def _clean_odk_data(self, data):
        """
        Recursively remove dictionary keys where the value is 'None', 'False', 'Null', or ''
        and map ODK string values to Odoo selection keys.
        Preserves Python booleans (True/False) — only strips STRING versions.
        """
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                if v is None:
                    continue
                # Preserve actual Python booleans
                if isinstance(v, bool):
                    cleaned[k] = v
                    continue
                if isinstance(v, str) and v.strip() in ('None', 'False', 'Null', ''):
                    continue
                cleaned_val = self._clean_odk_data(v)
                if cleaned_val is not None:
                    cleaned[k] = cleaned_val
            return cleaned
        elif isinstance(data, list):
            cleaned_list = []
            for item in data:
                if item is None:
                    continue
                if isinstance(item, bool):
                    cleaned_list.append(item)
                    continue
                if isinstance(item, str) and item.strip() in ('None', 'False', 'Null', ''):
                    continue
                cleaned_val = self._clean_odk_data(item)
                if cleaned_val is not None:
                    cleaned_list.append(cleaned_val)
            return cleaned_list
        else:
            if isinstance(data, str):
                s = data.strip().lower()
                # Location mappings
                if s in ('hospital', 'veterinary', 'clinic', 'veterinary_clinic'):
                    return 'veterinary'
                if s in ('field', 'grazing', 'grazing_area', 'field_grazing_area'):
                    return 'field'
                if s in ('home', 'farm', 'home_farm'):
                    return 'home'
                if s in ('market',):
                    return 'market'
                if s in ('quarantine', 'quarantine_center'):
                    return 'quarantine_center'
                if s in ('other',):
                    return 'other'
                # Species mappings
                if s in ('poultry', 'chicken', 'fowl', 'bird'):
                    return 'Chicken'
                if s in ('cow', 'bull', 'ox', 'cattle'):
                    return 'Cattle'
                if s in ('donkey', 'donkeys'):
                    return 'Donkey'
                if s in ('horse', 'horses'):
                    return 'Horse'
                if s in ('mule', 'mules'):
                    return 'Mule'
                if s in ('sheep', 'lamb'):
                    return 'Sheep'
                if s in ('goat', 'caprine'):
                    return 'Goat'
                if s in ('camel', 'camels'):
                    return 'Camel'
                # Breeding mappings
                if s in ('artificial_insemination', 'artificial_insemination_ai', 'ai'):
                    return 'ai'
                if s in ('natural_breeding', 'natural'):
                    return 'natural'
                # Vital event mappings
                if s in ('mortality', 'death', 'died'):
                    return 'mortality'
                if s in ('calving', 'birth'):
                    return 'birth'
                if s in ('lost', 'stray'):
                    return 'stray'
                if s in ('slaughter', 'slaughtered'):
                    return 'slaughter'
                if s in ('sale', 'transfer', 'sold'):
                    return 'sale'
            return data

    def _resolve_farmer(self, mapped_json):
        """
        Map fayda_id or owner_id to an existing res.partner.
        If the farmer doesn't exist, create a new registrant partner (with TEMP-{timestamp} format for farmer_id)
        and attach fayda_id as a g2p.reg.id record.
        """
        fayda_val = mapped_json.get('fayda_id')
        owner_val = mapped_json.get('owner_id')
        partner_obj = self.env['res.partner'].sudo()
        partner = partner_obj.browse()

        # 1. Search existing farmer by Fayda ID in g2p.reg.id or res.partner
        if fayda_val:
            clean_num = ''.join(c for c in str(fayda_val) if c.isdigit())
            possible_ids = [
                fayda_val,
                f"FAN-{clean_num}" if clean_num else fayda_val,
                f"FR-{clean_num}" if clean_num else fayda_val,
                f"TEMP-{clean_num}" if clean_num else fayda_val,
                clean_num
            ]
            possible_ids = [pid for pid in possible_ids if pid]

            reg_id_rec = self.env['g2p.reg.id'].sudo().search([
                ('value', 'in', possible_ids),
            ], limit=1)
            if reg_id_rec and reg_id_rec.partner_id:
                partner = reg_id_rec.partner_id

            if not partner:
                partner = partner_obj.search([
                    '|', '|', '|',
                    ('farmer_id', 'in', possible_ids),
                    ('unique_id', 'in', possible_ids),
                    ('ref', 'in', possible_ids),
                    ('name', 'in', possible_ids),
                ], limit=1)

        # 2. Fallback search by owner_val (name or farmer_id)
        if not partner and owner_val:
            if isinstance(owner_val, int):
                partner = partner_obj.search([('id', '=', owner_val)], limit=1)
            elif isinstance(owner_val, str) and owner_val.strip():
                owner_str = owner_val.strip()
                search_ids = [owner_str]
                if owner_str.startswith('FR-'):
                    search_ids.append(owner_str.replace('FR-', 'TEMP-', 1))
                elif owner_str.startswith('TEMP-'):
                    search_ids.append(owner_str.replace('TEMP-', 'FR-', 1))
                
                partner = partner_obj.search([
                    '|', '|',
                    ('farmer_id', 'in', search_ids),
                    ('name', '=ilike', owner_str),
                    ('ref', 'in', search_ids)
                ], limit=1)

        # 3. If farmer found, sync location, english name fields, and return
        if partner:
            mapped_json['owner_id'] = partner.id
            if not mapped_json.get('farmer_display_id'):
                mapped_json['farmer_display_id'] = partner.name

            # Populate English name fields on partner if missing
            if partner.name and not partner.given_name:
                name_parts = partner.name.split(maxsplit=2)
                write_vals = {}
                if len(name_parts) >= 1:
                    write_vals['given_name'] = name_parts[0]
                if len(name_parts) >= 2:
                    write_vals['family_name'] = name_parts[1]
                if len(name_parts) >= 3:
                    write_vals['gf_name_eng'] = name_parts[2]
                if write_vals:
                    partner.sudo().write(write_vals)

            # Check if Fayda ID is missing in mapped_json but exists on partner
            if partner.reg_ids and not fayda_val:
                uid_type = self.env['g2p.id.type'].sudo().search([('name', 'in', ['UID', 'Fayda', 'National ID'])], limit=1)
                if uid_type:
                    fayda_reg = partner.reg_ids.filtered(lambda r: r.id_type.id == uid_type.id)
                    if fayda_reg:
                        mapped_json['fayda_id'] = fayda_reg[0].value

            _logger.info("Matched existing farmer: '%s' (id=%s, farmer_id=%s)", partner.name, partner.id, partner.farmer_id)
            return mapped_json

        # 4. Farmer NOT Found: Create a new farmer with TEMP-{timestamp} ID format
        import time as _time
        temp_id = f"TEMP-{int(_time.time())}"

        farmer_name = mapped_json.get('farmer_display_id') or mapped_json.get('farmer_name') or (owner_val if isinstance(owner_val, str) else 'Unknown Farmer (Temp)')
        partner_vals = {
            'name': farmer_name,
            'is_farmer': 'yes',
            'farmer_id': temp_id,
            'ref': temp_id,
            'is_registrant': True,
            'is_group': False,
            'state': 'draft',
        }

        # Split farmer_name into English name fields
        name_parts = farmer_name.split(maxsplit=2)
        if len(name_parts) >= 1:
            partner_vals['given_name'] = name_parts[0]
        if len(name_parts) >= 2:
            partner_vals['family_name'] = name_parts[1]
        if len(name_parts) >= 3:
            partner_vals['gf_name_eng'] = name_parts[2]

        # Extract and assign Geo fields (Region, Zone, Woreda, Kebele)
        for field_name, odk_key, model_name in [
            ('region', 'region_display_id', 'g2p.region'),
            ('zone', 'zone_display_id', 'g2p.zone'),
            ('woreda', 'woreda_id', 'g2p.woreda'),
            ('kebele', 'kebele_id', 'g2p.kebele')
        ]:
            val = mapped_json.get(odk_key) or mapped_json.get(field_name + '_id') or mapped_json.get(field_name)
            if val:
                if isinstance(val, int):
                    partner_vals[field_name] = val
                elif isinstance(val, str) and val.strip() and val.strip().lower() not in ('none', 'false', 'null'):
                    val_str = val.strip()
                    comodel = self.env[model_name].sudo()
                    domain = ['|', ('code', '=ilike', val_str), ('name', '=ilike', val_str)] if 'code' in comodel._fields else [('name', '=ilike', val_str)]
                    rec = comodel.search(domain, limit=1)
                    if not rec and 'name' in comodel._fields:
                        domain_partial = [('name', '=ilike', f'%{val_str}%')]
                        rec = comodel.search(domain_partial, limit=1)
                    if rec:
                        partner_vals[field_name] = rec.id

        # Attach Fayda ID if available
        if fayda_val:
            id_type = self.env['g2p.id.type'].sudo().search([('name', 'in', ['UID', 'Fayda', 'National ID'])], limit=1)
            if not id_type:
                id_type = self.env['g2p.id.type'].sudo().search([], limit=1)
            if id_type:
                partner_vals['reg_ids'] = [(0, 0, {
                    'id_type': id_type.id,
                    'value': fayda_val,
                    'status': 'valid'
                })]

        new_partner = partner_obj.create(partner_vals)
        _logger.info("Created new farmer partner with temp ID: '%s' (id=%s, farmer_id=%s)", new_partner.name, new_partner.id, temp_id)

        mapped_json['owner_id'] = new_partner.id
        return mapped_json

    def _map_m2o_fields_recursive(self, model_name, data):
        """
        Recursively map string identifiers (from ODK) to Odoo Integer IDs for Many2one fields.
        Uses a multi-tier search strategy:
          1. Exact match on 'code' field
          2. Exact match on 'name' field (=ilike)
          3. Partial match on 'name' field (ilike, for 'Admin' → 'Administrator')
          4. For res.users: search by 'login' or 'partner_id.name'
        """
        if not isinstance(data, dict):
            return data

        if model_name not in self.env:
            return data
        model = self.env[model_name]

        for key, val in list(data.items()):
            field = model._fields.get(key)
            if not field:
                continue

            if field.type == 'many2one' and isinstance(val, str):
                v_str = val.strip()
                if v_str:
                    comodel = self.env[field.comodel_name].sudo()
                    rec = False

                    # Tier 1: exact match on 'code'
                    if 'code' in comodel._fields:
                        rec = comodel.search([('code', '=ilike', v_str)], limit=1)

                    # Tier 2: exact match on 'name'
                    if not rec and 'name' in comodel._fields:
                        rec = comodel.search([
                            '|', ('name', '=ilike', v_str),
                            ('name', '=ilike', v_str.replace('_', ' '))
                        ], limit=1)

                    # Tier 3: partial match on 'name' (for non-partner models, e.g. 'Admin' → 'Administrator')
                    if not rec and 'name' in comodel._fields and field.comodel_name != 'res.partner':
                        rec = comodel.search([('name', 'ilike', v_str)], limit=1)

                    # Tier 4: for res.users, search by 'login' or 'partner_id.name'
                    if not rec and field.comodel_name == 'res.users':
                        rec = comodel.search([
                            '|', ('login', 'ilike', v_str),
                            ('partner_id.name', 'ilike', v_str)
                        ], limit=1)

                    # Tier 5: for res.partner, try user login OR create a missing partner so veterinarian/technician names like "Vijay" are saved
                    if not rec and field.comodel_name == 'res.partner':
                        user = self.env['res.users'].sudo().search([
                            '|', ('login', 'ilike', v_str),
                            ('partner_id.name', 'ilike', v_str)
                        ], limit=1)
                        if user and user.partner_id:
                            rec = user.partner_id
                        else:
                            rec = comodel.create({'name': v_str})
                            _logger.info("Created missing partner for M2O %s.%s: '%s' → id=%s", model_name, key, v_str, rec.id)

                    # Tier 5.5: for g2p.kebele, auto-create missing kebele record so kebele is never lost
                    if not rec and field.comodel_name == 'g2p.kebele':
                        create_vals = {'name': v_str, 'code': v_str}
                        woreda_val = data.get('woreda_id')
                        if woreda_val and isinstance(woreda_val, int):
                            create_vals['woreda'] = woreda_val
                        rec = comodel.create(create_vals)
                        _logger.info("Auto-created missing kebele for M2O %s.%s: '%s' → id=%s", model_name, key, v_str, rec.id)

                    # Tier 5.6: for g2p.livestock.type (species), auto-create or match code/name so Chicken, Donkey, Horse, Mule work seamlessly
                    if not rec and field.comodel_name == 'g2p.livestock.type':
                        code_val = v_str.lower()
                        name_val = v_str.capitalize()
                        rec = comodel.search(['|', ('code', '=ilike', code_val), ('name', '=ilike', name_val)], limit=1)
                        if not rec:
                            rec = comodel.create({'name': name_val, 'code': code_val})
                            _logger.info("Auto-created missing species in g2p.livestock.type for '%s': code='%s' → id=%s", v_str, code_val, rec.id)

                    # Tier 6: for res.users, fallback to current environment user if no user was matched
                    if not rec and field.comodel_name == 'res.users':
                        rec = self.env.user
                        _logger.info("Fallback res.users for M2O %s.%s: '%s' → user id=%s", model_name, key, v_str, rec.id)

                    if rec:
                        data[key] = rec.id
                        _logger.info("M2O resolved: %s.%s '%s' → id=%s", model_name, key, v_str, rec.id)
                    else:
                        data[key] = False  # Clear invalid string to avoid DB constraint errors
                        _logger.warning("M2O not found: %s.%s '%s' → set to False", model_name, key, v_str)
                else:
                    data[key] = False

            elif field.type in ('one2many', 'many2many') and isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        self._map_m2o_fields_recursive(field.comodel_name, item)
                    elif isinstance(item, (list, tuple)) and len(item) == 3 and isinstance(item[2], dict):
                        self._map_m2o_fields_recursive(field.comodel_name, item[2])

        return data
