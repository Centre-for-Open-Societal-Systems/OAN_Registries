from odoo import api, fields, models
import json
import logging

_logger = logging.getLogger(__name__)

class G2PCropChangeRequest(models.Model):
    _name = 'g2p.crop.change.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'crop_registry_id'
    _description = 'Crop Update Request'

    name = fields.Char(string='Request')
    crop_registry_id = fields.Many2one('g2p.crop.registry', string='Record', required=True, ondelete='cascade')
    requested_by = fields.Many2one('res.users', default=lambda self: self.env.user)
    validator = fields.Many2one('res.users')
    new_values = fields.Json(string='Changes', required=True)
    update_message = fields.Char(string='Message')
    new_values_display = fields.Char(string='New Values (Preview)', compute='_compute_new_values_display')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending', string='Status')

    can_approve = fields.Boolean(compute='_compute_can_approve', string="Can Approve")

    @api.depends('state')
    @api.depends_context('uid')
    def _compute_can_approve(self):
        da_group = self.env.ref('g2p_crop_registry.group_development_agent', raise_if_not_found=False)
        sms_group = self.env.ref('g2p_crop_registry.group_woreda_sms', raise_if_not_found=False)
        wah_group = self.env.ref('g2p_crop_registry.group_woreda_agri_office_head', raise_if_not_found=False)

        is_admin = self.env.is_superuser()

        for request in self:
            if is_admin:
                request.can_approve = True
                continue

            user_groups = self.env.user.sudo().groups_id
            is_sms = (sms_group and sms_group in user_groups) or self.env.user.has_group('g2p_crop_registry.group_woreda_sms')
            is_wah = (wah_group and wah_group in user_groups) or self.env.user.has_group('g2p_crop_registry.group_woreda_agri_office_head')

            requester_groups = request.requested_by.sudo().groups_id
            requester_is_da = (da_group and da_group in requester_groups) or request.requested_by.has_group('g2p_crop_registry.group_development_agent')
            requester_is_sms = (sms_group and sms_group in requester_groups) or request.requested_by.has_group('g2p_crop_registry.group_woreda_sms')

            if is_wah and (requester_is_sms or requester_is_da):
                request.can_approve = True
            elif is_sms and not is_wah and requester_is_da:
                request.can_approve = True
            else:
                request.can_approve = False

    def _compute_new_values_display(self):
        for record in self:
            try:
                record.new_values_display = json.dumps(record.new_values, indent=2)
            except Exception:
                record.new_values_display = 'Error displaying JSON'

    def approve_changes(self):
        user = self.env.user
        is_sms = user.has_group('g2p_crop_registry.group_woreda_sms')
        is_wah = user.has_group('g2p_crop_registry.group_woreda_agri_office_head')

        for request in self:
            requester_is_da = request.requested_by.has_group('g2p_crop_registry.group_development_agent')

            if is_sms and not is_wah and requester_is_da:
                # Forward to WAH
                original_da_name = request.requested_by.name
                request.requested_by = user.id
                forward_msg = f"[Forwarded by SMS: {user.name} (Original DA: {original_da_name})] "
                request.update_message = forward_msg + (request.update_message or "")
                # We do NOT apply changes yet. Keep in pending state.
                continue

            try:
                new_vals = request.new_values
                if isinstance(new_vals, dict):
                    # Set the crop registry state back to approved
                    new_vals['state'] = 'approved'
                    if request.crop_registry_id.planning_state == 'update_requested':
                        new_vals['planning_state'] = 'approved'
                    if request.crop_registry_id.cultivation_state == 'update_requested':
                        new_vals['cultivation_state'] = 'approved'
                    if request.crop_registry_id.sowing_state == 'update_requested':
                        new_vals['sowing_state'] = 'approved'
                    if request.crop_registry_id.harvesting_state == 'update_requested':
                        new_vals['harvesting_state'] = 'approved'

                    # Write new values
                    request.crop_registry_id.with_context(bypass_write=True).sudo().write(new_vals)
                    request.state = 'approved'
                    request.validator = self.env.user
                else:
                    raise ValueError("Parsed new_values is not a dictionary")
            except Exception as e:
                request.state = 'rejected'
                request.validator = self.env.user
                raise

            edit_suggestions = self.env['g2p.crop.edit.request'].search([('crop_registry_id', '=', request.crop_registry_id.id)])
            for suggests in edit_suggestions:
                suggests.status = 'updated'

    def reject_changes(self):
        for request in self:
            request.state = 'rejected'
            request.validator = self.env.user
            reset_vals = {'state': 'approved'}
            if request.crop_registry_id.planning_state == 'update_requested':
                reset_vals['planning_state'] = 'approved'
            if request.crop_registry_id.cultivation_state == 'update_requested':
                reset_vals['cultivation_state'] = 'approved'
            if request.crop_registry_id.sowing_state == 'update_requested':
                reset_vals['sowing_state'] = 'approved'
            if request.crop_registry_id.harvesting_state == 'update_requested':
                reset_vals['harvesting_state'] = 'approved'
            request.crop_registry_id.with_context(bypass_write=True).sudo().write(reset_vals)
