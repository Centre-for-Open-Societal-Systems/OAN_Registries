#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ODOO_ROOT = Path(__file__).resolve().parents[3]
if str(ODOO_ROOT) not in sys.path:
    sys.path.insert(0, str(ODOO_ROOT))

import odoo
from odoo import SUPERUSER_ID, api
from odoo.modules.registry import Registry
from odoo.service.server import load_server_wide_modules
from odoo.tools import config as odoo_config


DATA_FIELD_CODE = "ati_farmer_profile_payload"

MAPPING_LINES = [
    {"payload_key": "FarmerFayidaId", "source_path": "reg_ids.value", "filter_path": "id_type.name", "filter_value": "UID"},
    {
        "payload_key": "FarmerResidentialId",
        "source_path": "reg_ids.value",
        "filter_path": "id_type.name",
        "filter_value": "RID",
    },
    {"payload_key": "FirstName", "source_path": "given_name"},
    {"payload_key": "MiddleName", "source_path": "family_name"},
    {"payload_key": "LastName", "source_path": "gf_name_eng"},
    {"payload_key": "Birthdate", "source_path": "birthdate"},
    {"payload_key": "Sex", "source_path": "gender"},
    {"payload_key": "MartialStatus", "source_path": "martial_status"},
    {"payload_key": "FamilySize", "source_path": "size_of_family"},
    {"payload_key": "TotalLandOwnedArea", "source_path": "total_land_owned_area"},
    {"payload_key": "TotalLandRentedArea", "source_path": "total_land_rent_area"},
    {"payload_key": "TotalCropSharingLandArea", "source_path": "total_land_crop_sharing_area"},
    {"payload_key": "FarmingType", "source_path": "farming_type"},
    {"payload_key": "ContactPhone1", "source_path": "phone_number_ids.phone_no", "filter_path": "phone_type", "filter_value": "primary"},
    {
        "payload_key": "ContactPhone2",
        "source_path": "phone_number_ids.phone_no",
        "filter_path": "phone_type",
        "filter_value": "secondary",
        "fallback_filter_path": "phone_type",
        "fallback_filter_value": "other",
    },
    {"payload_key": "KebeleCode", "source_path": "kebele.code"},
    {"payload_key": "Status", "source_path": "state"},
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create or update the ATI farmer profile data field in Odoo."
    )
    parser.add_argument(
        "-c",
        "--config",
        default="/opt/odoo17/odoo17.conf",
        help="Path to the Odoo config file.",
    )
    parser.add_argument(
        "-d",
        "--database",
        required=True,
        help="Target database name.",
    )
    parser.add_argument(
        "--addons-path",
        default=None,
        help="Optional addons path override. Usually not needed when the config file is correct.",
    )
    return parser.parse_args()


def bootstrap_odoo(args):
    config_args = ["-c", args.config, "-d", args.database]
    if args.addons_path:
        config_args.extend(["--addons-path", args.addons_path])

    odoo_config.parse_config(config_args)
    load_server_wide_modules()
    return Registry(args.database)


def upsert_data_field(env):
    data_field_model = env["g2p.consent.data.field"].sudo()
    mapping_model = env["g2p.consent.data.field.map.line"].sudo()

    data_field = data_field_model.search([("code", "=", DATA_FIELD_CODE)], limit=1)
    values = {
        "name": "ATI Farmer Profile Payload",
        "code": DATA_FIELD_CODE,
        "payload_key": "FarmerProfile",
        "description": (
            "Farmer profile payload used by ATI WebSub sharing. "
            "This record uses advanced mapping lines to build a structured payload."
        ),
        "source_path": False,
    }

    if data_field:
        data_field.write(values)
    else:
        data_field = data_field_model.create(values)

    existing_lines = {line.payload_key: line for line in data_field.mapping_line_ids}
    seen_payload_keys = set()

    for line_vals in MAPPING_LINES:
        payload_key = line_vals["payload_key"]
        seen_payload_keys.add(payload_key)
        vals = {
            "data_field_id": data_field.id,
            "payload_key": payload_key,
            "source_path": line_vals["source_path"],
            "filter_path": line_vals.get("filter_path", False),
            "filter_operator": line_vals.get("filter_operator", "="),
            "filter_value": line_vals.get("filter_value", False),
            "fallback_filter_path": line_vals.get("fallback_filter_path", False),
            "fallback_filter_operator": line_vals.get("fallback_filter_operator", "="),
            "fallback_filter_value": line_vals.get("fallback_filter_value", False),
        }
        if payload_key in existing_lines:
            existing_lines[payload_key].write(vals)
        else:
            mapping_model.create(vals)

    stale_lines = data_field.mapping_line_ids.filtered(lambda line: line.payload_key not in seen_payload_keys)
    if stale_lines:
        stale_lines.unlink()

    return data_field


def main():
    args = parse_args()
    registry = bootstrap_odoo(args)
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        data_field = upsert_data_field(env)
        cr.commit()
        print(
            f"Created/updated data field '{data_field.display_name}' "
            f"(code={data_field.code}, id={data_field.id}) with {len(data_field.mapping_line_ids)} mapping lines."
        )


if __name__ == "__main__":
    main()
