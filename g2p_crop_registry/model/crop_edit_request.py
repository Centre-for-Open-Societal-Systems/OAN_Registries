from odoo import api, fields, models

class G2PCropEditRequest(models.Model):
    _name = 'g2p.crop.edit.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Crop Edit Request'

    reason = fields.Text(string='Reason Description', required=True)
    crop_registry_id = fields.Many2one('g2p.crop.registry', required=True, ondelete='cascade')
    requester_id = fields.Many2one('res.users', string='Requester', required=True, default=lambda self: self.env.user)
    status = fields.Selection(
        [('newSuggestion', 'New Suggestion'), ('updated', 'Updated'), ('accepted', 'Accepted'), ('rejected', 'Rejected')],
        default='newSuggestion'
    )
    type = fields.Selection(
        [('suggestion', 'Suggestion'), ('edit', 'Edit Access Request')], string='Edit Type', default='edit'
    )
    seen = fields.Boolean(default=False)
    can_approve = fields.Boolean(compute='_compute_can_approve', string="Can Approve")

    @api.depends('status')
    @api.depends_context('uid')
    def _compute_can_approve(self):
        user = self.env.user
        is_sms = user.has_group('g2p_crop_registry.group_woreda_sms')
        is_wah = user.has_group('g2p_crop_registry.group_woreda_agri_office_head')
        is_admin = self.env.is_superuser()

        for req in self:
            if is_admin:
                req.can_approve = True
                continue
            
            requester_is_da = req.requester_id.has_group('g2p_crop_registry.group_development_agent')
            requester_is_sms = req.requester_id.has_group('g2p_crop_registry.group_woreda_sms')
            
            if is_wah and (requester_is_sms or requester_is_da):
                req.can_approve = True
            elif is_sms and not is_wah and requester_is_da:
                req.can_approve = True
            else:
                req.can_approve = False

    def accept_request(self):
        user = self.env.user
        is_sms = user.has_group('g2p_crop_registry.group_woreda_sms')
        is_wah = user.has_group('g2p_crop_registry.group_woreda_agri_office_head')
        
        for req in self:
            requester_is_da = req.requester_id.has_group('g2p_crop_registry.group_development_agent')
            
            if is_sms and not is_wah and requester_is_da:
                # Forward to WAH
                original_da_name = req.requester_id.name
                req.requester_id = user.id
                forward_msg = f"[Forwarded by SMS: {user.name} (Original DA: {original_da_name})] "
                req.reason = forward_msg + (req.reason or "")
                # We do NOT apply changes yet. Keep in newSuggestion state.
                continue

            req.crop_registry_id.with_context(bypass_write=True).write({'edit_state': 'open', 'state': 'approved'})
            req.status = 'accepted'

    def reject_request(self):
        self.crop_registry_id.with_context(bypass_write=True).write({'edit_state': 'locked', 'state': 'approved'})
        self.status = 'rejected'

    @api.model
    def create(self, vals):
        vals['status'] = 'newSuggestion'
        vals['seen'] = False
        return super().create(vals)
