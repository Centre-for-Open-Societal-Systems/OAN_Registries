# __manifest__.py
{
    'name': 'OpenAgriNet - Livestock Registry',
    'version': '17.0.1.1.0',
    'summary': 'National livestock identity, traceability, and health information registry',
    'description': """
Livestock Registry Module for OpenAgriNet (OAN)
=================================================
Implements the Livestock Registry SRS: profile lifecycle, ear tag identification,
health & vaccination tracking, vital events (birth/mortality/disease), breeding &
AI tracking, herd/flock dashboard & analytics, role-based access control,
and immutable audit logging.
    """,
    'category': 'Agriculture',
    'author': 'OpenAgriNet',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'g2p_ati', 'g2p_odk_importer', 'g2p_odk_importer_ati'],
    'external_dependencies': {
        'python': ['xlsxwriter', 'reportlab', 'openpyxl', 'jq'],
    },
    'data': [
        'security/livestock_security.xml',
        'security/ir.model.access.csv',
        'security/livestock_record_rules.xml',

        'data/sequences.xml',
        'data/mail_templates.xml',
        'data/cron.xml',
        'data/odk_import_data.xml',

        'views/g2p_livestock_registry_views.xml',
        'views/event_views.xml',
        'views/technician_partner_view.xml',
        'views/dashboard_views.xml',
        'views/audit_log_views.xml',
        'views/bulk_health_update_wizard_views.xml',
        'views/bulk_vaccination_update_wizard_views.xml',
        'views/livestock_menu.xml',
        'views/vaccine_schedule_views.xml',
        'views/registry_line_views.xml',
        'views/import_batch_views.xml',
        'views/livestock_dashboard.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'g2p_livestock_registry/static/src/css/livestock_dashboard.css',
            'g2p_livestock_registry/static/src/js/livestock_dashboard.xml',  # OWL template FIRST
            'g2p_livestock_registry/static/src/js/livestock_dashboard.js',  # JS second
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
