# Part of OpenG2P. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenG2P ODK Config: ATI",
    "category": "G2P",
    "version": "17.0.1.5.0",
    "sequence": 1,
    "author": "OpenG2P",
    "website": "https://openg2p.org",
    "license": "LGPL-3",
    "depends": ["g2p_ati", "g2p_odk_importer", "g2p_registry_addl_info"],
    "external_dependencies": {},
    "data": [
        "security/ir.model.access.csv",
        "views/views.xml",
        # "views/odk_res_config_setting.xml"
        "data/odk_config.xml",
        "data/odk_import.xml",
    ],
    "assets": {"web.assets_backend": []},
    "demo": [],
    "images": [],
    "application": True,
    "installable": True,
    "auto_install": False,
}
