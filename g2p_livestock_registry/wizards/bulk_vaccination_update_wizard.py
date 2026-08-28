from odoo import fields, models, _
from odoo.exceptions import UserError


class G2PLivestockBulkVaccinationUpdateWizard(models.TransientModel):
    """LR-21: Bulk Operations on Livestock Records — Update Vaccination Status.

    Opened from the Livestock Inventory list view after selecting one or
    more rows. Lets the user set a single Vaccination Status on all of them.
    """
    _name = 'g2p.livestock.bulk.vaccination.wizard'
    _description = 'Bulk Update Vaccination Status'

    livestock_ids = fields.Many2many(
        'g2p.livestock.registry.line', 'g2p_lv_bulk_vaccination_wizard_rel',
        'wizard_id', 'line_id', string='Selected Animals')
    vaccination_status = fields.Selection([
        ('up_to_date', 'Up-to-date'),
        ('overdue', 'Overdue'),
        ('none', 'None'),
    ], string='New Vaccination Status', required=True)
    notes = fields.Char(string='Reason / Notes')

    def action_apply(self):
        self.ensure_one()
        if not self.livestock_ids:
            raise UserError(_("No animals selected."))

        self.livestock_ids.write({'vaccination_status': self.vaccination_status})

        if self.notes:
            for rec in self.livestock_ids:
                if rec.registry_id:
                    rec.registry_id.message_post(
                        body=_("Vaccination status bulk-updated to '%s' for animal %s. Reason: %s")
                             % (self.vaccination_status, rec.ear_tag_id or rec.name, self.notes))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Update Complete'),
                'message': _('%s animal(s) updated to "%s".') % (len(self.livestock_ids), self.vaccination_status),
                'type': 'success',
                'sticky': False,
            }
        }
