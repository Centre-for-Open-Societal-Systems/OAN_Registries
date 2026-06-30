# Part of OpenG2P. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenG2P ATI: WebSub Integration",
    "category": "G2P",
    "version": "17.0.1.5.0",
    "sequence": 1,
    "author": "OpenG2P",
    "website": "https://openg2p.org",
    "license": "LGPL-3",
    "depends": [
        "g2p_registry_datashare_websub",
        "g2p_ati",
    ],
    "external_dependencies": {},
    "data": [
        "data/queue_job_cron.xml",
        "security/ir.model.access.csv",
        "views/datashare_config_websub_ati.xml",
        "views/data_field_views.xml",
        "views/res_partner_websub_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "/g2p_ati_websub/static/src/js/data_field_widgets.js",
            "/g2p_ati_websub/static/src/xml/data_field_widgets.xml",
            "/g2p_ati_websub/static/src/scss/data_field_widgets.scss",
        ],
    },
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
