{
    "name": "Crop Registry",
    "category": "G2P",
    "version": "17.0.1.0.0",
    "author": "OpenG2P",
    "website": "https://openg2p.org",
    "license": "LGPL-3",
    "depends": [
        'web','base','mail','g2p_ati','g2p_odk_importer',
    ],
    "data": [
        'security/ir.model.access.csv',
        'data/pest_data.xml',
        'data/pesticide_data.xml',
        'data/weed_data.xml',
        'data/weedicide_data.xml',
        'data/land_prep_method_data.xml',
        'data/ir_sequence_data.xml',
        'views/crop_registry.xml',
        'views/crop_production.xml',
    ],
    "demo": [],
    "images": [],
    "installable": True,
    "assets": {
        "web.assets_backend": [
            "g2p_crop_registry/static/src/css/crop_maturity.css",
        ],
    },
}
