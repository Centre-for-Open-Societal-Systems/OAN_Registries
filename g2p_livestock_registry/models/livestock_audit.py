# models/livestock_audit.py
from odoo import models, fields, _
from odoo.exceptions import AccessError


class G2PLivestockAuditLog(models.Model):
    _name = 'g2p.livestock.audit.log'
    _description = 'Immutable Audit Log'
    _log_access = False
    _order = 'timestamp desc'

    res_model = fields.Char(string='Related Model', required=True, index=True)
    res_id = fields.Integer(string='Related Record ID', index=True)
    user_id = fields.Many2one('res.users', string='User', required=True, index=True)
    user_role = fields.Char(string='User Role')
    action_type = fields.Selection([
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('import', 'Import'),
        ('sync', 'Offline Sync'),
    ], string='Action Type', required=True)
    changes = fields.Text(string='Changes (JSON)')
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, required=True, index=True)
    ip_address = fields.Char(string='IP Address')
    session_id = fields.Char(string='Session ID')

    def write(self, vals):
        # LR-27: logs are immutable once created. Block all writes, even from sudo
        # callers outside of internal _create_audit_log (which only ever calls create()).
        raise AccessError(_("Audit logs are immutable and cannot be modified."))

    def unlink(self):
        raise AccessError(_("Audit logs are immutable and cannot be deleted."))
