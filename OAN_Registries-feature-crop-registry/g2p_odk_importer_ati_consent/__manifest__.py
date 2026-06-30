# Part of OpenG2P. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenG2P ODK Config: ATI Consent",
    "summary": "Import ATI consent requests from ODK Central.",
    "category": "G2P",
    "version": "17.0.1.0.0",
    "author": "OpenG2P",
    "website": "https://openg2p.org",
    "license": "LGPL-3",
    "depends": [
        "g2p_odk_importer",
        "g2p_ati_consent_mgt",
    ],
    "data": [
        "data/odk_config.xml",
        "data/odk_import.xml",
        "views/odk_import_views.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
