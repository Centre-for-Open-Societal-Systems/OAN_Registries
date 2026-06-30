from odoo import _, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    notification = fields.One2many("g2p.ati.notification", "notified_user")
    unseen_notification_count = fields.Integer(
        compute="_compute_unseen_notification_count",
    )

    def _compute_unseen_notification_count(self):
        for rec in self:
            count = 0
            for notification in rec.notification:
                if not notification.has_seen:
                    count = count + 1
            self.unseen_notification_count = count
        return

    def show_notifcation(self):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Warning head"),
                "type": "warning",
                "message": _("This is the detailed warning"),
                "sticky": True,
            },
        }
