import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if version == "17.0.1.3.0":
        #    delete the ati res config odk view
        cr.execute(
            """
        DELETE FROM ir_ui_view
        WHERE id IN (
            SELECT id FROM ir_ui_view
            WHERE name = 'res.config.settings.view.form.ati.inherit'
            ORDER BY id LIMIT 1)"""
        )
