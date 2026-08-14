from odoo import fields, models, _
from odoo.exceptions import UserError


class G2PLivestockBulkHealthUpdateWizard(models.TransientModel):
    """LR-21: Bulk Operations on Livestock Records — Update Health Status.

    Opened from the Livestock Inventory list view after selecting one or
    more rows. Lets the user set a single Health Status on all of them.
    """
    _name = 'g2p.livestock.bulk.health.wizard'
    _description = 'Bulk Update Health Status'

    livestock_ids = fields.Many2many(
        'g2p.livestock.registry.line', 'g2p_lv_bulk_health_wizard_rel',
        'wizard_id', 'line_id', string='Selected Animals')
    health_status = fields.Selection([
        ('healthy', 'Healthy'),
        ('sick', 'Sick'),
        ('quarantined', 'Quarantined'),
    ], string='New Health Status', required=True)
    notes = fields.Char(string='Reason / Notes')

    def action_apply(self):
        self.ensure_one()
        if not self.livestock_ids:
            raise UserError(_("No animals selected."))

        self.livestock_ids.write({'health_status': self.health_status})

        # Log a short note on each record's chatter for traceability (LR-05: reason/notes)
        if self.notes:
            for rec in self.livestock_ids:
                if rec.registry_id:
                    rec.registry_id.message_post(
                        body=_("Health status bulk-updated to '%s' for animal %s. Reason: %s")
                             % (self.health_status, rec.ear_tag_id or rec.name, self.notes))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Update Complete'),
                'message': _('%s animal(s) updated to "%s".') % (len(self.livestock_ids), self.health_status),
                'type': 'success',
                'sticky': False,
            }
        }
