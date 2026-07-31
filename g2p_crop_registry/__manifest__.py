{
    "name": "Crop Registry",
    "category": "G2P",
    "version": "17.0.1.0.0",
    "author": "OpenG2P",
    "website": "https://openg2p.org",
    "license": "LGPL-3",
    "depends": [
        'web','base','mail','g2p_odk_importer_ati', 'g2p_ati_integrations'
    ],
    "data": [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'wizard/crop_reject_wizard.xml',
        'wizard/crop_request_wiz.xml',
        'data/infestation_type_data.xml',
        'data/land_prep_method_data.xml',
        'data/machinery_data.xml',
        'data/ir_sequence_data.xml',
        'data/cluster_status_data.xml',
        'views/crop_request_views.xml',
        'views/crop_production_menu.xml',
        'views/crop_registry.xml',
        'views/crop_production.xml',
        'views/dashboard_action.xml',
    ],
    "demo": [],
    "images": [],
    "installable": True,
    "assets": {
        "web.assets_backend": [
            "g2p_crop_registry/static/src/css/crop_maturity.css",
            "g2p_crop_registry/static/src/components/dashboard/crop_dashboard.js",
            "g2p_crop_registry/static/src/components/dashboard/crop_dashboard.xml",
            "g2p_crop_registry/static/src/components/dashboard/crop_dashboard.scss",
        ],
    },
}
