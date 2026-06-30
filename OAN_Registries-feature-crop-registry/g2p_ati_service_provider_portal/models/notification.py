from odoo import fields, models


class Notification(models.Model):
    _name = "g2p.ati.notification"
    _description = "G2p ATI Notification"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    notified_user = fields.Many2one("res.users", requried=True)
    message = fields.Text(requried=True)
    title = fields.Text(requried=True)
    has_seen = fields.Boolean(default=False)
