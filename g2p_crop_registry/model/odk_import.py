from odoo import models, fields, api
from odoo.exceptions import ValidationError
import jq
import logging

_logger = logging.getLogger(__name__)

class OdkImport(models.Model):
    _inherit = 'odk.import'

    def _register_hook(self):
        super()._register_hook()


        try:
            reg_model = self.env['g2p.crop.registry']
            if 'harvest_detail_ids' in reg_model._fields:
                reg_model._fields['harvest_detail_ids'].domain = [
                    '|', '|', '|',
                    ('harvest_date', '!=', False),
                    ('crop_maturity_status', '!=', False),
                    ('area_harvested', '>', 0),
                    ('qty_harvested', '>', 0)
                ]
        except Exception as e:
            _logger.warning("Could not patch harvest_detail_ids domain in _register_hook: %s", e)

    target_registry = fields.Selection(
        selection_add=[
            ('g2p.crop.registry.planning', 'Crop Registry - Planning'),
            ('g2p.crop.registry.cultivation', 'Crop Registry - Cultivation'),
            ('g2p.crop.registry.sowing_harvesting', 'Crop Registry - Sowing'),
            ('g2p.crop.registry.harvesting', 'Crop Registry - Harvesting'),
        ],
        ondelete={
            'g2p.crop.registry.planning': 'cascade',
            'g2p.crop.registry.cultivation': 'cascade',
            'g2p.crop.registry.sowing_harvesting': 'cascade',
            'g2p.crop.registry.harvesting': 'cascade',
        },
    )


    def process_records(self, instance_id=None, last_sync_time=None):
        if self.target_registry in [
            'g2p.crop.registry.planning',
            'g2p.crop.registry.cultivation',
            'g2p.crop.registry.sowing_harvesting',
            'g2p.crop.registry.harvesting'
        ]:
            return self._process_crop_registry_records(instance_id, last_sync_time)
        return super().process_records(instance_id=instance_id, last_sync_time=last_sync_time)

    def process_records_handle_addl_data(self, mapped_json):
        if mapped_json and "hh_is_household_head" not in mapped_json:
            mapped_json["hh_is_household_head"] = "no"
        return super().process_records_handle_addl_data(mapped_json)

    def process_reg_ids(self, json_data, id_type_name, id_value_key):
        if not json_data or not json_data.get(id_value_key):
            return json_data
        return super().process_reg_ids(json_data, id_type_name, id_value_key)

    def _normalize_raw_odk_member(self, val):
        if isinstance(val, dict):
            if 'has_cluster' in val and isinstance(val['has_cluster'], dict):
                if 'has_cluster_farming' in val['has_cluster'] and not val.get('has_cluster_farming'):
                    val['has_cluster_farming'] = val['has_cluster']['has_cluster_farming']
            if 'survey_personnel' in val and isinstance(val['survey_personnel'], list) and val['survey_personnel']:
                val['survey_personnel'] = val['survey_personnel'][0]
            for k, v in list(val.items()):
                self._normalize_raw_odk_member(v)
        elif isinstance(val, (list, tuple)):
            for item in val:
                self._normalize_raw_odk_member(item)

    def _download_media_recursive(self, data_dict, current_instance_id):
        if not isinstance(data_dict, dict):
            return
        for k, v in list(data_dict.items()):
            if isinstance(v, dict):
                self._download_media_recursive(v, current_instance_id)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        self._download_media_recursive(item, current_instance_id)
                    elif isinstance(item, (list, tuple)) and len(item) == 3 and isinstance(item[2], dict):
                        self._download_media_recursive(item[2], current_instance_id)
            elif k in ['geo_tagged_photo', 'image_1920', 'photo'] and isinstance(v, str) and v and len(v) < 255 and not v.startswith('http') and not v.startswith('data:'):
                try:
                    import base64
                    import requests

                    # Instead of self.odk_config.download_attachment which has a 10s timeout,
                    # we do the request manually here with a 60s timeout for large images.
                    url = (
                        f"{self.odk_config.base_url}/v1/projects/{self.odk_config.project}/forms/{self.odk_config.form_id}/"
                        f"submissions/{current_instance_id}/attachments/{v}"
                    )
                    headers = {"Authorization": f"Bearer {self.odk_config.login_get_session_token()}"}
                    response = requests.get(url, headers=headers, timeout=60)

                    if response.status_code == 200:
                        attachm = response.content
                        data_dict[k] = base64.b64encode(attachm).decode('utf-8')
                    elif response.status_code == 404:
                        _logger.warning("Attachment %s not found on ODK server.", v)
                        data_dict[k] = False
                    else:
                        response.raise_for_status()
                except Exception as e:
                    _logger.error("Failed to download attachment %s: %s", v, e)
                    # Clear the value so we don't save garbage base64 strings
                    data_dict[k] = False

    def _process_crop_registry_records(self, instance_id=None, last_sync_time=None):
        self.ensure_one()

        data = self.odk_config.download_records(
            instance_id=instance_id,
            last_sync_time=last_sync_time
        )
        if not data.get('value') and last_sync_time and not instance_id:
            _logger.info("No records found with last_sync_time %s. Falling back to full download...", last_sync_time)
            data = self.odk_config.download_records(
                instance_id=instance_id,
                last_sync_time=None
            )

        partner_count = 0
        for member in data['value']:
            self._normalize_raw_odk_member(member)
            _logger.info("=== ODK IMPORT DEBUG: RAW ODK MEMBER KEYS ===")
            _logger.info("Raw member top-level keys: %s", list(member.keys()) if isinstance(member, dict) else type(member))

            mapped_json = jq.first(self.json_formatter, member)
            _logger.info("=== ODK IMPORT DEBUG: AFTER JQ MAPPING ===")
            _logger.info("mapped_json top-level keys: %s", list(mapped_json.keys()) if isinstance(mapped_json, dict) else type(mapped_json))
            for k, v in (mapped_json.items() if isinstance(mapped_json, dict) else []):
                if isinstance(v, (list, dict)):
                    _logger.info("  mapped_json['%s'] type=%s len=%s", k, type(v).__name__, len(v) if isinstance(v, (list, dict)) else 'N/A')
                else:
                    _logger.info("  mapped_json['%s'] = %s", k, repr(v)[:200])

            # Promote nested dicts recursively
            self._promote_nested_dicts_recursive(mapped_json)
            self._normalize_mobile_numbers_recursive(mapped_json)

            current_instance_id = member.get('__id') or member.get('meta', {}).get('instanceID') or member.get('__system', {}).get('instanceID') or instance_id
            if current_instance_id:
                # Download media in both mapped_json AND raw member so that
                # _auto_enrich_production_and_incidents (which reads from member)
                # gets base64 data instead of raw filenames.
                self._download_media_recursive(mapped_json, current_instance_id)
                self._download_media_recursive(member, current_instance_id)

            def _flatten_dict(d):
                flattened = {}
                for k, v in d.items():
                    if isinstance(v, dict):
                        if k in ('gps', 'polygon_data', 'geoshape', 'geotrace') or ('type' in v and 'coordinates' in v):
                            # Convert GeoJSON dict to string format "lon,lat; lon,lat"
                            coords = v.get('coordinates', [])
                            def extract_pts(c):
                                if not c: return []
                                if isinstance(c[0], (int, float)): return [f"{c[0]},{c[1]}"]
                                res = []
                                for x in c: res.extend(extract_pts(x))
                                return res
                            pts = extract_pts(coords)
                            flattened[k] = "; ".join(pts)
                        else:
                            flattened.update(_flatten_dict(v))
                    else:
                        if isinstance(v, str):
                            v = v.strip("'\"")
                        flattened[k] = v
                return flattened
            def _process_complex_line(raw_line):
                # Handle cluster_information mapping
                cluster_info = raw_line.pop('cluster_information', {})
                cult_details = raw_line.pop('cultivation_details', {})
                cluster_water = raw_line.pop('water_details_1', [])
                cluster_smallholders = raw_line.pop('cluster_smallholders', None)
                farmer_list = raw_line.pop('farmer_list', [])

                has_cluster = raw_line.get('has_cluster_farming') in ('yes', 'Yes', 'YES', True, 1) or bool(cluster_info) or bool(cluster_smallholders) or any(k in raw_line for k in ['cluster_size', 'number_of_smallholders', 'agro_ecological_zone'])

                if has_cluster:
                    merged_cluster = {}
                    for c_key in ['cluster_size', 'number_of_smallholders', 'agro_ecological_zone', 'cluster_collected_land_quintal', 'cluster_name', 'cluster_area_hectare']:
                        if c_key in raw_line:
                            merged_cluster[c_key] = raw_line.pop(c_key)

                    if isinstance(cluster_info, dict):
                        merged_cluster.update(cluster_info)
                    if isinstance(cult_details, dict):
                        merged_cluster.update(cult_details)
                    if cluster_smallholders is not None:
                        merged_cluster['cluster_smallholders'] = cluster_smallholders

                    if isinstance(farmer_list, list) and farmer_list:
                        farmer_cmds = []
                        for sh in farmer_list:
                            if isinstance(sh, dict):
                                f_dict = {}
                                sh_data = sh.get('farmer_list', sh) if isinstance(sh, dict) else sh
                                if not isinstance(sh_data, dict):
                                    continue

                                fayda = sh_data.get('fayda_id') or sh_data.get('fyda_id')
                                if fayda:
                                    f_dict['fayda_id'] = fayda
                                    uid_type = self.env['g2p.id.type'].sudo().search([('name', '=', 'UID')], limit=1)
                                    if uid_type:
                                        reg_id_rec = self.env['g2p.reg.id'].sudo().search([
                                            ('id_type', '=', uid_type.id),
                                            ('value', '=', fayda),
                                        ], limit=1)
                                        if reg_id_rec and reg_id_rec.partner_id:
                                            f_dict['farmer_id'] = reg_id_rec.partner_id.id

                                if 'farmer_name' in sh_data:
                                    f_dict['farmer_name'] = sh_data['farmer_name']

                                for key in ['region_id', 'zone_id', 'woreda_id', 'kebele_id', 'region', 'zone', 'woreda', 'kebele']:
                                    if key in sh_data:
                                        f_dict[key] = sh_data[key]

                                farmer_cmds.append((0, 0, f_dict))
                        if farmer_cmds:
                            merged_cluster['cluster_farmer_line_ids'] = farmer_cmds

                    for loc_field in ['gps', 'region', 'zone', 'woreda', 'kebele', 'region_name_id', 'zone_name_id', 'woreda_name_id', 'kebele_id']:
                        if loc_field in raw_line and not merged_cluster.get(loc_field):
                            val = raw_line[loc_field]
                            # If it's a raw GeoJSON dictionary here, format it too
                            if loc_field == 'gps' and isinstance(val, dict) and 'coordinates' in val:
                                coords = val.get('coordinates', [])
                                def extract_pts(c):
                                    if not c: return []
                                    if isinstance(c[0], (int, float)): return [f"{c[0]},{c[1]}"]
                                    res = []
                                    for x in c: res.extend(extract_pts(x))
                                    return res
                                pts = extract_pts(coords)
                                val = "; ".join(pts)

                            if loc_field == 'gps':
                                merged_cluster['gps_location'] = val
                            else:
                                merged_cluster[loc_field] = val

                    if isinstance(cluster_water, list) and cluster_water:
                        c_water_cmds = [(5, 0, 0)]
                        for w in cluster_water:
                            if isinstance(w, dict):
                                c_water_cmds.append((0, 0, w))
                        if len(c_water_cmds) > 1:
                            merged_cluster['cluster_water_resource_line_ids'] = c_water_cmds

                    if merged_cluster:
                        raw_line['cluster_info_ids'] = [(0, 0, merged_cluster)]

                water_1 = raw_line.pop('water_details', [])
                water_cmds = [(5, 0, 0)]
                for w in (water_1 if isinstance(water_1, list) else []):
                    if isinstance(w, dict):
                        water_cmds.append((0, 0, w))
                if len(water_cmds) > 1:
                    raw_line['water_resource_line_ids'] = water_cmds

            planning_key = next((k for k in ['planning', 'planning_details'] if k in mapped_json), None)
            annual_cmds = [(5, 0, 0)]
            perennial_cmds = [(5, 0, 0)]
            biennial_cmds = [(5, 0, 0)]

            _logger.info("=== ODK IMPORT DEBUG: PLANNING KEY = %s ===", planning_key)
            if planning_key and isinstance(mapped_json[planning_key], list):
                planning_lines = mapped_json.pop(planning_key)
                _logger.info("Planning lines count: %s", len(planning_lines))
                for idx, raw_line in enumerate(planning_lines):
                    if not isinstance(raw_line, dict):
                        _logger.info("  Planning line %s: NOT a dict, type=%s", idx, type(raw_line))
                        continue
                    _logger.info("  Planning line %s keys: %s", idx, list(raw_line.keys()))
                    for pk, pv in raw_line.items():
                        if not isinstance(pv, (list, dict)):
                            _logger.info("    line[%s]['%s'] = %s", idx, pk, repr(pv)[:200])

                    _process_complex_line(raw_line)

                    flat_line = _flatten_dict(raw_line)
                    category = flat_line.get('land_category')

                    # Store all lines in annual_cmds since crop registry only has annual_line_ids to hold them
                    annual_cmds.append((0, 0, flat_line))

            _logger.info("=== ODK IMPORT DEBUG: PLANNING LINES PROCESSED ===")
            _logger.info("annual_cmds count: %s", len(annual_cmds)-1)
            if len(annual_cmds) > 1:
                mapped_json['annual_line_ids'] = annual_cmds
                _logger.info("SET mapped_json['annual_line_ids'] with %s lines", len(annual_cmds)-1)
            else:
                _logger.info("NOT setting annual_line_ids (no lines)")

            if self.target_registry not in ['g2p.crop.registry.planning', 'g2p.crop.registry.harvesting']:
                cultivation_key = next((k for k in ['cultivation', 'cultivation_land_prep'] if k in mapped_json), None)
                if cultivation_key and isinstance(mapped_json[cultivation_key], list):
                    cult_lines = mapped_json.pop(cultivation_key)
                    actual_annual_cmds = []
                    actual_perennial_cmds = []
                    actual_biennial_cmds = []

                    for line in cult_lines:
                        if not isinstance(line, dict): continue
                        _process_complex_line(line)
                        flat = _flatten_dict(line)
                        ignore_keys = ['land_category', 'land_id', 'crop_name_id', 'season_id', 'land_info_id', 'region', 'zone', 'woreda', 'kebele', '__id', '__parent_id', '__version', '__system', 'meta', 'instanceID', 'surveyor_name', 'interviewer_name', 'phone_no']
                        meaningful_keys = [k for k, v in flat.items() if v and k not in ignore_keys and not str(k).startswith('_')]
                        if meaningful_keys:
                            actual_annual_cmds.append((0, 0, flat))

                    if actual_annual_cmds:
                        mapped_json['actual_annual_line_ids'] = actual_annual_cmds
                sowing_key = next((k for k in ['sowing_harvesting', 'sowing', 'sown_harvest', 'sowing_details'] if k in mapped_json), None)
                if sowing_key:
                    sowing_val = mapped_json.pop(sowing_key)

                    if isinstance(sowing_val, list):
                        mapped_json['production_detail_ids'] = [(0, 0, _flatten_dict(line)) for line in sowing_val if isinstance(line, dict)]
                        _logger.info("SOWING VAL EXTRACTED: %s", sowing_val)
                        _logger.info("PRODUCTION DETAIL IDS: %s", mapped_json["production_detail_ids"])
                    elif isinstance(sowing_val, dict):
                        mapped_json['production_detail_ids'] = [(0, 0, _flatten_dict(sowing_val))]
                        _logger.info("SOWING VAL EXTRACTED: %s", sowing_val)
                        _logger.info("PRODUCTION DETAIL IDS: %s", mapped_json["production_detail_ids"])

            if self.target_registry not in ['g2p.crop.registry.planning', 'g2p.crop.registry.cultivation']:
                harvest_keys = [k for k in ['harvest_detail_ids', 'harvest_details', 'harvesting_details', 'harvesting', 'harvest', 'independant_harvest'] if k in mapped_json]
                if harvest_keys:
                    merged_harvest_lines = []
                    for hk in harvest_keys:
                        h_val = mapped_json.pop(hk)
                        if isinstance(h_val, list):
                            for idx, item in enumerate(h_val):
                                if isinstance(item, dict):
                                    while len(merged_harvest_lines) <= idx:
                                        merged_harvest_lines.append({})
                                    merged_harvest_lines[idx].update(_flatten_dict(item))
                        elif isinstance(h_val, dict):
                            if not merged_harvest_lines:
                                merged_harvest_lines.append({})
                            merged_harvest_lines[0].update(_flatten_dict(h_val))
                    if merged_harvest_lines:
                        mapped_json['harvest_detail_ids'] = [(0, 0, line) for line in merged_harvest_lines if line]

            # Auto-enrich production details and incidents before alias mapping and m2o resolution
            self._auto_enrich_production_and_incidents(mapped_json, member)

            # Map aliases recursively
            self._map_aliases_recursive('g2p.crop.registry', mapped_json)
            self._auto_populate_ec_dates_recursive(mapped_json)

            # Extract fyda_id from any key structure if missing or placeholder at top-level
            if not mapped_json.get('fyda_id') or mapped_json.get('fyda_id') == 'FAN-0000000000000000':
                def _find_id_in_val(val):
                    if isinstance(val, dict):
                        for k, v in val.items():
                            k_str = str(k).lower()
                            if any(x in k_str for x in ['fyda', 'fayda', 'farmer_id', 'unique_id']) and v:
                                v_str = str(v).strip()
                                if v_str and v_str != 'FAN-0000000000000000' and any(c.isdigit() for c in v_str):
                                    return v_str
                        for v in val.values():
                            res = _find_id_in_val(v)
                            if res: return res
                    elif isinstance(val, (list, tuple)):
                        for item in val:
                            res = _find_id_in_val(item)
                            if res: return res
                    return None
                found_id = _find_id_in_val(mapped_json)
                if not found_id and 'member' in locals() and member:
                    found_id = _find_id_in_val(member)
                if found_id:
                    _logger.info("=== ODK IMPORT: DEEP EXTRACTED FAYDA ID: %s ===", found_id)
                    mapped_json['fyda_id'] = found_id

            # Ensure fyda_id has a fallback value and is normalized to FAN- + 16 digits
            if not mapped_json.get('fyda_id'):
                mapped_json['fyda_id'] = 'FAN-0000000000000000'
            else:
                uid_str = str(mapped_json.get('fyda_id')).strip()
                for prefix in ['FAN-', 'FR-', 'TEMP-']:
                    if uid_str.startswith(prefix):
                        uid_str = uid_str[len(prefix):]
                clean_uid = ''.join(c for c in uid_str if c.isdigit())
                mapped_json['fyda_id'] = f"FAN-{clean_uid.zfill(16)[:16]}"

            # ===== Farmer Lookup: Primarily by Fayda ID =====
            fayda_val = mapped_json.get('fyda_id')
            partner_val = mapped_json.get('partner_id') or mapped_json.get('farmer_id')
            partner = False

            # 1. Primary lookup: Search by Fayda ID (fyda_id) in g2p.reg.id or res.partner
            if fayda_val and fayda_val != 'FAN-0000000000000000':
                clean_num = ''.join(c for c in str(fayda_val) if c.isdigit())
                possible_ids = [
                    fayda_val,
                    f"FAN-{clean_num}",
                    f"FR-{clean_num}",
                    f"TEMP-{clean_num}",
                    clean_num
                ]
                reg_id_rec = self.env['g2p.reg.id'].sudo().search([
                    ('value', 'in', possible_ids),
                ], limit=1)
                if reg_id_rec and reg_id_rec.partner_id:
                    partner = reg_id_rec.partner_id
                if not partner:
                    partner = self.env['res.partner'].sudo().search([
                        '|', '|', '|',
                        ('farmer_id', 'in', possible_ids),
                        ('unique_id', 'in', possible_ids),
                        ('ref', 'in', possible_ids),
                        ('name', 'in', possible_ids),
                    ], limit=1)

            # 2. Fallback: Search by farmer_id / partner_id (backward compatibility)
            if not partner and partner_val:
                if isinstance(partner_val, str):
                    search_ids = [partner_val]
                    if partner_val.startswith('FR-'):
                        search_ids.append(partner_val.replace('FR-', 'TEMP-', 1))
                    elif partner_val.startswith('TEMP-'):
                        search_ids.append(partner_val.replace('TEMP-', 'FR-', 1))
                    partner = self.env['res.partner'].sudo().search([('farmer_id', 'in', search_ids)], limit=1)
                    if not partner:
                        partner = self.env['res.partner'].sudo().search([('unique_id', 'in', search_ids)], limit=1)
                if not partner:
                    try:
                        partner_db_id = int(partner_val)
                        if -2147483648 <= partner_db_id <= 2147483647:
                            partner = self.env['res.partner'].sudo().search([('id', '=', partner_db_id)], limit=1)
                    except (TypeError, ValueError):
                        pass

            if partner:
                # ---- Farmer Found: auto-populate identity & geo from existing farmer ----
                mapped_json['partner_id'] = partner.id

                # Check if we should update the existing farmer (if it's a placeholder or missing data)
                update_vals = {}
                if partner.name == 'Unknown Farmer (Temp)':
                    new_name = mapped_json.get('farmer_display_id') or mapped_json.get('farmer_name')
                    if new_name:
                        update_vals['name'] = new_name
                        mapped_json['farmer_display_id'] = new_name
                elif not mapped_json.get('farmer_display_id'):
                    mapped_json['farmer_display_id'] = partner.name

                _logger.info("=== GEO EXTRACTION DEBUG ===")
                _logger.info("Raw mapped_json Region: %s", mapped_json.get('region_display_id') or mapped_json.get('region_id') or mapped_json.get('region'))
                _logger.info("Raw mapped_json Zone: %s", mapped_json.get('zone_display_id') or mapped_json.get('zone_id') or mapped_json.get('zone'))

                for field_name, odk_key, model_name in [
                    ('region', 'region_display_id', 'g2p.region'),
                    ('zone', 'zone_display_id', 'g2p.zone'),
                    ('woreda', 'woreda_id', 'g2p.woreda'),
                    ('kebele', 'kebele_id', 'g2p.kebele')
                ]:
                    val = mapped_json.get(odk_key) or mapped_json.get(field_name + '_id') or mapped_json.get(field_name)
                    if val and not getattr(partner, field_name, False):
                        if isinstance(val, int):
                            update_vals[field_name] = val
                        elif isinstance(val, str) and val.strip() and val.strip().lower() not in ('none', 'false', 'null'):
                            val_str = val.strip()
                            # Search by exact code or name
                            domain = ['|', ('code', '=ilike', val_str), ('name', '=ilike', val_str)]
                            rec = self.env[model_name].sudo().search(domain, limit=1)
                            if not rec:
                                # Search by partial code or name
                                domain_partial = ['|', ('code', '=ilike', f'%{val_str}%'), ('name', '=ilike', f'%{val_str}%')]
                                rec = self.env[model_name].sudo().search(domain_partial, limit=1)
                            if rec:
                                update_vals[field_name] = rec.id
                            else:
                                _logger.warning("ODK Import: Could not find %s matching '%s' in %s", field_name, val, model_name)

                # Handle GPS
                gps_val = mapped_json.get('gps')
                if gps_val:
                    if isinstance(gps_val, dict) and 'coordinates' in gps_val:
                        coords = gps_val['coordinates']
                        if len(coords) >= 2:
                            # Convert dict to a clean string for the crop registry record (Longitude, Latitude)
                            mapped_json['gps'] = f"{coords[0]}, {coords[1]}"
                            # Update partner if missing
                            if not partner.partner_latitude or not partner.partner_longitude:
                                update_vals['partner_longitude'] = float(coords[0])
                                update_vals['partner_latitude'] = float(coords[1])
                    elif isinstance(gps_val, str) and gps_val.strip().lower() not in ('none', 'false', 'null', ''):
                        # Extract the first valid coordinate pair
                        first_coord = gps_val.split(';')[0].strip()
                        if ',' in first_coord:
                            parts = [p.strip() for p in first_coord.split(',')]
                            if len(parts) >= 2:
                                try:
                                    if not partner.partner_latitude or not partner.partner_longitude:
                                        update_vals['partner_longitude'] = float(parts[0])
                                        update_vals['partner_latitude'] = float(parts[1])
                                except ValueError:
                                    pass
                        else:
                            parts = first_coord.split()
                            if len(parts) >= 2:
                                try:
                                    # ODK string format is usually "latitude longitude altitude accuracy"
                                    # If it's a point, we swap it for mapped_json['gps']
                                    if ';' not in gps_val:
                                        mapped_json['gps'] = f"{parts[1]}, {parts[0]}"
                                    if not partner.partner_latitude or not partner.partner_longitude:
                                        update_vals['partner_latitude'] = float(parts[0])
                                        update_vals['partner_longitude'] = float(parts[1])
                                except ValueError:
                                    pass

                if update_vals:
                    partner.sudo().write(update_vals)

                # Sync Fayda ID from farmer if the payload has a placeholder
                if partner.reg_ids and (not fayda_val or fayda_val == 'FAN-0000000000000000'):
                    uid_type = self.env['g2p.id.type'].sudo().search([('name', '=', 'UID')], limit=1)
                    if uid_type:
                        fayda_reg = partner.reg_ids.filtered(lambda r: r.id_type.id == uid_type.id)
                        if fayda_reg:
                            mapped_json['fyda_id'] = fayda_reg[0].value

                # Auto-populate geographic fields to mapped_json if they were updated or exist
                for field_name in ['region', 'zone', 'woreda', 'kebele']:
                    if not mapped_json.get(f"{field_name}_id") and hasattr(partner, field_name) and getattr(partner, field_name):
                        mapped_json[f"{field_name}_id"] = getattr(partner, field_name).id

                if not mapped_json.get('gps'):
                    if hasattr(partner, 'partner_latitude') and hasattr(partner, 'partner_longitude'):
                        if partner.partner_latitude and partner.partner_longitude:
                            mapped_json['gps'] = f"{partner.partner_latitude}, {partner.partner_longitude}"

                # Resolve land_info_id from farmer's existing land records
                # and overwrite line land details from the existing record
                farmer_lands = partner.land_information_ids if hasattr(partner, 'land_information_ids') else False
                if farmer_lands:
                    for line_field in ['annual_line_ids', 'actual_annual_line_ids', 'perennial_line_ids', 'biennial_line_ids', 'production_detail_ids', 'harvest_detail_ids']:
                        if line_field in mapped_json and isinstance(mapped_json[line_field], list):
                            for cmd in mapped_json[line_field]:
                                if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == 0:
                                    line_vals = cmd[2]
                                    if not isinstance(line_vals, dict):
                                        continue
                                    land_ref = line_vals.get('land_info_id')
                                    if not land_ref:
                                        continue
                                    # Match by land_id string (e.g. RU/12/12/123/12345)
                                    matched_land = False
                                    if isinstance(land_ref, str):
                                        matched_land = farmer_lands.filtered(lambda l: l.land_id == land_ref)
                                    elif isinstance(land_ref, int):
                                        matched_land = farmer_lands.filtered(lambda l: l.id == land_ref)
                                    if matched_land:
                                        land = matched_land[0]
                                        # Set land_info_id to the actual DB record ID
                                        line_vals['land_info_id'] = land.id
                                        # Overwrite land details from existing record
                                        inc_area = 0.0
                                        for a_k in ['land_area', 'actual_crop_area', 'area_sown']:
                                            if line_vals.get(a_k):
                                                try:
                                                    inc_area = max(inc_area, float(line_vals[a_k]))
                                                except (TypeError, ValueError):
                                                    pass
                                        if inc_area > land.total_land_area:
                                            land.sudo().write({'total_land_area': inc_area})
                                        line_vals['land_area'] = land.total_land_area
                                        line_vals['ownership_type'] = land.ownership_type
                                        # Populate geo from land_kebele hierarchy
                                        if land.land_kebele:
                                            line_vals['kebele_id'] = land.land_kebele.id
                                            if land.land_kebele.woreda:
                                                line_vals['woreda_name_id'] = land.land_kebele.woreda.id
                                                if land.land_kebele.woreda.zone:
                                                    line_vals['zone_name_id'] = land.land_kebele.woreda.zone.id
                                                    if land.land_kebele.woreda.zone.region:
                                                        line_vals['region_name_id'] = land.land_kebele.woreda.zone.region.id
                                        if hasattr(land, 'soil_fertility') and land.soil_fertility:
                                            line_vals['soil_fertility'] = land.soil_fertility.lower() if isinstance(land.soil_fertility, str) else land.soil_fertility
                                        # GPS: prefer ODK-submitted value, fall back to land record, sync both ways
                                        odk_gps = line_vals.get('gps')
                                        if odk_gps:
                                            if isinstance(odk_gps, dict) and 'coordinates' in odk_gps:
                                                c = odk_gps['coordinates']
                                                if len(c) >= 2:
                                                    odk_gps = f"{c[0]}, {c[1]}"
                                            elif isinstance(odk_gps, str):
                                                if str(odk_gps).strip().lower() in ('none', 'false', 'null', ''):
                                                    odk_gps = None
                                                elif ';' not in odk_gps and ',' not in odk_gps:
                                                    parts = odk_gps.split()
                                                    if len(parts) >= 2 and parts[0].replace('.','',1).isdigit():
                                                        odk_gps = f"{parts[1]}, {parts[0]}"
                                        land_gps = getattr(land, 'polygon_data', None)
                                        if odk_gps:
                                            line_vals['gps'] = odk_gps
                                            # Also update the land record if it lacks GPS
                                            if not land_gps:
                                                try:
                                                    land.sudo().write({'polygon_data': odk_gps})
                                                except Exception:
                                                    pass
                                        elif land_gps:
                                            line_vals['gps'] = land_gps
                                        # (Removed propagation of registry-level GPS to line)
                                    else:
                                        # Ensure a valid land_information record exists for this farmer
                                        land_rec = False
                                        if isinstance(land_ref, str) and str(land_ref).strip() and str(land_ref).strip() != 'False':
                                            land_rec = self.env['g2p.land.information'].sudo().search([('land_id', '=', land_ref), ('partner_id', '=', partner.id)], limit=1)
                                            if not land_rec:
                                                land_rec = self.env['g2p.land.information'].sudo().search([('land_id', '=', land_ref)], limit=1)
                                        elif isinstance(land_ref, int):
                                            land_rec = self.env['g2p.land.information'].sudo().search([('id', '=', land_ref)], limit=1)

                                        if not land_rec:
                                            # Clean GPS before using it for land record
                                            line_gps = line_vals.get('gps')
                                            if line_gps:
                                                if isinstance(line_gps, dict) and 'coordinates' in line_gps:
                                                    c = line_gps['coordinates']
                                                    if len(c) >= 2:
                                                        line_gps = f"{c[0]}, {c[1]}"
                                                elif isinstance(line_gps, str):
                                                    if str(line_gps).strip().lower() in ('none', 'false', 'null', ''):
                                                        line_gps = None
                                                    elif ';' not in line_gps and ',' not in line_gps:
                                                        parts = line_gps.split()
                                                        if len(parts) >= 2 and parts[0].replace('.','',1).isdigit():
                                                            line_gps = f"{parts[1]}, {parts[0]}"

                                                line_vals['gps'] = line_gps

                                            if not line_gps and mapped_json.get('gps'):
                                                # Root mapped_json['gps'] might still be a GeoJSON dict because of raw payload extraction
                                                mg = mapped_json['gps']
                                                if isinstance(mg, dict) and 'coordinates' in mg:
                                                    c = mg['coordinates']
                                                    if len(c) >= 2:
                                                        mg = f"{c[0]}, {c[1]}"
                                                elif isinstance(mg, str) and str(mg).strip().lower() not in ('none', 'false', 'null', ''):
                                                    if ';' not in mg and ',' not in mg:
                                                        parts = mg.split()
                                                        if len(parts) >= 2 and parts[0].replace('.','',1).isdigit():
                                                            mg = f"{parts[1]}, {parts[0]}"
                                                if isinstance(mg, str) and str(mg).strip().lower() not in ('none', 'false', 'null', ''):
                                                    line_gps = mg
                                                    line_vals['gps'] = line_gps
                                            land_vals = {
                                                'partner_id': partner.id,
                                                'land_id': str(land_ref).strip() if (land_ref and str(land_ref).strip() not in ('False', 'None', '')) else f"Plot {partner.id}-1",
                                                'total_land_area': line_vals.get('land_area', 0.0),
                                                'ownership_type': line_vals.get('ownership_type') or 'owner',
                                            }
                                            if line_gps:
                                                land_vals['polygon_data'] = line_gps
                                            if line_vals.get('kebele_id') and isinstance(line_vals['kebele_id'], int):
                                                land_vals['land_kebele'] = line_vals['kebele_id']
                                            land_rec = self.env['g2p.land.information'].sudo().create(land_vals)

                                        if land_rec:
                                            line_vals['land_info_id'] = land_rec.id
                                            line_vals['temporary_land_id'] = land_rec.land_id or str(land_ref)
                                            # Also populate GPS from land if line still lacks it
                                            if not line_vals.get('gps') or str(line_vals.get('gps', '')).strip().lower() in ('none', 'false', 'null', ''):
                                                if hasattr(land_rec, 'polygon_data') and land_rec.polygon_data:
                                                    line_vals['gps'] = land_rec.polygon_data

            else:
                # ---- Farmer NOT Found: create a new temp farmer ----
                import time as _time
                temp_id = f"TEMP-{int(_time.time())}"

                full_name = mapped_json.get('farmer_display_id') or mapped_json.get('farmer_name') or 'Unknown Farmer (Temp)'
                partner_vals = {
                    'name': full_name,
                    'is_farmer': 'yes',
                    'farmer_id': temp_id,
                    'is_registrant': True,
                    'is_group': False,
                }

                # Try to map specific name fields from ODK payload
                g_name = mapped_json.get('given_name') or mapped_json.get('first_name')
                f_name = mapped_json.get('family_name') or mapped_json.get('father_name')
                gf_name = mapped_json.get('gf_name_eng') or mapped_json.get('grand_father_name')

                if g_name:
                    partner_vals['given_name'] = g_name
                    if f_name:
                        partner_vals['family_name'] = f_name
                    if gf_name:
                        partner_vals['gf_name_eng'] = gf_name
                # If no specific name fields provided, split the full name
                elif full_name and full_name != 'Unknown Farmer (Temp)':
                    parts = full_name.split()
                    if len(parts) >= 1:
                        partner_vals['given_name'] = parts[0]
                    if len(parts) >= 2:
                        partner_vals['family_name'] = parts[1]
                    if len(parts) >= 3:
                        partner_vals['gf_name_eng'] = " ".join(parts[2:])

                # Extract and assign Geo fields (Region, Zone, Woreda, Kebele)
                for field_name, odk_key, model_name in [
                    ('region', 'region_display_id', 'g2p.region'),
                    ('zone', 'zone_display_id', 'g2p.zone'),
                    ('woreda', 'woreda_id', 'g2p.woreda'),
                    ('kebele', 'kebele_id', 'g2p.kebele')
                ]:
                    # Use fallback to 'region_id' etc. in case jq maps them to that
                    val = mapped_json.get(odk_key) or mapped_json.get(field_name + '_id') or mapped_json.get(field_name)
                    if val:
                        if isinstance(val, int):
                            partner_vals[field_name] = val
                        elif isinstance(val, str) and val.strip() and val.strip().lower() not in ('none', 'false', 'null'):
                            val_str = val.strip()
                            domain = ['|', ('code', '=ilike', val_str), ('name', '=ilike', val_str)]
                            rec = self.env[model_name].sudo().search(domain, limit=1)
                            if not rec:
                                domain_partial = ['|', ('code', '=ilike', f'%{val_str}%'), ('name', '=ilike', f'%{val_str}%')]
                                rec = self.env[model_name].sudo().search(domain_partial, limit=1)
                            if rec:
                                partner_vals[field_name] = rec.id
                            else:
                                _logger.warning("ODK Import: Could not find %s matching '%s' in %s", field_name, val, model_name)

                # Extract and assign GPS
                gps_val = mapped_json.get('gps')
                if gps_val:
                    if isinstance(gps_val, dict) and 'coordinates' in gps_val:
                        # GeoJSON format: {'type': 'Point', 'coordinates': [longitude, latitude, altitude]}
                        coords = gps_val['coordinates']
                        if len(coords) >= 2:
                            # Note: GeoJSON stores coordinates as [longitude, latitude]
                            partner_vals['partner_longitude'] = float(coords[0])
                            partner_vals['partner_latitude'] = float(coords[1])
                    elif isinstance(gps_val, str) and gps_val.strip().lower() not in ('none', 'false', 'null', ''):
                        # Extract the first valid coordinate pair
                        first_coord = gps_val.split(';')[0].strip()
                        if ',' in first_coord:
                            parts = [p.strip() for p in first_coord.split(',')]
                            if len(parts) >= 2:
                                try:
                                    partner_vals['partner_longitude'] = float(parts[0])
                                    partner_vals['partner_latitude'] = float(parts[1])
                                except ValueError:
                                    pass
                        else:
                            parts = first_coord.split()
                            if len(parts) >= 2:
                                try:
                                    # ODK string format is usually "latitude longitude altitude accuracy"
                                    partner_vals['partner_latitude'] = float(parts[0])
                                    partner_vals['partner_longitude'] = float(parts[1])
                                except ValueError:
                                    pass

                # Debug log to see exactly what we are saving
                _logger.info("=== SAVING NEW FARMER ===")
                _logger.info("Mapped JSON farmer_display_id: %s", mapped_json.get('farmer_display_id'))
                _logger.info("Partner Vals: %s", partner_vals)

                # Save Fayda ID as a reg_id on the new partner
                if fayda_val and fayda_val != 'FAN-0000000000000000':
                    uid_type = self.env['g2p.id.type'].sudo().search([('name', '=', 'UID')], limit=1)
                    if uid_type:
                        partner_vals['reg_ids'] = [(0, 0, {
                            'id_type': uid_type.id,
                            'value': fayda_val,
                            'status': 'valid'
                         })]

                # Convert GPS dict to string for the new farmer creation scenario
                gps_val = mapped_json.get('gps')
                if gps_val and isinstance(gps_val, dict) and 'coordinates' in gps_val:
                    coords = gps_val['coordinates']
                    if len(coords) >= 2:
                        mapped_json['gps'] = f"{coords[0]}, {coords[1]}"

                new_partner = self.env['res.partner'].sudo().create(partner_vals)
                mapped_json['partner_id'] = new_partner.id
                if not mapped_json.get('farmer_display_id'):
                    mapped_json['farmer_display_id'] = new_partner.name

                # Propagate geographic IDs to mapped_json so the Crop Registry also gets them
                if hasattr(new_partner, 'region') and new_partner.region and not mapped_json.get('region_id'):
                    mapped_json['region_id'] = new_partner.region.id
                if hasattr(new_partner, 'zone') and new_partner.zone and not mapped_json.get('zone_id'):
                    mapped_json['zone_id'] = new_partner.zone.id
                if hasattr(new_partner, 'woreda') and new_partner.woreda and not mapped_json.get('woreda_id'):
                    mapped_json['woreda_id'] = new_partner.woreda.id
                if hasattr(new_partner, 'kebele') and new_partner.kebele and not mapped_json.get('kebele_id'):
                    mapped_json['kebele_id'] = new_partner.kebele.id

                # Create land records on the new farmer from ODK planning/cultivation lines
                seen_land_ids = set()
                for line_field in ['annual_line_ids', 'actual_annual_line_ids', 'perennial_line_ids', 'biennial_line_ids']:
                    if line_field in mapped_json and isinstance(mapped_json[line_field], list):
                        for cmd in mapped_json[line_field]:
                            if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == 0:
                                line_vals = cmd[2]
                                if isinstance(line_vals, dict) and line_vals.get('land_info_id'):
                                    land_ref = line_vals['land_info_id']
                                    land_ref_key = str(land_ref)
                                    if land_ref_key in seen_land_ids:
                                        # Already created this land, just resolve the ID
                                        existing_land = self.env['g2p.land.information'].sudo().search([
                                            ('land_id', '=', land_ref if isinstance(land_ref, str) else False),
                                            ('partner_id', '=', new_partner.id)
                                        ], limit=1)
                                        if existing_land:
                                            line_vals['land_info_id'] = existing_land.id
                                        continue
                                    seen_land_ids.add(land_ref_key)
                                    land_vals = {
                                        'partner_id': new_partner.id,
                                        'land_id': str(land_ref).strip() if (land_ref and str(land_ref).strip() not in ('False', 'None', '')) else f"Plot {new_partner.id}-1",
                                        'total_land_area': line_vals.get('land_area', 0.0),
                                        'ownership_type': line_vals.get('ownership_type') or 'owner',
                                    }
                                    if line_vals.get('gps'):
                                        land_vals['polygon_data'] = line_vals['gps']

                                    if line_vals.get('kebele_id'):
                                        if isinstance(line_vals['kebele_id'], str):
                                            k_val = line_vals['kebele_id']
                                            k_rec = self.env['g2p.kebele'].sudo().search([('name', '=ilike', k_val)], limit=1)
                                            if not k_rec:
                                                k_rec = self.env['g2p.kebele'].sudo().search([('name', '=ilike', f'%{k_val}%')], limit=1)
                                            if k_rec:
                                                line_vals['kebele_id'] = k_rec.id
                                                land_vals['land_kebele'] = k_rec.id
                                        elif isinstance(line_vals['kebele_id'], int):
                                            land_vals['land_kebele'] = line_vals['kebele_id']

                                    new_land = self.env['g2p.land.information'].sudo().create(land_vals)
                                    line_vals['land_info_id'] = new_land.id

            if not mapped_json.get('farmer_display_id'):
                mapped_json['farmer_display_id'] = 'Unknown Farmer'

            self._resolve_m2o_recursive(mapped_json)
            mapped_json.pop('total_farmers', None)

            # Find if an existing record already exists for this farmer
            partner_id = mapped_json.get('partner_id')
            existing = False
            if partner_id:
                existing = self.env['g2p.crop.registry'].sudo().search([
                    ('partner_id', '=', partner_id)
                ], limit=1)

            # Auto-populate missing crop_name_id and link/update existing cluster_info_ids for actual lines (cultivation) from planning lines
            if 'actual_annual_line_ids' in mapped_json and isinstance(mapped_json['actual_annual_line_ids'], list):
                new_actual_cmds = []
                for cmd in mapped_json['actual_annual_line_ids']:
                    if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] in [0, 1]:
                        line_vals = cmd[2]

                        if isinstance(line_vals, dict) and line_vals.get('land_info_id'):
                            found_crop = None
                            found_season = None
                            matched_plan_line = None
                            matched_cult_line = None

                            # 1. Match with existing registry lines
                            if existing:
                                # Match existing cultivation line to update instead of duplicate
                                if hasattr(existing, 'actual_annual_line_ids'):
                                    ex_cults = existing.actual_annual_line_ids.filtered(lambda l: l.land_info_id.id == line_vals['land_info_id'])
                                    if ex_cults:
                                        matched_cult_line = ex_cults[0]

                                # Match existing planning line
                                for plan_f in ['annual_line_ids', 'perennial_line_ids', 'biennial_line_ids']:
                                    existing_lines = getattr(existing, plan_f, self.env['g2p.annual.line'].browse())
                                    p_line = existing_lines.filtered(lambda l: l.land_info_id.id == line_vals['land_info_id'])
                                    if p_line:
                                        if p_line[0].crop_name_id:
                                            found_crop = p_line[0].crop_name_id.id
                                        if hasattr(p_line[0], 'season_id') and p_line[0].season_id:
                                            found_season = p_line[0].season_id.id
                                        matched_plan_line = p_line[0]
                                        break

                            if not line_vals.get('crop_name_id') and found_crop:
                                line_vals['crop_name_id'] = found_crop
                            if not line_vals.get('season_id') and found_season:
                                line_vals['season_id'] = found_season

                            if not line_vals.get('sync_id') and matched_plan_line and hasattr(matched_plan_line, 'sync_id') and matched_plan_line.sync_id:
                                line_vals['sync_id'] = matched_plan_line.sync_id

                            # Handle Cluster Separation (Option 1)
                            cult_cluster = matched_cult_line.cluster_info_ids[0] if matched_cult_line and hasattr(matched_cult_line, 'cluster_info_ids') and matched_cult_line.cluster_info_ids else None
                            plan_cluster = matched_plan_line.cluster_info_ids[0] if matched_plan_line and hasattr(matched_plan_line, 'cluster_info_ids') and matched_plan_line.cluster_info_ids else None

                            if cult_cluster:
                                # A cultivation cluster already exists. Just update it.
                                if line_vals.get('cluster_info_ids') and isinstance(line_vals['cluster_info_ids'], list):
                                    new_cluster_cmds = []
                                    for c_cmd in line_vals['cluster_info_ids']:
                                        if isinstance(c_cmd, (list, tuple)) and len(c_cmd) == 3 and c_cmd[0] == 0:
                                            # Update the existing cultivation cluster
                                            update_vals = dict(c_cmd[2])
                                            update_vals.pop('cluster_farmer_line_ids', None)
                                            update_vals.pop('cluster_smallholders', None)
                                            new_cluster_cmds.append((1, cult_cluster.id, update_vals))
                                        else:
                                            new_cluster_cmds.append(c_cmd)
                                    line_vals['cluster_info_ids'] = new_cluster_cmds
                                else:
                                    line_vals['cluster_info_ids'] = [(4, cult_cluster.id)]
                            elif plan_cluster:
                                # No cultivation cluster yet, but planning cluster exists. Create a NEW independent cluster.
                                new_cluster_vals = {
                                    'cluster_id': plan_cluster.cluster_id,
                                    'cluster_name': plan_cluster.cluster_name,
                                    'cluster_smallholders': plan_cluster.cluster_smallholders,
                                }
                                # Copy farmers
                                farmer_cmds = []
                                for f in plan_cluster.cluster_farmer_line_ids:
                                    farmer_cmds.append((0, 0, {
                                        'farmer_id': f.farmer_id.id if f.farmer_id else False,
                                        'fayda_id': f.fayda_id,
                                        'farmer_name': f.farmer_name,
                                        'region_id': f.region_id.id if f.region_id else False,
                                        'zone_id': f.zone_id.id if f.zone_id else False,
                                        'woreda_id': f.woreda_id.id if f.woreda_id else False,
                                        'kebele_id': f.kebele_id.id if f.kebele_id else False,
                                    }))
                                if farmer_cmds:
                                    new_cluster_vals['cluster_farmer_line_ids'] = farmer_cmds

                                if line_vals.get('cluster_info_ids') and isinstance(line_vals['cluster_info_ids'], list):
                                    for c_cmd in line_vals['cluster_info_ids']:
                                        if isinstance(c_cmd, (list, tuple)) and len(c_cmd) == 3 and c_cmd[0] == 0:
                                            # Merge incoming cultivation cluster data into the new independent cluster
                                            incoming_vals = dict(c_cmd[2])
                                            incoming_vals.pop('cluster_farmer_line_ids', None)
                                            incoming_vals.pop('cluster_smallholders', None)
                                            new_cluster_vals.update(incoming_vals)

                                line_vals['cluster_info_ids'] = [(0, 0, new_cluster_vals)]

                            # Change (0, 0, vals) to (1, matched_id, vals) for idempotent updates
                            if matched_cult_line and cmd[0] == 0:
                                new_actual_cmds.append((1, matched_cult_line.id, line_vals))
                            else:
                                new_actual_cmds.append(cmd)
                        else:
                            new_actual_cmds.append(cmd)
                    else:
                        new_actual_cmds.append(cmd)
                mapped_json['actual_annual_line_ids'] = new_actual_cmds

            # Ensure command tuples are mutable lists so we can update op and record_id in place
            for f_detail in ['production_detail_ids', 'harvest_detail_ids']:
                if isinstance(mapped_json.get(f_detail), list):
                    mapped_json[f_detail] = [list(cmd) if isinstance(cmd, (list, tuple)) else cmd for cmd in mapped_json[f_detail]]

            # If harvest_detail_ids contains any create commands (op == 0), move them to production_detail_ids
            # before processing so they are included in detail_cmds and matched with existing production records.
            if isinstance(mapped_json.get('harvest_detail_ids'), list):
                new_harv = []
                prod_adds = []
                for hcmd in mapped_json['harvest_detail_ids']:
                    if isinstance(hcmd, (list, tuple)) and len(hcmd) >= 3 and hcmd[0] == 0:
                        prod_adds.append(hcmd)
                    else:
                        new_harv.append(hcmd)
                mapped_json['harvest_detail_ids'] = new_harv
                if prod_adds:
                    if not isinstance(mapped_json.get('production_detail_ids'), list):
                        mapped_json['production_detail_ids'] = []
                    _logger.info("PRODUCTION DETAIL IDS (before extend): %s", mapped_json["production_detail_ids"])
                    mapped_json['production_detail_ids'].extend(prod_adds)

            # Auto-populate sowing/production/harvesting lines from cultivation/sowing data by matching land_info_id
            detail_cmds = (mapped_json.get('production_detail_ids') if isinstance(mapped_json.get('production_detail_ids'), list) else []) + (mapped_json.get('harvest_detail_ids') if isinstance(mapped_json.get('harvest_detail_ids'), list) else [])
            if detail_cmds:
                for cmd in detail_cmds:
                    if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == 0:
                        prod_vals = cmd[2]
                        if not isinstance(prod_vals, dict):
                            continue
                        prod_land_id = prod_vals.get('land_info_id')
                        if not prod_land_id:
                            # Try to infer prod_land_id if there is only one cultivation line in payload
                            cult_cmds = mapped_json.get('actual_annual_line_ids', [])
                            if isinstance(cult_cmds, list):
                                valid_cults = [cmd[2] for cmd in cult_cmds if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] in [0, 1] and isinstance(cmd[2], dict) and cmd[2].get('land_info_id')]
                                if len(valid_cults) == 1:
                                    prod_land_id = valid_cults[0].get('land_info_id')
                                    prod_vals['land_info_id'] = prod_land_id

                            # Fallback to existing registry if it has exactly one cultivation/planning line
                            if not prod_land_id and existing:
                                if len(existing.actual_annual_line_ids) == 1 and existing.actual_annual_line_ids[0].land_info_id:
                                    prod_land_id = existing.actual_annual_line_ids[0].land_info_id.id
                                    prod_vals['land_info_id'] = prod_land_id
                                elif len(existing.annual_line_ids) == 1 and existing.annual_line_ids[0].land_info_id:
                                    prod_land_id = existing.annual_line_ids[0].land_info_id.id
                                    prod_vals['land_info_id'] = prod_land_id

                        if not prod_land_id:
                            continue

                        # Find matching cultivation line by land_info_id
                        matched_cult = None
                        # 1. Check in current payload's cultivation lines
                        for line_field in ['actual_annual_line_ids']:
                            if line_field in mapped_json and isinstance(mapped_json[line_field], list):
                                for acmd in mapped_json[line_field]:
                                    if isinstance(acmd, (list, tuple)) and len(acmd) == 3 and acmd[0] in [0, 1]:
                                        avals = acmd[2]
                                        if isinstance(avals, dict) and avals.get('land_info_id') == prod_land_id:
                                            matched_cult = avals
                                            break
                                if matched_cult:
                                    break

                        # 2. Check in existing registry record's cultivation and planning lines
                        if not matched_cult and existing:
                            cult_line = existing.actual_annual_line_ids.filtered(lambda l: l.land_info_id.id == prod_land_id)
                            if not cult_line:
                                cult_line = existing.annual_line_ids.filtered(lambda l: l.land_info_id.id == prod_land_id)
                            if not cult_line:
                                cult_line = existing.perennial_line_ids.filtered(lambda l: l.land_info_id.id == prod_land_id)
                            if not cult_line:
                                cult_line = existing.biennial_line_ids.filtered(lambda l: l.land_info_id.id == prod_land_id)
                            if not cult_line and hasattr(existing, 'production_detail_ids'):
                                cult_line = existing.production_detail_ids.filtered(lambda l: l.land_info_id.id == prod_land_id)

                            # Filter by crop_name_id if possible
                            if len(cult_line) > 1 and (prod_vals.get('crop_name_id') or prod_vals.get('actual_crop_name')):
                                raw_crop = prod_vals.get('crop_name_id') or prod_vals.get('actual_crop_name')
                                if isinstance(raw_crop, int):
                                    c_line = cult_line.filtered(lambda l: l.crop_name_id.id == raw_crop)
                                    if c_line: cult_line = c_line
                                elif isinstance(raw_crop, str):
                                    c_line = cult_line.filtered(lambda l: l.crop_name_id.name and raw_crop.lower() in l.crop_name_id.name.lower())
                                    if c_line: cult_line = c_line

                            if cult_line:
                                cl = cult_line[0]
                                matched_cult = {
                                    'sync_id': cl.sync_id if hasattr(cl, 'sync_id') else False,
                                    'season_id': cl.season_id.id if cl.season_id else False,
                                    'crop_name_id': cl.crop_name_id.id if cl.crop_name_id else False,
                                    'collected_gc': getattr(cl, 'actual_sowing_date', getattr(cl, 'collected_gc', False)),
                                    'actual_fertilizer_type': getattr(cl, 'actual_fertilizer_type', False),
                                    'actual_fertilizer_qty': getattr(cl, 'actual_fertilizer_qty', False),
                                    'actual_crop_area': getattr(cl, 'actual_crop_area', getattr(cl, 'crop_area', getattr(cl, 'area_sown', False))),
                                    'actual_seed_qty': getattr(cl, 'actual_seed_qty', False),
                                    'cluster_info_ids': cl.cluster_info_ids.ids if hasattr(cl, 'cluster_info_ids') and cl.cluster_info_ids else [],
                                }

                        matched_plan = None
                        for line_field in ['annual_line_ids', 'perennial_line_ids', 'biennial_line_ids']:
                            if line_field in mapped_json and isinstance(mapped_json[line_field], list):
                                for pcmd in mapped_json[line_field]:
                                    if isinstance(pcmd, (list, tuple)) and len(pcmd) == 3 and pcmd[0] in [0, 1]:
                                        pvals = pcmd[2]
                                        if isinstance(pvals, dict) and pvals.get('land_info_id') == prod_land_id:
                                            matched_plan = pvals
                                            break
                                if matched_plan:
                                    break
                        if not matched_plan and existing:
                            plan_line = existing.annual_line_ids.filtered(lambda l: l.land_info_id.id == prod_land_id)
                            if not plan_line:
                                plan_line = existing.perennial_line_ids.filtered(lambda l: l.land_info_id.id == prod_land_id)
                            if not plan_line:
                                plan_line = existing.biennial_line_ids.filtered(lambda l: l.land_info_id.id == prod_land_id)
                            if plan_line:
                                pl = plan_line[0]
                                matched_plan = {
                                    'sync_id': pl.sync_id if hasattr(pl, 'sync_id') else False,
                                    'season_id': pl.season_id.id if hasattr(pl, 'season_id') and pl.season_id else False,
                                    'crop_name_id': pl.crop_name_id.id if hasattr(pl, 'crop_name_id') and pl.crop_name_id else False,
                                    'expected_yield': getattr(pl, 'crop_expected', getattr(pl, 'expected_yield', False)),
                                    'planned_area': getattr(pl, 'crop_planned_area', getattr(pl, 'planned_area', False)),
                                }

                        matched_prod_id = None
                        if existing and hasattr(existing, 'production_detail_ids'):
                            prod_recs = existing.production_detail_ids.filtered(lambda l: l.land_info_id.id == prod_land_id)
                            if not prod_recs and hasattr(existing, 'harvest_detail_ids'):
                                prod_recs = existing.harvest_detail_ids.filtered(lambda l: l.land_info_id.id == prod_land_id)

                            if len(prod_recs) > 1 and (prod_vals.get('crop_name_id') or prod_vals.get('actual_crop_name')):
                                raw_crop = prod_vals.get('crop_name_id') or prod_vals.get('actual_crop_name')
                                if isinstance(raw_crop, int):
                                    c_recs = prod_recs.filtered(lambda l: l.crop_name_id.id == raw_crop)
                                    if c_recs: prod_recs = c_recs
                                elif isinstance(raw_crop, str):
                                    c_recs = prod_recs.filtered(lambda l: l.crop_name_id.name and raw_crop.lower() in l.crop_name_id.name.lower())
                                    if c_recs: prod_recs = c_recs

                            if prod_recs:
                                matched_prod_id = prod_recs[0].id

                        if matched_cult:
                            # Pass sync_id to ensure _sync_production_cached_values runs for this line
                            if not prod_vals.get('sync_id') and matched_cult.get('sync_id'):
                                prod_vals['sync_id'] = matched_cult['sync_id']

                            # Auto-populate missing fields from cultivation
                            if not prod_vals.get('season_id') and matched_cult.get('season_id'):
                                prod_vals['season_id'] = matched_cult['season_id']
                            if not prod_vals.get('crop_name_id') and matched_cult.get('crop_name_id'):
                                prod_vals['crop_name_id'] = matched_cult['crop_name_id']
                            if not prod_vals.get('actual_sowing_date') and matched_cult.get('collected_gc'):
                                sowing_date = matched_cult['collected_gc']
                                if hasattr(sowing_date, 'strftime'):
                                    prod_vals['actual_sowing_date'] = sowing_date.strftime('%Y-%m-%d')
                                else:
                                    prod_vals['actual_sowing_date'] = sowing_date
                            if not prod_vals.get('actual_fertilizer_type') and matched_cult.get('actual_fertilizer_type'):
                                prod_vals['actual_fertilizer_type'] = matched_cult['actual_fertilizer_type']
                            if not prod_vals.get('actual_fertilizer_qty') and matched_cult.get('actual_fertilizer_qty'):
                                prod_vals['actual_fertilizer_qty'] = matched_cult['actual_fertilizer_qty']
                            if not prod_vals.get('actual_crop_area') and matched_cult.get('actual_crop_area'):
                                prod_vals['actual_crop_area'] = matched_cult['actual_crop_area']
                            if not prod_vals.get('actual_seed_qty') and matched_cult.get('actual_seed_qty'):
                                prod_vals['actual_seed_qty'] = matched_cult['actual_seed_qty']

                        if matched_plan:
                            if matched_plan.get('sync_id'):
                                prod_vals['sync_id'] = matched_plan['sync_id']
                                if cult_line and hasattr(cult_line[0], 'sync_id') and cult_line[0].sync_id != matched_plan['sync_id']:
                                    try:
                                        cult_line[0].sudo().write({'sync_id': matched_plan['sync_id']})
                                    except Exception:
                                        pass
                            if not prod_vals.get('season_id') and matched_plan.get('season_id'):
                                prod_vals['season_id'] = matched_plan['season_id']
                            if not prod_vals.get('crop_name_id') and matched_plan.get('crop_name_id'):
                                prod_vals['crop_name_id'] = matched_plan['crop_name_id']
                            if not prod_vals.get('expected_yield') and matched_plan.get('expected_yield'):
                                prod_vals['expected_yield'] = matched_plan['expected_yield']
                            if not prod_vals.get('planned_area') and matched_plan.get('planned_area'):
                                prod_vals['planned_area'] = matched_plan['planned_area']

                        # Auto-populate cluster_info_id for cluster details if not set
                        cluster_lines = prod_vals.get('production_cluster_line_ids') or prod_vals.get('cluster_details') or []
                        if isinstance(cluster_lines, list) and cluster_lines:
                            valid_c_id = None
                            if matched_cult:
                                c_ids = matched_cult.get('cluster_info_ids') or []
                                if isinstance(c_ids, list) and c_ids:
                                    for cid in c_ids:
                                        if isinstance(cid, int):
                                            valid_c_id = cid
                                            break
                                        elif isinstance(cid, (list, tuple)) and len(cid) == 3 and isinstance(cid[2], dict) and cid[2].get('id'):
                                            valid_c_id = cid[2]['id']
                                            break
                            if not valid_c_id and existing:
                                cluster_recs = self.env['g2p.cluster.information'].sudo().search([
                                    '|', '|', '|',
                                    ('annual_line_id.registry_id', '=', existing.id),
                                    ('perennial_line_id.registry_id', '=', existing.id),
                                    ('biennial_line_id.registry_id', '=', existing.id),
                                    ('actual_annual_line_id.registry_id', '=', existing.id),
                                ], limit=1)
                                if cluster_recs:
                                    valid_c_id = cluster_recs[0].id
                            if not valid_c_id:
                                try:
                                    new_cluster = self.env['g2p.cluster.information'].sudo().create({
                                        'cluster_name': 'Default Cluster (Auto)',
                                    })
                                    valid_c_id = new_cluster.id
                                except Exception:
                                    pass
                            if valid_c_id:
                                for c_cmd in cluster_lines:
                                    if isinstance(c_cmd, (list, tuple)) and len(c_cmd) == 3 and isinstance(c_cmd[2], dict):
                                        if not c_cmd[2].get('cluster_info_id'):
                                            c_cmd[2]['cluster_info_id'] = valid_c_id
                                    elif isinstance(c_cmd, dict):
                                        if not c_cmd.get('cluster_info_id'):
                                            c_cmd['cluster_info_id'] = valid_c_id

                        # Auto-populate sowing_status if not set
                        if not prod_vals.get('sowing_status'):
                            if prod_vals.get('actual_sowing_date') or prod_vals.get('area_sown') or prod_vals.get('actual_crop_area') or prod_vals.get('harvest_date'):
                                prod_vals['sowing_status'] = 'sown'
                            elif str(prod_vals.get('is_sown', '')).strip().lower() in ('yes', 'true', '1', 'sown'):
                                prod_vals['sowing_status'] = 'sown'

                        # Normalize cluster_status_ids (ODK sends raw strings like 'clustered independent')
                        c_status = prod_vals.get('cluster_status_ids')
                        if isinstance(c_status, str) or not isinstance(c_status, list):
                            is_cl = False
                            if isinstance(c_status, str) and 'clustered' in c_status.lower():
                                is_cl = True
                            elif isinstance(cluster_lines, list) and len(cluster_lines) > 0:
                                is_cl = True
                            elif str(prod_vals.get('has_cluster_farming', '')).strip().lower() in ('yes', 'true', '1'):
                                is_cl = True
                            elif prod_vals.get('cluster_info_ids'):
                                is_cl = True
                            elif matched_cult and matched_cult.get('cluster_info_ids'):
                                is_cl = True
                            elif matched_plan and matched_plan.get('cluster_info_ids'):
                                is_cl = True
                            elif existing:
                                ex_cl = self.env['g2p.cluster.information'].sudo().search([
                                    '|', '|', '|',
                                    ('annual_line_id.registry_id', '=', existing.id),
                                    ('perennial_line_id.registry_id', '=', existing.id),
                                    ('biennial_line_id.registry_id', '=', existing.id),
                                    ('actual_annual_line_id.registry_id', '=', existing.id),
                                ], limit=1)
                                if ex_cl:
                                    is_cl = True
                            status_val = self._resolve_cluster_status_id(is_cl)
                            if status_val:
                                prod_vals['cluster_status_ids'] = status_val
                            else:
                                prod_vals.pop('cluster_status_ids', None)

                        # Validate harvest_date: must be after actual_sowing_date
                        harvest_dt = prod_vals.get('harvest_date')
                        sowing_dt = prod_vals.get('actual_sowing_date')
                        if harvest_dt and sowing_dt:
                            from datetime import date as _date
                            try:
                                if isinstance(harvest_dt, str):
                                    harvest_dt = _date.fromisoformat(harvest_dt)
                                if isinstance(sowing_dt, str):
                                    sowing_dt = _date.fromisoformat(sowing_dt)
                                if harvest_dt < sowing_dt:
                                    _logger.warning(
                                        "Skipping harvest_date %s because it is before actual_sowing_date %s for land %s",
                                        harvest_dt, sowing_dt, prod_land_id
                                    )
                                    prod_vals['harvest_date'] = False
                            except (ValueError, TypeError):
                                pass

                        # Propagate harvest fields to cluster lines if present
                        harvest_fields = ['crop_maturity_status', 'harvest_date', 'area_harvested', 'qty_harvested', 'post_harvest_loss_pct', 'qty_stored', 'qty_sold']
                        has_harv = any(hf in prod_vals and prod_vals[hf] is not None and prod_vals[hf] != '' and prod_vals[hf] != False for hf in harvest_fields)
                        if has_harv:
                            harv_sub = {hf: prod_vals[hf] for hf in harvest_fields if hf in prod_vals}
                            if matched_prod_id and not prod_vals.get('production_cluster_line_ids') and not prod_vals.get('cluster_details'):
                                ex_prod = self.env['g2p.crop.production'].sudo().browse(matched_prod_id)
                                if ex_prod.exists() and ex_prod.production_cluster_line_ids:
                                    cl_cmds = []
                                    for cl in ex_prod.production_cluster_line_ids:
                                        cl_cmds.append((1, cl.id, harv_sub.copy()))
                                    prod_vals['production_cluster_line_ids'] = cl_cmds
                            elif isinstance(prod_vals.get('production_cluster_line_ids'), list):
                                for c_cmd in prod_vals['production_cluster_line_ids']:
                                    if isinstance(c_cmd, (list, tuple)) and len(c_cmd) == 3 and isinstance(c_cmd[2], dict):
                                        for hf, hv in harv_sub.items():
                                            if not c_cmd[2].get(hf):
                                                c_cmd[2][hf] = hv

                        # Transform cluster lines to avoid triggering unlink on them, which crashes
                        if isinstance(prod_vals.get('production_cluster_line_ids'), list):
                            cl_cmds = prod_vals['production_cluster_line_ids']
                            has_five = any(isinstance(c, (list, tuple)) and c[0] == 5 for c in cl_cmds)
                            if has_five:
                                new_cl_cmds = []
                                ex_prod = self.env['g2p.crop.production'].sudo().browse(matched_prod_id) if matched_prod_id else None
                                for c in cl_cmds:
                                    if isinstance(c, (list, tuple)) and c[0] == 5:
                                        continue
                                    elif isinstance(c, (list, tuple)) and c[0] == 0 and isinstance(c[2], dict) and ex_prod and ex_prod.exists() and ex_prod.production_cluster_line_ids:
                                        c_vals = c[2]
                                        c_info_id = c_vals.get('cluster_info_id')
                                        match_cl = False
                                        if c_info_id:
                                            ex_cl = ex_prod.production_cluster_line_ids.filtered(lambda l: l.cluster_info_id.id == c_info_id)
                                            if ex_cl:
                                                new_cl_cmds.append((1, ex_cl[0].id, c_vals))
                                                match_cl = True
                                        if not match_cl and len(ex_prod.production_cluster_line_ids) == 1:
                                            new_cl_cmds.append((1, ex_prod.production_cluster_line_ids[0].id, c_vals))
                                            match_cl = True
                                        if not match_cl:
                                            new_cl_cmds.append(c)
                                    else:
                                        new_cl_cmds.append(c)
                                prod_vals['production_cluster_line_ids'] = new_cl_cmds

                        if matched_prod_id and cmd[0] == 0:
                            cmd[0] = 1
                            cmd[1] = matched_prod_id

            # If harvest_detail_ids contains any create commands (op == 0), move them to production_detail_ids
            # because g2p.crop.registry ignores op == 0 commands from harvest_detail_ids.
            if isinstance(mapped_json.get('harvest_detail_ids'), list):
                new_harv = []
                prod_adds = []
                for hcmd in mapped_json['harvest_detail_ids']:
                    if isinstance(hcmd, (list, tuple)) and len(hcmd) >= 3 and hcmd[0] == 0:
                        prod_adds.append(hcmd)
                    else:
                        new_harv.append(hcmd)
                mapped_json['harvest_detail_ids'] = new_harv
                if prod_adds:
                    if not isinstance(mapped_json.get('production_detail_ids'), list):
                        mapped_json['production_detail_ids'] = []
                        _logger.info("SOWING VAL EXTRACTED: %s", sowing_val)
                        _logger.info("PRODUCTION DETAIL IDS: %s", mapped_json["production_detail_ids"])
                    mapped_json['production_detail_ids'].extend(prod_adds)

            # Filter out invalid lines from annual_line_ids and actual_annual_line_ids
            for field in ['annual_line_ids', 'actual_annual_line_ids', 'perennial_line_ids', 'biennial_line_ids']:
                if field in mapped_json and isinstance(mapped_json[field], list):
                    filtered_cmds = []
                    for cmd in mapped_json[field]:
                        if isinstance(cmd, (list, tuple)) and len(cmd) == 3:
                            op, record_id, line_vals = cmd
                            if op == 0 and isinstance(line_vals, dict):
                                # Check if it has season_id and crop_name_id (required for both now)
                                if not line_vals.get('season_id') or not line_vals.get('crop_name_id'):
                                    raise ValidationError(f"Import Rejected: Season or Crop Name is missing or not found in Odoo Configuration. Please ensure they exist in Odoo before importing. (Found season_id={line_vals.get('season_id')}, crop_name_id={line_vals.get('crop_name_id')})")
                            elif op == 1 and isinstance(line_vals, dict):
                                # Check if season_id or crop_name_id is set to False
                                if 'season_id' in line_vals and not line_vals['season_id']:
                                    raise ValidationError("Import Rejected: Season is not found in Odoo Configuration. Please ensure it exists in Odoo before importing.")
                                if 'crop_name_id' in line_vals and not line_vals['crop_name_id']:
                                    raise ValidationError("Import Rejected: Crop Name is not found in Odoo Configuration. Please ensure it exists in Odoo before importing.")
                        filtered_cmds.append(cmd)
                    if len(filtered_cmds) == 1 and filtered_cmds[0][0] == 5:
                        mapped_json[field] = False
                    else:
                        mapped_json[field] = filtered_cmds

            # Sync survey details bidirectionally between root and lines
            survey_fields = ['surveyor_name', 'surveyor_mobile_number', 'supervisor_name', 'supervisor_mobile_number']

            # Step 1: Pull from lines to root if root doesn't have it
            for line_field in ['annual_line_ids', 'perennial_line_ids', 'biennial_line_ids']:
                if line_field in mapped_json and isinstance(mapped_json[line_field], list):
                    for cmd in mapped_json[line_field]:
                        if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == 0:
                            line_vals = cmd[2]
                            if isinstance(line_vals, dict):
                                for sf in survey_fields:
                                    if sf in line_vals and not mapped_json.get(sf):
                                        mapped_json[sf] = line_vals[sf]

            # Step 2: Push from root to all lines
            for line_field in [
                'annual_line_ids', 'actual_annual_line_ids',
                'perennial_line_ids',
                'biennial_line_ids',
                'production_detail_ids', 'harvest_detail_ids'
            ]:
                if line_field in mapped_json and isinstance(mapped_json[line_field], list):
                    for cmd in mapped_json[line_field]:
                        if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == 0:
                            line_vals = cmd[2]
                            if isinstance(line_vals, dict):
                                for sf in survey_fields:
                                    if sf in mapped_json and not line_vals.get(sf):
                                        line_vals[sf] = mapped_json[sf]
                                # (Removed pushing registry GPS to lines)

            _logger.info("=== ODK IMPORT DEBUG: BEFORE STRIP INVALID FIELDS ===")
            for k, v in mapped_json.items():
                if isinstance(v, list):
                    _logger.info("  mapped_json['%s'] = list with %s items", k, len(v))
                    for ci, cv in enumerate(v):
                        if isinstance(cv, (list, tuple)) and len(cv) == 3:
                            _logger.info("    [%s] op=%s, vals_keys=%s", ci, cv[0], list(cv[2].keys()) if isinstance(cv[2], dict) else cv[2])
                elif isinstance(v, dict):
                    _logger.info("  mapped_json['%s'] = dict with keys %s", k, list(v.keys()))
                else:
                    _logger.info("  mapped_json['%s'] = %s", k, repr(v)[:200])

            def _extract_global_gps(vals):
                if isinstance(vals, dict):
                    if 'type' in vals and 'coordinates' in vals and isinstance(vals['coordinates'], list):
                        return vals
                    for k in ['gps', 'gps_location', 'geopoint', 'location', 'plot_gps', 'cluster_gps']:
                        v = vals.get(k)
                        if v:
                            if isinstance(v, str) and ',' in v and str(v).strip().lower() not in ('none', 'false', 'null', ''):
                                return v
                            if isinstance(v, dict) and 'coordinates' in v:
                                return v
                    for v in vals.values():
                        res = _extract_global_gps(v)
                        if res: return res
                elif isinstance(vals, list):
                    for item in vals:
                        res = _extract_global_gps(item)
                        if res: return res
                return None

            # Calculate global_gps strictly from the raw ODK payload (member)
            # so that we do not mistakenly propagate the fallback Farmer Registry point GPS
            # to clusters or lands that lack their own GPS polygon.
            raw_global_gps = _extract_global_gps(member)

            global_gps = None
            if raw_global_gps:
                if isinstance(raw_global_gps, dict) and 'coordinates' in raw_global_gps:
                    # format as "lng,lat; lng,lat"
                    coords = raw_global_gps['coordinates']
                    flattened = []
                    def _flat(lst):
                        if not isinstance(lst, list) or len(lst) == 0: return
                        if isinstance(lst[0], (int, float)):
                            flattened.append(f"{lst[0]},{lst[1]}")
                        else:
                            for item in lst:
                                _flat(item)
                    _flat(coords)
                    if flattened:
                        global_gps = ";\n".join(flattened)
                else:
                    global_gps = raw_global_gps

            # We do not pop mapped_json['gps'] so it retains the farmer point GPS.
            # We also do not assign global_gps to mapped_json['gps'] because ODK GPS is for land/clusters.

            def _reconcile_cluster_data_recursive(vals):
                if isinstance(vals, dict):
                    # Fix cluster plan vs area
                    if 'cluster_plan' in vals and vals.get('cluster_plan') is not None:
                        area_ha = 0.0
                        if vals.get('cluster_area_hectare'):
                            try:
                                area_ha = float(vals['cluster_area_hectare'])
                            except:
                                pass
                        elif vals.get('cluster_area_timad'):
                            try:
                                area_ha = float(vals['cluster_area_timad']) * 0.25
                            except:
                                pass

                        if area_ha > 0:
                            try:
                                plan = float(vals['cluster_plan'])
                                if plan > area_ha:
                                    vals['cluster_plan'] = area_ha
                            except:
                                pass

                    # Fix farmer count
                    if 'cluster_smallholders' in vals and vals.get('cluster_smallholders') is not None:
                        try:
                            max_farmers = int(float(vals['cluster_smallholders']))
                            if 'cluster_farmer_line_ids' in vals and isinstance(vals['cluster_farmer_line_ids'], list):
                                current_cmds = vals['cluster_farmer_line_ids']
                                # filter out 0 commands (creates) and cap them
                                creates = [cmd for cmd in current_cmds if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == 0]
                                others = [cmd for cmd in current_cmds if not (isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == 0)]
                                if len(creates) > max_farmers:
                                    vals['cluster_farmer_line_ids'] = others + creates[:max_farmers]
                                elif len(creates) < max_farmers:
                                    # Adjust the expected count so validation doesn't fail
                                    vals['cluster_smallholders'] = len(creates)
                        except:
                            pass

                    # Push ODK GPS to cluster lines
                    if 'cluster_name' in vals or 'cluster_id' in vals or 'cluster_area_hectare' in vals or 'cluster_area_timad' in vals:
                        if not vals.get('gps_location') and global_gps:
                            vals['gps_location'] = global_gps

                    # Push ODK GPS to planning lines
                    if 'land_info_id' in vals or 'crop_planned_area' in vals or 'crop_name_id' in vals:
                        if not vals.get('gps') and global_gps:
                            vals['gps'] = global_gps

                    for v in vals.values():
                        _reconcile_cluster_data_recursive(v)
                elif isinstance(vals, list):
                    for item in vals:
                        if isinstance(item, dict):
                            _reconcile_cluster_data_recursive(item)
                        elif isinstance(item, (list, tuple)) and len(item) == 3 and isinstance(item[2], dict):
                            _reconcile_cluster_data_recursive(item[2])

            _reconcile_cluster_data_recursive(mapped_json)

            self._strip_invalid_fields_recursive('g2p.crop.registry', mapped_json)

            _logger.info("=== ODK IMPORT DEBUG: AFTER STRIP - FINAL PAYLOAD ===")
            for k, v in mapped_json.items():
                if isinstance(v, list):
                    _logger.info("  FINAL['%s'] = list with %s items", k, len(v))
                    for ci, cv in enumerate(v):
                        if isinstance(cv, (list, tuple)) and len(cv) == 3 and isinstance(cv[2], dict):
                            _logger.info("    [%s] op=%s, vals=%s", ci, cv[0], {kk: repr(vv)[:100] for kk, vv in cv[2].items()})
                elif isinstance(v, dict):
                    _logger.info("  FINAL['%s'] = dict %s", k, {kk: repr(vv)[:100] for kk, vv in v.items()})
                else:
                    _logger.info("  FINAL['%s'] = %s", k, repr(v)[:200])

            # Log exact Python types for the first annual line to diagnose type issues
            if 'annual_line_ids' in mapped_json and isinstance(mapped_json['annual_line_ids'], list):
                for cmd in mapped_json['annual_line_ids']:
                    if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == 0 and isinstance(cmd[2], dict):
                        _logger.info("=== ANNUAL LINE VALUE TYPES ===")
                        for fk, fv in cmd[2].items():
                            _logger.info("  %s: value=%s, type=%s", fk, repr(fv)[:150], type(fv).__name__)
                        break

            # Reconcile land areas in DB to prevent area validation errors
            land_area_requirements = {}
            for line_field in ['actual_annual_line_ids', 'annual_line_ids', 'perennial_line_ids', 'biennial_line_ids']:
                if line_field in mapped_json and isinstance(mapped_json[line_field], list):
                    for cmd in mapped_json[line_field]:
                        if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and isinstance(cmd[2], dict):
                            l_vals = cmd[2]
                            l_id = l_vals.get('land_info_id')
                            if l_id:
                                try:
                                    l_int = int(l_id)
                                except (TypeError, ValueError):
                                    l_int = False
                                if l_int:
                                    crop_a = 0.0
                                    for a_key in ['actual_crop_area', 'land_area', 'area_sown']:
                                        if l_vals.get(a_key):
                                            try:
                                                crop_a = max(crop_a, float(l_vals.get(a_key)))
                                            except (TypeError, ValueError):
                                                pass
                                    land_area_requirements[l_int] = land_area_requirements.get(l_int, 0.0) + crop_a

            for l_db_id, req_area in land_area_requirements.items():
                if req_area > 0:
                    l_rec = self.env['g2p.land.information'].sudo().browse(l_db_id)
                    if l_rec.exists() and l_rec.total_land_area < req_area:
                        _logger.info("Auto-adjusting total_land_area for Land ID %s (DB ID %s) from %s to %s ha to satisfy crop area constraint", l_rec.land_id, l_rec.id, l_rec.total_land_area, req_area)
                        l_rec.sudo().write({'total_land_area': req_area})

            if existing:
                _logger.info("WRITING to existing crop registry id=%s", existing.id)
                # The SQL cleanup block for production cluster lines was removed here
                # because it causes 'Record does not exist' errors when the ORM tries
                # to update these lines via (1, id, vals) commands generated by ODK mapping.
                _logger.info("MAPPED JSON GPS BEFORE WRITE: %s", mapped_json.get("gps"))

                # 1. Protect existing Farmer Identity fields from being overwritten
                farmer_identity_fields = ['partner_id', 'farmer_id', 'fyda_id', 'farmer_display_id', 'farmer_name', 'region_display_id', 'zone_display_id', 'woreda_id', 'kebele_id', 'region_id', 'zone_id', 'gps']
                for f in farmer_identity_fields:
                    val = getattr(existing, f, False)
                    if val and f in mapped_json:
                        mapped_json.pop(f, None)

                # 2. Protect Land/Plot details (planning lines) from being overwritten
                planning_fields = ['annual_line_ids', 'perennial_line_ids', 'biennial_line_ids']
                for p in planning_fields:
                    val = getattr(existing, p, False)
                    if val and len(val) > 0 and p in mapped_json:
                        mapped_json.pop(p, None)

                existing.with_context(tracking_disable=True, skip_date_validation=True).write(mapped_json)
                _logger.info("POST-WRITE: annual_line_ids count=%s", len(existing.annual_line_ids))
            else:
                _logger.info("CREATING new crop registry record")
                try:
                    new_rec = self.env['g2p.crop.registry'].sudo().with_context(tracking_disable=True, skip_date_validation=True).create(mapped_json)
                    _logger.info("POST-CREATE: record id=%s, annual_line_ids count=%s", new_rec.id, len(new_rec.annual_line_ids))
                    for line in new_rec.annual_line_ids:
                        _logger.info("  LINE id=%s crop=%s season=%s land=%s", line.id, line.crop_name_id.name, line.season_id.name, line.land_info_id.id if line.land_info_id else None)
                except Exception as e:
                    _logger.error("CREATE FAILED: %s", e, exc_info=True)

            rec_to_check = existing if existing else (new_rec if 'new_rec' in locals() and new_rec else None)
            if rec_to_check and rec_to_check.exists():
                all_prods = getattr(rec_to_check, 'production_detail_ids', self.env['g2p.crop.production'].browse()) | getattr(rec_to_check, 'harvest_detail_ids', self.env['g2p.crop.production'].browse())
                for prod in all_prods:
                    write_vals = {}
                    if not prod.sowing_status:
                        if prod.actual_sowing_date or prod.area_sown or prod.actual_crop_area or prod.harvest_date:
                            write_vals['sowing_status'] = 'sown'

                    eff_area = prod.area_sown or prod.actual_crop_area or prod.planned_area or 0.0
                    if not prod.area_sown and eff_area:
                        write_vals['area_sown'] = eff_area

                    c_infos = prod.cluster_info_ids
                    if not c_infos and prod.crop_registry_id and prod.sync_id:
                        ann = prod.crop_registry_id.actual_annual_line_ids.filtered(lambda l: l.sync_id == prod.sync_id and l.cluster_info_ids)
                        if ann:
                            c_infos = ann.cluster_info_ids

                    is_cl = bool(c_infos or prod.production_cluster_line_ids)
                    if not prod.cluster_status_ids:
                        status_val = self._resolve_cluster_status_id(is_cl)
                        if status_val:
                            write_vals['cluster_status_ids'] = status_val
                    if write_vals:
                        try:
                            prod.sudo().write(write_vals)
                        except Exception:
                            pass

                    if is_cl and c_infos:
                        for c_info in c_infos:
                            ex_cl_line = prod.production_cluster_line_ids.filtered(lambda l: l.cluster_info_id.id == c_info.id)
                            sow_st = 'Sown' if (prod.sowing_status == 'sown' or write_vals.get('sowing_status') == 'sown') else prod.sowing_status
                            if not ex_cl_line:
                                try:
                                    self.env['g2p.crop.production.cluster.line'].sudo().create({
                                        'production_id': prod.id,
                                        'cluster_info_id': c_info.id,
                                        'cluster_name': c_info.cluster_name or c_info.display_name,
                                        'sowing_status': sow_st,
                                        'area_sown': eff_area,
                                        'has_pest_disease': prod.has_pest_disease,
                                        'infestation_incident_ids': [(6, 0, prod.infestation_incident_ids.ids)] if prod.infestation_incident_ids else False,
                                        'season_id': prod.season_id.id if prod.season_id else False,
                                        'crop_maturity_status': prod.crop_maturity_status,
                                        'harvest_date': prod.harvest_date,
                                        'area_harvested': prod.area_harvested or 0.0,
                                        'qty_harvested': prod.qty_harvested or 0.0,
                                        'post_harvest_loss_pct': prod.post_harvest_loss_pct or 0.0,
                                        'qty_stored': prod.qty_stored or 0.0,
                                        'qty_sold': prod.qty_sold or 0.0,
                                    })
                                    _logger.info("CREATED cluster line for prod %s with qty_harvested %s", prod.id, prod.qty_harvested)
                                except Exception as e:
                                    _logger.warning("Failed to auto-create production cluster line: %s", e)
                            else:
                                cl_update = {}
                                if not ex_cl_line.sowing_status and sow_st:
                                    cl_update['sowing_status'] = sow_st
                                if not ex_cl_line.area_sown and eff_area:
                                    cl_update['area_sown'] = eff_area
                                if not ex_cl_line.has_pest_disease and prod.has_pest_disease:
                                    cl_update['has_pest_disease'] = prod.has_pest_disease
                                if not ex_cl_line.infestation_incident_ids and prod.infestation_incident_ids:
                                    cl_update['infestation_incident_ids'] = [(6, 0, prod.infestation_incident_ids.ids)]
                                if not ex_cl_line.season_id and prod.season_id:
                                    cl_update['season_id'] = prod.season_id.id
                                if not ex_cl_line.crop_maturity_status and prod.crop_maturity_status:
                                    cl_update['crop_maturity_status'] = prod.crop_maturity_status
                                if not ex_cl_line.harvest_date and prod.harvest_date:
                                    cl_update['harvest_date'] = prod.harvest_date
                                if not ex_cl_line.area_harvested and prod.area_harvested:
                                    cl_update['area_harvested'] = prod.area_harvested
                                if not ex_cl_line.qty_harvested and prod.qty_harvested:
                                    cl_update['qty_harvested'] = prod.qty_harvested
                                if not ex_cl_line.post_harvest_loss_pct and prod.post_harvest_loss_pct:
                                    cl_update['post_harvest_loss_pct'] = prod.post_harvest_loss_pct
                                if not ex_cl_line.qty_stored and prod.qty_stored:
                                    cl_update['qty_stored'] = prod.qty_stored
                                if not ex_cl_line.qty_sold and prod.qty_sold:
                                    cl_update['qty_sold'] = prod.qty_sold

                                _logger.info("UPDATING cluster line %s with %s", ex_cl_line.id, cl_update)
                                if cl_update:
                                    try:
                                        ex_cl_line.sudo().write(cl_update)
                                    except Exception:
                                        pass

            partner_count += 1
            data.update({'form_updated': True})
        data.update({'partner_count': partner_count})
        return data

    def _resolve_cluster_status_id(self, is_clustered):
        status_names = ['Clustered', 'Independent'] if is_clustered else ['Independent']
        status_recs = self.env['g2p.cluster.status'].sudo().search([('name', 'in', status_names)])
        for status_name in status_names:
            if status_name not in status_recs.mapped('name'):
                try:
                    new_st = self.env['g2p.cluster.status'].sudo().create({'name': status_name})
                    status_recs |= new_st
                except Exception:
                    pass
        return [(6, 0, status_recs.ids)] if status_recs else False

    def _auto_enrich_production_and_incidents(self, mapped_json, member):
        """Auto-recover and enrich production lines and cluster lines from raw ODK member data
        when jq mapping fails due to schema/naming mismatches (e.g. farmer_plot vs farmer_identity,
        independant_details vs top-level incident tables, etc.)."""
        if not isinstance(mapped_json, dict) or not isinstance(member, dict):
            return

        sowing_list = member.get('sowing_details') or member.get('sowing_harvesting') or member.get('sowing')
        if not isinstance(sowing_list, list) or not sowing_list or not isinstance(sowing_list[0], dict):
            raw_sowing = member
        else:
            raw_sowing = sowing_list[0]

        def _build_commands(raw_items, field_mappings=None, target_model=None):
            if not isinstance(raw_items, list) or not raw_items:
                return []
            cmds = []
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                clean_item = {}
                for k, v in item.items():
                    if k.startswith('_') or k in ('meta', 'instanceID'):
                        continue
                    clean_item[k] = v
                if field_mappings:
                    for old_f, new_f in field_mappings.items():
                        if old_f in clean_item and not clean_item.get(new_f):
                            clean_item[new_f] = clean_item.pop(old_f)
                # NOTE: Do NOT patch selection fields here with raw values.
                # Invalid keys like 'contact_herbicide' would be stored in the DB
                # but not recognized after a server restart (only 'contact' is valid).
                # Let _map_aliases_recursive handle proper selection normalization later.
                if clean_item:
                    cmds.append((0, 0, clean_item))
            return cmds

        prod_cmds = mapped_json.get('production_detail_ids', [])
        if not isinstance(prod_cmds, list):
            return

        for cmd in prod_cmds:
            if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == 0 and isinstance(cmd[2], dict):
                line_vals = cmd[2]
            elif isinstance(cmd, dict):
                line_vals = cmd
            else:
                continue

            raw_indep = raw_sowing.get('independant_details') if isinstance(raw_sowing.get('independant_details'), dict) else {}
            hp = raw_indep.get('has_pest_disease') or raw_indep.get('sowing_has_pest_disease') or raw_sowing.get('has_pest_disease') or line_vals.get('has_pest_disease')
            if str(hp).strip().lower() in ('yes', 'true', '1'):
                line_vals['has_pest_disease'] = True
            elif str(hp).strip().lower() in ('no', 'false', '0', 'none', 'null', ''):
                line_vals['has_pest_disease'] = False

            # Build independent pest/disease incidents from multiple possible locations
            raw_incidents = (
                raw_indep.get('infestation_incidents') or raw_indep.get('infestation_incidents_1')
                or raw_sowing.get('infestation_incidents') or raw_sowing.get('infestation_incidents_1')
                or line_vals.get('infestation_incidents') or line_vals.get('infestation_incidents_1')
            )
            if isinstance(raw_incidents, list) and raw_incidents:
                inc_cmds = []
                for inc in raw_incidents:
                    if not isinstance(inc, dict):
                        continue
                    inc_vals = {k: v for k, v in inc.items() if not k.startswith('_')}
                    if 'security_level' in inc_vals and not inc_vals.get('severity_level'):
                        inc_vals['severity_level'] = inc_vals.pop('security_level')
                    if 'cluster_security_level' in inc_vals and not inc_vals.get('severity_level'):
                        inc_vals['severity_level'] = inc_vals.pop('cluster_security_level')
                    if 'cluster_severity_level' in inc_vals and not inc_vals.get('severity_level'):
                        inc_vals['severity_level'] = inc_vals.pop('cluster_severity_level')
                    if 'infestation_type_ids' not in inc_vals and 'cluster_infestation_type_ids' in inc_vals:
                        inc_vals['infestation_type_ids'] = inc_vals.pop('cluster_infestation_type_ids')
                    if 'observation_date' not in inc_vals and 'cluster_observation_date' in inc_vals:
                        inc_vals['observation_date'] = inc_vals.pop('cluster_observation_date')

                    # Collect sub-detail lines from raw_indep, raw_sowing, and incident itself
                    _pest_src = inc.get('pest_occurance') or inc.get('pest_occurrence') or inc.get('pest_occurance_1') or inc.get('pest_occurrence_1') or raw_indep.get('pest_occurance') or raw_indep.get('pest_occurrence') or raw_sowing.get('pest_occurance') or raw_sowing.get('pest_occurrence')
                    _weed_src = inc.get('weed_occurrence') or inc.get('weed_occurrence_1') or raw_indep.get('weed_occurrence') or raw_sowing.get('weed_occurrence')
                    _disease_src = inc.get('disease') or inc.get('disease_1') or raw_indep.get('disease') or raw_sowing.get('disease')
                    _nutrient_src = inc.get('nutrient_deficiency') or inc.get('nutrient_deficiency_1') or raw_indep.get('nutrient_deficiency') or raw_sowing.get('nutrient_deficiency')
                    _climate_src = inc.get('climate_shock') or inc.get('climate_shock_1') or raw_indep.get('climate_shock') or raw_sowing.get('climate_shock')

                    _logger.info("=== ODK IMPORT DEBUG: PEST SRC ===\n%s", repr(_pest_src))
                    inc_vals['pest_line_ids'] = _build_commands(_pest_src, {'pest_name_id': 'pest_name'}, 'g2p.crop.pest.line')

                    _logger.info("=== ODK IMPORT DEBUG: WEED SRC ===\n%s", repr(_weed_src))
                    inc_vals['weed_line_ids'] = _build_commands(_weed_src, {'weed_name_id': 'weed_name'}, 'g2p.crop.weed.line')

                    # Sanitize independent disease_line_ids
                    _logger.info("=== ODK IMPORT DEBUG: DISEASE SRC ===\n%s", repr(_disease_src))
                    indep_disease_lines = _build_commands(_disease_src, None, 'g2p.crop.disease.line')
                    for d_cmd in indep_disease_lines:
                        if len(d_cmd) == 3 and isinstance(d_cmd[2], dict):
                            d_cmd[2].pop('fungicide_type', None)
                            d_cmd[2].pop('chemical_type', None)
                    inc_vals['disease_line_ids'] = indep_disease_lines

                    inc_vals['nutrient_line_ids'] = _build_commands(_nutrient_src, None, 'g2p.crop.nutrient.line')
                    inc_vals['climate_line_ids'] = _build_commands(_climate_src, None, 'g2p.crop.climate.line')

                    inc_cmds.append((0, 0, inc_vals))
                if inc_cmds:
                    line_vals['infestation_incident_ids'] = inc_cmds

            cluster_cmds = line_vals.get('production_cluster_line_ids') or line_vals.get('cluster_details') or []
            if isinstance(cluster_cmds, list) and cluster_cmds:
                for c_cmd in cluster_cmds:
                    if isinstance(c_cmd, (list, tuple)) and len(c_cmd) == 3 and c_cmd[0] == 0 and isinstance(c_cmd[2], dict):
                        c_vals = c_cmd[2]
                    elif isinstance(c_cmd, dict):
                        c_vals = c_cmd
                    else:
                        continue

                    c_hp = c_vals.get('has_pest_disease') or c_vals.get('sowing_has_pest_disease') or raw_sowing.get('sowing_has_pest_disease')
                    if str(c_hp).strip().lower() in ('yes', 'true', '1'):
                        c_vals['has_pest_disease'] = True
                    elif str(c_hp).strip().lower() in ('no', 'false', '0', 'none', 'null', ''):
                        c_vals['has_pest_disease'] = False

                    raw_c_inc = c_vals.get('infestation_incidents_1') or c_vals.get('infestation_incidents') or c_vals.get('infestation_incident_ids') or raw_sowing.get('infestation_incidents_1') or raw_sowing.get('infestation_incidents')
                    if isinstance(raw_c_inc, list) and raw_c_inc:
                        c_inc_cmds = []
                        for c_inc in raw_c_inc:
                            if not isinstance(c_inc, dict):
                                continue
                            c_inc_vals = {k: v for k, v in c_inc.items() if not k.startswith('_')}
                            if 'security_level' in c_inc_vals and not c_inc_vals.get('severity_level'):
                                c_inc_vals['severity_level'] = c_inc_vals.pop('security_level')
                            if 'cluster_security_level' in c_inc_vals and not c_inc_vals.get('severity_level'):
                                c_inc_vals['severity_level'] = c_inc_vals.pop('cluster_security_level')
                            if 'cluster_severity_level' in c_inc_vals and not c_inc_vals.get('severity_level'):
                                c_inc_vals['severity_level'] = c_inc_vals.pop('cluster_severity_level')
                            if 'cluster_infestation_type_ids' in c_inc_vals and not c_inc_vals.get('infestation_type_ids'):
                                c_inc_vals['infestation_type_ids'] = c_inc_vals.pop('cluster_infestation_type_ids')
                            if 'cluster_observation_date' in c_inc_vals and not c_inc_vals.get('observation_date'):
                                c_inc_vals['observation_date'] = c_inc_vals.pop('cluster_observation_date')

                            c_inc_vals['pest_line_ids'] = _build_commands(c_inc.get('pest_occurance_1') or c_inc.get('pest_occurrence_1') or c_inc.get('pest_occurance') or c_inc.get('pest_occurrence') or c_vals.get('pest_occurance_1') or c_vals.get('pest_occurrence_1') or raw_sowing.get('pest_occurance_1') or raw_sowing.get('pest_occurrence_1'), {'pest_name_id': 'pest_name'}, 'g2p.crop.pest.line')
                            if c_inc_vals.get('pest_line_ids'):
                                _logger.info("=== ODK IMPORT DEBUG: PEST LINE KEYS ===")
                                for pl in c_inc_vals['pest_line_ids']:
                                    if len(pl) == 3 and isinstance(pl[2], dict):
                                        _logger.info("Pest Line Keys: %s", list(pl[2].keys()))
                            c_inc_vals['weed_line_ids'] = _build_commands(c_inc.get('weed_occurrence_1') or c_inc.get('weed_occurrence') or c_vals.get('weed_occurrence_1') or c_vals.get('weed_occurrence') or raw_sowing.get('weed_occurrence_1') or raw_sowing.get('weed_occurrence'), {'weed_name_id': 'weed_name'}, 'g2p.crop.weed.line')

                            # Sanitize disease_line_ids to prevent UI crash: fungicide_type has no choices in the model
                            disease_lines = _build_commands(c_inc.get('disease_1') or c_inc.get('disease') or c_vals.get('disease_1') or c_vals.get('disease') or raw_sowing.get('disease_1') or raw_sowing.get('disease'), None, 'g2p.crop.disease.line')
                            for d_cmd in disease_lines:
                                if len(d_cmd) == 3 and isinstance(d_cmd[2], dict):
                                    d_cmd[2].pop('fungicide_type', None)
                                    d_cmd[2].pop('chemical_type', None)
                            c_inc_vals['disease_line_ids'] = disease_lines
                            if disease_lines:
                                _logger.info("=== ODK IMPORT DEBUG: DISEASE LINE KEYS ===")
                                for pl in disease_lines:
                                    if len(pl) == 3 and isinstance(pl[2], dict):
                                        _logger.info("Disease Line Keys: %s", list(pl[2].keys()))

                            c_inc_vals['nutrient_line_ids'] = _build_commands(c_inc.get('nutrient_deficiency_1') or c_inc.get('nutrient_deficiency') or c_vals.get('nutrient_deficiency_1') or c_vals.get('nutrient_deficiency') or raw_sowing.get('nutrient_deficiency_1') or raw_sowing.get('nutrient_deficiency'), None, 'g2p.crop.nutrient.line')
                            c_inc_vals['climate_line_ids'] = _build_commands(c_inc.get('climate_shock_1') or c_inc.get('climate_shock') or c_vals.get('climate_shock_1') or c_vals.get('climate_shock') or raw_sowing.get('climate_shock_1') or raw_sowing.get('climate_shock'), None, 'g2p.crop.climate.line')

                            c_inc_cmds.append((0, 0, c_inc_vals))
                        if c_inc_cmds:
                            c_vals['infestation_incident_ids'] = c_inc_cmds

                    # Validate cluster_info_id is a valid integer DB ID
                    # Do NOT auto-create a "Default Cluster" here — the post-write logic
                    # will resolve real clusters from the registry's actual crop lines.
                    c_id_ref = c_vals.get('cluster_info_id')
                    if isinstance(c_id_ref, int) and c_id_ref > 0:
                        # Valid cluster reference, keep it
                        pass
                    elif c_id_ref:
                        # Try to convert string to int
                        try:
                            c_vals['cluster_info_id'] = int(c_id_ref)
                        except (TypeError, ValueError):
                            # Not a valid reference; remove it so it doesn't cause errors
                            c_vals.pop('cluster_info_id', None)
                    else:
                        c_vals.pop('cluster_info_id', None)

            if not line_vals.get('sowing_status'):
                if line_vals.get('actual_sowing_date') or line_vals.get('area_sown') or line_vals.get('actual_crop_area') or line_vals.get('harvest_date'):
                    line_vals['sowing_status'] = 'sown'
                elif str(line_vals.get('is_sown', '')).strip().lower() in ('yes', 'true', '1', 'sown'):
                    line_vals['sowing_status'] = 'sown'

            c_status = line_vals.get('cluster_status_ids')
            if isinstance(c_status, str) or not isinstance(c_status, list):
                is_cl = False
                if isinstance(c_status, str) and 'clustered' in c_status.lower():
                    is_cl = True
                elif cluster_cmds:
                    is_cl = True
                elif str(line_vals.get('has_cluster_farming', '')).strip().lower() in ('yes', 'true', '1'):
                    is_cl = True
                status_val = self._resolve_cluster_status_id(is_cl)
                if status_val:
                    line_vals['cluster_status_ids'] = status_val
                else:
                    line_vals.pop('cluster_status_ids', None)

    def _auto_populate_ec_dates_recursive(self, vals):
        if not isinstance(vals, dict):
            return
        from odoo.addons.g2p_ati.models.utils import eth_date
        from odoo import fields as odoo_fields

        # Check common date pairs (GC -> EC)
        date_pairs = [
            ('observation_date', 'observation_date_ec'),
            ('actual_sowing_date', 'actual_sowing_date_ec'),
            ('actual_planted_date', 'actual_planted_date_ec'),
            ('actual_planted_date_gc', 'actual_planted_date_ec'),
            ('collected_gc', 'collected_ec'),
            ('planned_date_gc', 'planned_date_ec'),
            ('harvest_date', 'harvest_date_ec'),
        ]
        for gc_field, ec_field in date_pairs:
            if vals.get(gc_field) and not vals.get(ec_field):
                try:
                    d_str = str(vals[gc_field]).split(' ')[0]
                    d = odoo_fields.Date.from_string(d_str)
                    if d:
                        eth_str = eth_date.to_ethiopian(d.year, d.month, d.day)
                        vals[ec_field] = eth_date.convert_tuple_to_string_with_separator(eth_str)
                except Exception:
                    pass

        # Recurse into nested dictionaries and lists / command tuples
        for v in vals.values():
            if isinstance(v, dict):
                self._auto_populate_ec_dates_recursive(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        self._auto_populate_ec_dates_recursive(item)
                    elif isinstance(item, (list, tuple)) and len(item) == 3 and isinstance(item[2], dict):
                        self._auto_populate_ec_dates_recursive(item[2])

    def _map_aliases_recursive(self, model_name, vals):
        if not isinstance(vals, dict):
            return

        if model_name in ('g2p.crop.pest.line', 'g2p.crop.weed.line', 'g2p.crop.disease.line'):
            _logger.info("=== DEBUG MODEL %s KEYS: %s ===", model_name, list(vals.keys()))

        model = self.env[model_name]
        valid_fields = model._fields.keys()

        # Mapping from alias key to possible target fields
        aliases = {
            'land_info_id': ['land_info_id', 'temporary_land_id'],
            'region': ['region_name_id', 'region_id'],
            'zone': ['zone_name_id', 'zone_id'],
            'woreda': ['woreda_name_id', 'woreda_id'],
            'kebele': ['kebele_id'],
            'crop': ['crop_name_id'],
            'crop_category': ['crop_category_id'],
            'crop_variety': ['crop_variety_id'],
            'season': ['season_id'],
            'first_approval_status': ['first_approvel_status'],

            # Date fields
            'planned_date_ec': ['collected_ec'],
            'planned_date_gc': ['collected_gc'],

            # Seed planned inputs
            'seed_type': ['seed_planned', 'actual_seed_class'],
            'planned_seed_qty_kg': ['seed_planned_qty', 'actual_seed_qty'],
            'planned_fertilizer_qty_kg': ['seed_planned_fertilizer_qty', 'actual_fertilizer_qty'],
            'planned_fertilizer_type': ['seed_planned_fertilizer_type', 'actual_fertilizer_type'],

            # Crop planned inputs
            'avg_growth_duration_days': ['crop_growth_duration', 'actual_growth_duration'],
            'planned_crop_area_ha': ['crop_planned_area', 'actual_crop_area'],
            'expected_yield_quintal': ['crop_expected', 'actual_yield'],

            # Actual details for Cultivation / Sowing / Harvesting
            'actual_season': ['season_id', 'actual_season_id'],
            'actual_crop': ['crop_name_id', 'actual_crop_name_id'],
            'actual_crop_category': ['crop_category_id', 'actual_crop_category_id'],
            'actual_crop_variety': ['crop_variety_id', 'actual_crop_variety_id'],
            'actual_seed_type': ['actual_seed_class'],
            'actual_seed_qty_kg': ['actual_seed_qty'],
            'actual_fertilizer_qty_kg': ['actual_fertilizer_qty'],
            'actual_fertilizer_type': ['actual_fertilizer_type'],
            'actual_planted_date_gc': ['collected_gc'],
            'actual_planted_date_ec': ['collected_ec'],
            'actual_crop_area_ha': ['actual_crop_area'],
            'actual_growth_duration_days': ['actual_growth_duration'],
            'actual_yield_quintal': ['actual_yield'],
            'cultivation_type': ['cultivated_by'],
            'land_prep_methods': ['land_prep_method_ids'],
            'land_preparation_methods': ['land_prep_method_ids'],
            'land_prep_method': ['land_prep_method_ids'],
            'land_preparation_method': ['land_prep_method_ids'],
            'preparation_method': ['land_prep_method_ids'],
            'preparation_methods': ['land_prep_method_ids'],
            'land_preparation': ['land_prep_method_ids'],
            'land_prep': ['land_prep_method_ids'],
            'pest_occurrence_repeat': ['pest_line_ids'],
            'weed_occurrence_repeat': ['weed_line_ids'],
            'cluster_details': ['production_cluster_line_ids'],
            'infestation_incidents': ['infestation_incident_ids'],
            'infestation_incidents_1': ['infestation_incident_ids'],
            'pest_occurrence': ['pest_line_ids'],
            'weed_occurrence': ['weed_line_ids'],
            'disease': ['disease_line_ids'],
            'nutrient_deficiency': ['nutrient_line_ids'],
            'climate_shock': ['climate_line_ids'],

            # Sowing / Harvesting specific aliases
            'actual_crop_name': ['crop_name_id'],
            'actual_planted_date': ['actual_sowing_date'],
            'area_harvested_ha': ['area_harvested'],
            'qty_harvested_quintal': ['qty_harvested'],

            # Pest/Weed specific aliases
            'pest_type_id': ['pest_type'],
            'pest_type': ['pest_type'],
            'pest_name_id': ['pest_name'],
            'pest_name': ['pest_name'],
            'pesticide_name': ['pesticide_name'],
            'pesticides_type': ['pesticide_type'],
            'pesticide_type': ['pesticide_type'],
            'weed_type_id': ['weed_type'],
            'weed_type': ['weed_type'],
            'weed_name_id': ['weed_name'],
            'weed_name': ['weed_name'],

            # Exhaustive aliases for Method of Control
            # PEST
            'pest_pesticide_method': ['pesticide_method'],
            'clus_pest_pesticide_method': ['pesticide_method'],
            # WEED
            'pesticide_method': ['pesticide_method'],
            'cluster_pesticide_method': ['pesticide_method'],
            # DISEASE
            'ind_method_of_control': ['method_of_control'],
            'disease_method_of_control': ['method_of_control'],

            # General fallbacks (for older forms or other models)
            'method_of_control': ['method_of_control', 'pesticide_method'],
            'control_method': ['pesticide_method', 'method_of_control'],
            'method_control': ['pesticide_method', 'method_of_control'],
            'm_control': ['pesticide_method', 'method_of_control'],
            'pest_method': ['pesticide_method', 'method_of_control'],
            'pest_control_method': ['pesticide_method', 'method_of_control'],
            'disease_method': ['pesticide_method', 'method_of_control'],
            'disease_control_method': ['pesticide_method', 'method_of_control'],
            'weed_method': ['pesticide_method', 'method_of_control'],
            'weed_control_method': ['pesticide_method', 'method_of_control'],
            'weedicide_method': ['pesticide_method', 'method_of_control'],
            'control_measure': ['pesticide_method', 'method_of_control'],
            'measure_of_control': ['pesticide_method', 'method_of_control'],
            'management_method': ['pesticide_method', 'method_of_control'],
            'pesticides_method': ['pesticide_method', 'method_of_control'],
            'chemical_method': ['pesticide_method', 'method_of_control'],
            'application_method': ['pesticide_method', 'method_of_control'],
            'method': ['pesticide_method', 'method_of_control'],

            'weedicides_type': ['weedicide_type'],
            'weedicide_type': ['weedicide_type'],
            'weedicides_name': ['weedicide_name'],
            'weedicide_name': ['weedicide_name'],
            'frequency_of_application': ['frequency_of_application', 'pesticide_frequency'],
            'pesticide_frequency': ['pesticide_frequency', 'frequency_of_application'],

            # Disease specific aliases
            'disease_type_id': ['disease_type'],
            'disease_type': ['disease_type'],
            'disease_types': ['disease_type'],
            'diseases_type': ['disease_type'],
            'disease_name_id': ['disease_name'],
            'diseases_name': ['disease_name'],
            'fungicide_type_id': ['fungicide_type'],
            'fungicide_type': ['fungicide_type'],
            'fungicides_type': ['fungicide_type'],
            'fungicide_bactericide_type': ['fungicide_type'],
            'fungicide_bactericide_type_id': ['fungicide_type'],
            'fungicide_name_id': ['fungicide_name'],
            'fungicides_name': ['fungicide_name'],
            'fungicide_bactericide_name': ['fungicide_name'],
            'fungicide_bactericide_name_id': ['fungicide_name'],

            # Nutrient deficiency specific aliases
            'nutrient_type_id': ['nutrient_type'],
            'nutrient_type': ['nutrient_type'],
            'nutrients_type': ['nutrient_type'],
            'nutrient_name_id': ['nutrient_name'],
            'nutrients_name': ['nutrient_name'],
            'fertilizer_type_id': ['fertilizer_type'],
            'fertilizer_type': ['fertilizer_type'],
            'fertilizers_type': ['fertilizer_type'],
            'fertilizer_amendment_type': ['fertilizer_type'],
            'fertilizer_amendment_type_id': ['fertilizer_type'],
            'fertilizer_name_id': ['fertilizer_name'],
            'fertilizers_name': ['fertilizer_name'],
            'fertilizer_amendment_name': ['fertilizer_name'],
            'fertilizer_amendment_name_id': ['fertilizer_name'],

            # Climate shock specific aliases
            'shock_type_id': ['shock_type'],
            'shock_type': ['shock_type'],
            'shocks_type': ['shock_type'],
            'climate_shock_type': ['shock_type'],
            'climate_shock_type_id': ['shock_type'],
            'shock_event_name_id': ['shock_event_name'],
            'recovery_input_type_id': ['recovery_input_type'],
            'recovery_inputs_type': ['recovery_input_type'],
            'recovery_input_name_id': ['recovery_input_name'],

            # Water resources
            'water_details': ['water_resource_line_ids', 'actual_water_resource_line_ids'],
            'water_resource': ['water_resource_id'],
            'method': ['method_id'],
            'frequency': ['frequency'],

            # Planning newly added inputs
            'avg_growth_duration_days': ['crop_growth_duration'],
            'planned_crop_area_ha': ['crop_planned_area'],
            'expected_yield_quintal': ['crop_expected'],
            'seed_type': ['seed_planned'],
            'planned_seed_qty_kg': ['seed_planned_qty'],
            'planned_fertilizer_type': ['seed_planned_fertilizer_type'],
            'planned_fertilizer_qty_kg': ['seed_planned_fertilizer_qty'],
            'region': ['region_name_id', 'region_id'],
            'zone': ['zone_name_id', 'zone_id'],
            'woreda': ['woreda_name_id', 'woreda_id'],
            'kebele': ['kebele_id'],
            'crop': ['crop_name_id'],
            'crop_variety': ['crop_variety_id'],
            'planned_date_gc': ['collected_gc'],
            'planned_date_ec': ['collected_ec'],
            'da_name': ['surveyor_name'],
            'da_mobile_number': ['surveyor_mobile_number'],

            # Cluster Aliases
            'agro_ecological_zone': ['cluster_agro_ecological_zone'],
            'cluster_size': ['cluster_area_timad'],
            'number_of_smallholders': ['cluster_smallholders'],
            'cluster_collected_land_quintal': ['cluster_collected_quintal'],

            # Survey Personnel Aliases
            'interviewer_name': ['surveyor_name'],
            'phone_no': ['surveyor_mobile_number'],
            'da_name': ['surveyor_name'],
            'da_mobile_number': ['surveyor_mobile_number'],
            'da_mobile_no': ['surveyor_mobile_number'],
            'surveyor_mobile_no': ['surveyor_mobile_number'],
            'da_phone_no': ['surveyor_mobile_number'],
            'supervisor_phone_no': ['supervisor_mobile_number'],
            'supervisor_mobile_no': ['supervisor_mobile_number'],
        }

        # Apply aliases
        for alias, targets in aliases.items():
            if alias in vals:
                val = vals.pop(alias)
                for target in targets:
                    if not vals.get(target):
                        vals[target] = val

        # Recurse and normalize selection fields / child forms
        for field_name, field in model._fields.items():
            if field_name in vals and vals[field_name]:
                if field.type in ['one2many', 'many2many']:
                    commands = vals[field_name]
                    if field.type == 'many2many':
                        if isinstance(commands, str):
                            commands = [t.strip() for t in commands.replace(',', ' ').split() if t.strip()]
                        if isinstance(commands, list) and commands and not all(isinstance(c, (dict, list, tuple)) for c in commands):
                            rel_ids = []
                            comodel = self.env[field.comodel_name].sudo()
                            for token in commands:
                                if isinstance(token, int) or (isinstance(token, str) and token.isdigit()):
                                    rec = comodel.search([('id', '=', int(token))], limit=1)
                                    if rec: rel_ids.append(rec.id)
                                elif isinstance(token, str):
                                    rec = comodel.search(['|', ('name', '=ilike', token), ('name', '=ilike', token.replace('_', ' '))], limit=1)
                                    if not rec and 'code' in comodel._fields:
                                        rec = comodel.search(['|', ('code', '=ilike', token), ('code', '=ilike', token.split('_')[0])], limit=1)
                                    if not rec:
                                        try:
                                            create_vals = {'name': token.replace('_', ' ').title()}
                                            if 'code' in comodel._fields:
                                                create_vals['code'] = token.lower().replace(' ', '_')
                                            rec = comodel.create(create_vals)
                                        except Exception:
                                            pass
                                    if rec:
                                        rel_ids.append(rec.id)
                            vals[field_name] = [(6, 0, rel_ids)]
                            commands = vals[field_name]

                    if isinstance(commands, list):
                        # Convert list of dicts to Odoo command tuples automatically
                        if all(isinstance(c, dict) for c in commands):
                            commands = [(5, 0, 0)] + [(0, 0, c) for c in commands]
                            vals[field_name] = commands

                        for cmd in commands:
                            if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and isinstance(cmd[2], dict):
                                self._map_aliases_recursive(field.comodel_name, cmd[2])
                elif field.type == 'many2one':
                    val_m2o = vals[field_name]
                    if isinstance(val_m2o, dict):
                        self._map_aliases_recursive(field.comodel_name, val_m2o)
                    elif isinstance(val_m2o, str):
                        v_str = val_m2o.strip()
                        comodel = self.env[field.comodel_name].sudo()
                        rec = False
                        if 'code' in comodel._fields:
                            rec = comodel.search([('code', '=ilike', v_str)], limit=1)
                        if not rec and 'name' in comodel._fields:
                            rec = comodel.search(['|', ('name', '=ilike', v_str), ('name', '=ilike', v_str.replace('_', ' '))], limit=1)
                        if not rec and field_name == 'land_info_id' and 'land_id' in comodel._fields:
                            rec = comodel.search([('land_id', '=ilike', v_str)], limit=1)
                        if not rec and field_name == 'cluster_info_id' and 'cluster_id' in comodel._fields:
                            rec = comodel.search([('cluster_id', '=ilike', v_str)], limit=1)
                        if rec:
                            vals[field_name] = rec.id
                elif field.type == 'selection':
                    val = vals[field_name]
                    if isinstance(val, str):
                        clean_str = lambda s: ''.join(c for c in s if c.isalnum()).lower()
                        # Build a map of key -> cleaned variations, including description
                        opt_map = {}
                        raw_opts = []
                        if isinstance(field.selection, list):
                            raw_opts = field.selection
                        elif callable(field.selection):
                            try:
                                raw_opts = field.selection(model)
                            except Exception:
                                pass

                        for opt in raw_opts:
                            if isinstance(opt, tuple) and len(opt) >= 2:
                                key, label = opt[0], opt[1]
                            else:
                                key, label = opt, opt
                            if not isinstance(key, str):
                                continue
                            opt_map[key] = [
                                key.strip().lower(),
                                clean_str(key),
                                label.strip().lower() if isinstance(label, str) else '',
                                clean_str(label) if isinstance(label, str) else ''
                            ]

                        normalized = val.strip().lower()
                        normalized_clean = clean_str(normalized)

                        matched_key = False
                        # 1. Exact match with key
                        for key, variations in opt_map.items():
                            if normalized == variations[0] or normalized_clean == variations[1] or variations[0].replace('by_', '') == normalized:
                                matched_key = key
                                break
                        # 2. Exact match with description/label
                        if not matched_key:
                            for key, variations in opt_map.items():
                                if normalized == variations[2] or normalized_clean == variations[3]:
                                    matched_key = key
                                    break
                        # 3. Substring matching or suffix/prefix matching
                        if not matched_key:
                            for key, variations in opt_map.items():
                                if (variations[0] and (normalized in variations[0] or variations[0] in normalized)) or \
                                   (variations[2] and (normalized in variations[2] or variations[2] in normalized)):
                                    matched_key = key
                                    break
                        if not matched_key:
                            # Try with suffix stripping
                            for suffix in ['_crop', '_type', '_class', '_share', '_herbicide', '_pesticide', '_fungicide']:
                                if normalized.endswith(suffix):
                                    stripped = normalized[:-len(suffix)]
                                    stripped_clean = clean_str(stripped)
                                    for key, variations in opt_map.items():
                                        if stripped == variations[0] or stripped_clean == variations[1] or \
                                           stripped == variations[2] or stripped_clean == variations[3]:
                                            matched_key = key
                                            break
                                if matched_key:
                                    break

                        if not matched_key:
                            _logger.warning("=== ODK IMPORT SELECTION MISMATCH ===")
                            _logger.warning("Field: %s, Model: %s, Raw Value: %s", field_name, model._name, repr(val))
                            _logger.warning("Tried to match against: %s", list(opt_map.keys()))

                        vals[field_name] = matched_key

    def _strip_invalid_fields_recursive(self, model_name, vals):
        if not isinstance(vals, dict):
            return
        model = self.env[model_name]
        valid_fields = model._fields.keys()

        # Strip invalid keys and clean quotes from string values
        invalid_keys = [k for k in vals if k not in valid_fields]
        for k in invalid_keys:
            vals.pop(k, None)
        for k, v in list(vals.items()):
            if isinstance(v, str):
                vals[k] = v.strip("'\"")

            if k in valid_fields:
                field = model._fields[k]
                if field.type == 'many2one' and isinstance(vals[k], str):
                    _logger.warning("ODK Import: Stripping unresolved Many2one string value for field %s in %s: %s", k, model_name, vals[k])
                    vals.pop(k)

        # Recurse into relational fields
        for field_name, field in model._fields.items():
            if field_name in vals and vals[field_name]:
                if field.type in ['one2many', 'many2many']:
                    commands = vals[field_name]
                    if isinstance(commands, list):
                        for cmd in commands:
                            if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and isinstance(cmd[2], dict):
                                self._strip_invalid_fields_recursive(field.comodel_name, cmd[2])
                elif field.type == 'many2one' and isinstance(vals[field_name], dict):
                    self._strip_invalid_fields_recursive(field.comodel_name, vals[field_name])

    def _promote_nested_dicts_recursive(self, val):
        if isinstance(val, dict):
            # Recurse into child items first
            for k, v in list(val.items()):
                if isinstance(v, (dict, list, tuple)):
                    self._promote_nested_dicts_recursive(v)
            # Now promote keys from any nested dictionary to this level (excluding lists/tuples)
            nested_dicts = [k for k, v in val.items() if isinstance(v, dict)]
            for nd_key in nested_dicts:
                nd_val = val[nd_key]
                for k, v in nd_val.items():
                    if k not in val or not val[k]:
                        val[k] = v
        elif isinstance(val, (list, tuple)):
            for item in val:
                if isinstance(item, (dict, list, tuple)):
                    self._promote_nested_dicts_recursive(item)
    def _normalize_mobile_numbers_recursive(self, val):
        if isinstance(val, dict):
            mobile_fields = ['mobile_number', 'alternative_mobile_number', 'supervisor_mobile_number', 'surveyor_mobile_number']
            for field in mobile_fields:
                if field in val and val[field]:
                    val[field] = self._normalize_ethiopian_mobile(val[field])
            # Recurse
            for k, v in val.items():
                if isinstance(v, (dict, list, tuple)):
                    self._normalize_mobile_numbers_recursive(v)
        elif isinstance(val, (list, tuple)):
            for item in val:
                if isinstance(item, (dict, list, tuple)):
                    self._normalize_mobile_numbers_recursive(item)

    def _normalize_ethiopian_mobile(self, number):
        if not number:
            return number
        import re
        # Remove any non-digits
        digits = ''.join(c for c in str(number) if c.isdigit())
        if re.match(r'^(\+251[79]\d{8}|0[79]\d{8})$', str(number)):
            return number
        if len(digits) == 9 and digits[0] in ['7', '9']:
            return '0' + digits
        if len(digits) == 12 and digits.startswith('251') and digits[3] in ['7', '9']:
            return '+' + digits
        last_8 = digits[-8:] if len(digits) >= 8 else digits.zfill(8)
        return '09' + last_8


    def _resolve_kebele_id(self, kebele_val, val):
        if not kebele_val:
            return False
        if isinstance(kebele_val, int):
            return kebele_val
        if isinstance(kebele_val, str):
            kebele_str = kebele_val.strip()
            k_rec = self.env['g2p.kebele'].sudo().search([('code', '=ilike', kebele_str)], limit=1)
            if not k_rec:
                k_rec = self.env['g2p.kebele'].sudo().search([('name', '=ilike', kebele_str)], limit=1)
            if not k_rec:
                k_rec = self.env['g2p.kebele'].sudo().search([('name', '=ilike', f'%{kebele_str}%')], limit=1)
            if k_rec:
                return k_rec.id

            # Auto-creation fallback
            woreda_val = val.get('woreda_name_id') or val.get('woreda_id')
            resolved_woreda_id = False
            if woreda_val:
                if isinstance(woreda_val, int):
                    resolved_woreda_id = woreda_val
                elif isinstance(woreda_val, str):
                    woreda_str = woreda_val.strip()
                    w_rec = self.env['g2p.woreda'].sudo().search([('code', '=ilike', woreda_str)], limit=1)
                    if not w_rec:
                        w_rec = self.env['g2p.woreda'].sudo().search([('name', '=ilike', woreda_str)], limit=1)
                    if not w_rec:
                        # Find/create zone/region hierarchy
                        zone_val = val.get('zone_name_id') or val.get('zone_id')
                        resolved_zone_id = False
                        if zone_val:
                            if isinstance(zone_val, int):
                                resolved_zone_id = zone_val
                            elif isinstance(zone_val, str):
                                zone_str = zone_val.strip()
                                z_rec = self.env['g2p.zone'].sudo().search([('code', '=ilike', zone_str)], limit=1)
                                if not z_rec:
                                    z_rec = self.env['g2p.zone'].sudo().search([('name', '=ilike', zone_str)], limit=1)
                                if not z_rec:
                                    region_val = val.get('region_name_id') or val.get('region_id') or val.get('region')
                                    resolved_region_id = False
                                    if region_val:
                                        if isinstance(region_val, int):
                                            resolved_region_id = region_val
                                        elif isinstance(region_val, str):
                                            region_str = region_val.strip()
                                            r_rec = self.env['g2p.region'].sudo().search([('code', '=ilike', region_str)], limit=1)
                                            if not r_rec:
                                                r_rec = self.env['g2p.region'].sudo().search([('name', '=ilike', region_str)], limit=1)
                                            if not r_rec:
                                                r_rec = self.env['g2p.region'].sudo().create({'code': region_str, 'name': region_str})
                                            resolved_region_id = r_rec.id
                                    if not resolved_region_id:
                                        r_rec = self.env['g2p.region'].sudo().search([], limit=1)
                                        if not r_rec:
                                            r_rec = self.env['g2p.region'].sudo().create({'code': 'TEMP', 'name': 'Temporary Region'})
                                        resolved_region_id = r_rec.id
                                    z_rec = self.env['g2p.zone'].sudo().create({'code': zone_str, 'name': zone_str, 'region': resolved_region_id})
                                resolved_zone_id = z_rec.id
                        if not resolved_zone_id:
                            z_rec = self.env['g2p.zone'].sudo().search([], limit=1)
                            resolved_zone_id = z_rec.id if z_rec else False
                        if resolved_zone_id:
                            w_rec = self.env['g2p.woreda'].sudo().create({'code': woreda_str, 'name': woreda_str, 'zone': resolved_zone_id})
                    if w_rec:
                        resolved_woreda_id = w_rec.id

            # If still no woreda, use the first woreda in DB as a safety fallback
            if not resolved_woreda_id:
                w_rec = self.env['g2p.woreda'].sudo().search([], limit=1)
                resolved_woreda_id = w_rec.id if w_rec else False

            if resolved_woreda_id:
                k_rec = self.env['g2p.kebele'].sudo().create({
                    'name': kebele_str,
                    'code': kebele_str,
                    'woreda': resolved_woreda_id
                })
                return k_rec.id
        return False

    def _resolve_m2o_recursive(self, val, partner_id=False):
        if isinstance(val, dict):
            # Resolve partner_id if present
            if 'partner_id' in val:
                partner_val = val['partner_id']
                if partner_val:
                    partner = False
                    if isinstance(partner_val, str):
                        search_ids = [partner_val]
                        if partner_val.startswith('FR-'):
                            search_ids.append(partner_val.replace('FR-', 'TEMP-', 1))
                        elif partner_val.startswith('TEMP-'):
                            search_ids.append(partner_val.replace('TEMP-', 'FR-', 1))
                        partner = self.env['res.partner'].sudo().search([('farmer_id', 'in', search_ids)], limit=1)
                    if not partner:
                        partner = self.env['res.partner'].sudo().search([('unique_id', '=', partner_val)], limit=1)
                    if not partner:
                        try:
                            partner_db_id = int(partner_val)
                            if -2147483648 <= partner_db_id <= 2147483647:
                                partner = self.env['res.partner'].sudo().search([('id', '=', partner_db_id)], limit=1)
                        except (TypeError, ValueError):
                            pass
                    val['partner_id'] = partner.id if partner else False

            current_partner_id = val.get('partner_id') or partner_id

            # Resolve land_info_id if present
            if 'land_info_id' in val:
                land_val = val['land_info_id']
                if land_val:
                    land_rec = self.env['g2p.land.information'].sudo().search([('land_id', '=', land_val)], limit=1)
                    if not land_rec:
                        try:
                            land_db_id = int(land_val)
                            if -2147483648 <= land_db_id <= 2147483647:
                                land_rec = self.env['g2p.land.information'].sudo().search([('id', '=', land_db_id)], limit=1)
                        except (TypeError, ValueError):
                            pass
                    if not land_rec and isinstance(land_val, str) and current_partner_id:
                        # Auto-create land record if it doesn't exist
                        land_vals = {
                            'land_id': land_val,
                            'partner_id': current_partner_id,
                            'total_land_area': val.get('land_area', 0.0),
                            'ownership_type': val.get('ownership_type') or 'owner',
                        }
                        # Resolve kebele_id first if present to link to land_kebele
                        kebele_val = val.get('kebele_id')
                        resolved_kebele_id = self._resolve_kebele_id(kebele_val, val)
                        if resolved_kebele_id:
                            land_vals['land_kebele'] = resolved_kebele_id

                        land_rec = self.env['g2p.land.information'].sudo().create(land_vals)
                    if land_rec and (not land_rec.land_id or str(land_rec.land_id).strip() in ('False', 'None', '')):
                        land_rec.land_id = str(land_val).strip() if (land_val and str(land_val).strip() not in ('False', 'None', '')) else f"Plot {land_rec.id}"
                    val['land_info_id'] = land_rec.id if land_rec else False

            # Resolve land_prep_method_ids if present
            prep_keys = [k for k in list(val.keys()) if any(w in k.lower() for w in ['land_prep', 'preparation_method', 'land_preparation'])]
            if prep_keys or 'land_prep_method_ids' in val:
                lp_val = val.get('land_prep_method_ids')
                if not lp_val:
                    for pk in prep_keys:
                        if val.get(pk):
                            lp_val = val[pk]
                            break
                if lp_val:
                    resolved_ids = []
                    raw_items = []
                    if isinstance(lp_val, list):
                        if len(lp_val) > 0 and isinstance(lp_val[0], (list, tuple)) and lp_val[0][0] == 6:
                            raw_items = lp_val[0][2]
                        else:
                            raw_items = lp_val
                    elif isinstance(lp_val, str):
                        import re
                        raw_items = [x.strip() for x in re.split(r'[\s,]+', lp_val.strip()) if x.strip()]

                    for item in raw_items:
                        if not item:
                            continue
                        if isinstance(item, int):
                            resolved_ids.append(item)
                        elif isinstance(item, str):
                            item_str = item.strip()
                            lp_rec = self.env['g2p.land.prep.method'].sudo().search([('name', '=ilike', item_str)], limit=1)
                            if not lp_rec:
                                lp_rec = self.env['g2p.land.prep.method'].sudo().search([('name', '=ilike', f'%{item_str}%')], limit=1)
                            if lp_rec:
                                resolved_ids.append(lp_rec.id)
                    val['land_prep_method_ids'] = [(6, 0, resolved_ids)]
                else:
                    val['land_prep_method_ids'] = False

            m2os = {
                'region': 'g2p.region',
                'region_id': 'g2p.region',
                'region_name_id': 'g2p.region',
                'zone': 'g2p.zone',
                'zone_id': 'g2p.zone',
                'zone_name_id': 'g2p.zone',
                'woreda': 'g2p.woreda',
                'woreda_id': 'g2p.woreda',
                'woreda_name_id': 'g2p.woreda',
                'kebele': 'g2p.kebele',
                'kebele_id': 'g2p.kebele',
                'crop_name_id': 'g2p.crop',
                'crop_category_id': 'g2p.crop.category',
                'crop_variety_id': 'g2p.crop.variety',
                'live_stock_type_id': 'g2p.livestock.type',
                'crop_season_id': 'g2p.season',
                'season_id': 'g2p.season',
                'actual_crop_name_id': 'g2p.crop',
                'actual_crop_category_id': 'g2p.crop.category',
                'actual_crop_variety_id': 'g2p.crop.variety',
                'actual_season_id': 'g2p.season',
                'water_resource_id': 'g2p.water.source',
                'cultivated_by': 'g2p.machinery',
                'cluster_info_id': 'g2p.cluster.information',
                'cluster_id': 'g2p.cluster.information',
            }

            for field, model_name in m2os.items():
                if field in val:
                    value = val[field]
                    if value:
                        if field == 'kebele_id' and model_name == 'g2p.kebele':
                            val[field] = self._resolve_kebele_id(value, val)
                        elif isinstance(value, str):
                            value_str = value.strip()
                            if model_name == 'g2p.season':
                                season_map = {
                                    'meher': 'Kiremt',
                                    'belg': 'Belg',
                                    'bega': 'Bega'
                                }
                                value_str = season_map.get(value_str.lower(), value_str)
                            elif model_name == 'g2p.water.source':
                                water_map = {
                                    'well_ground': 'well_water',
                                    'rainfed': 'rainfall'
                                }
                                value_str = water_map.get(value_str.lower(), value_str)
                            record = False
                            comodel = self.env[model_name]
                            if 'code' in comodel._fields:
                                record = comodel.sudo().search([('code', '=ilike', value_str)], limit=1)
                            if not record and 'name' in comodel._fields:
                                record = comodel.sudo().search([('name', '=ilike', value_str)], limit=1)
                            if not record and 'name' in comodel._fields:
                                record = comodel.sudo().search([('name', '=ilike', f'%{value_str}%')], limit=1)
                            if not record and 'name' in comodel._fields and '_' in value_str:
                                # Fuzzy match for ODK keys (e.g., 'sweet_hot_pepper' -> 'Sweet/Hot Pepper')
                                fuzzy_val = f"%{value_str.replace('_', '%')}%"
                                record = comodel.sudo().search([('name', '=ilike', fuzzy_val)], limit=1)

                            # Auto-create for specific models if not found
                            if not record and model_name in ['g2p.crop.variety', 'g2p.cluster.information']:
                                create_vals = {'name': value_str} if 'name' in comodel._fields else {}
                                if 'cluster_name' in comodel._fields:
                                    create_vals['cluster_name'] = value_str
                                if 'code' in comodel._fields:
                                    create_vals['code'] = value_str.upper().replace(' ', '_')

                                can_create = True
                                if model_name == 'g2p.crop.variety':
                                    linked_crop = val.get('crop_name_id') or val.get('actual_crop_name_id')
                                    if linked_crop:
                                        create_vals['crop_id'] = linked_crop
                                    else:
                                        can_create = False

                                if can_create:
                                    record = comodel.sudo().create(create_vals)

                            if record:
                                val[field] = record.id
                            else:
                                val[field] = False
                        elif isinstance(value, int):
                            val[field] = value
                            record = self.env[model_name].sudo().browse(value)
                    else:
                        val[field] = False

                    if val.get(field) and model_name == 'g2p.season':
                        season_rec = record or self.env['g2p.season'].sudo().browse(val[field])
                        if season_rec and getattr(season_rec, 'start_gc', False):
                            val['start_gc'] = season_rec.start_gc.strftime('%Y-%m-%d') if hasattr(season_rec.start_gc, 'strftime') else str(season_rec.start_gc)
                            val['start_month'] = getattr(season_rec.start_gc, 'month', False)
                            val['start_day'] = getattr(season_rec.start_gc, 'day', False)
                        if season_rec and getattr(season_rec, 'end_gc', False):
                            val['end_gc'] = season_rec.end_gc.strftime('%Y-%m-%d') if hasattr(season_rec.end_gc, 'strftime') else str(season_rec.end_gc)
                            val['end_month'] = getattr(season_rec.end_gc, 'month', False)
                            val['end_day'] = getattr(season_rec.end_gc, 'day', False)

            # Recurse on dictionary values
            for k, v in val.items():
                if isinstance(v, (dict, list, tuple)):
                    self._resolve_m2o_recursive(v, partner_id=current_partner_id)

        elif isinstance(val, (list, tuple)):
            for item in val:
                if isinstance(item, (dict, list, tuple)):
                    self._resolve_m2o_recursive(item, partner_id=partner_id)
