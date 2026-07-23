from odoo import fields, models, api

class G2PCropRequestWiz(models.TransientModel):
    _name = 'g2p.crop.request.wiz'
    _description = 'Suggest Edit Wizard'

    reason = fields.Text(string='Reason Description', required=True)
    crop_registry_ids = fields.Many2many('g2p.crop.registry', string='Records to be Edited')

    @api.model
    def default_get(self, fields):
        res = super(G2PCropRequestWiz, self).default_get(fields)
        if 'crop_registry_ids' in fields and self.env.context.get('active_ids'):
            res['crop_registry_ids'] = [(6, 0, self.env.context.get('active_ids'))]
        return res

    def confirm(self):
        for record in self.crop_registry_ids:
            self.env['g2p.crop.edit.request'].create({
                'reason': self.reason,
                'crop_registry_id': record.id,
            })
            record.with_context(bypass_write=True).write({'state': 'update_requested'})
