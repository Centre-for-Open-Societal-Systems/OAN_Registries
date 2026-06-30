import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class RequestWizard(models.TransientModel):
    _name = "request.wiz"
    _inherit = ["mail.thread.main.attachment", "mail.activity.mixin"]
    _description = "Request Wizard"

    reason = fields.Text(string="Reason Description", required=True)
    record_ids = fields.Many2many("res.partner", string="Records to be Edited")

    def send_request(self):
        # Get the activity type (e.g., To Do)
        for record in self.record_ids:
            enumerators = record.create_uid

            self.activity_schedule(
                "g2p_lock_unlock.mail_activity_edit_suggest",
                user_id=enumerators.id,
                note="Please Validate This Request",
            )

            # Save the data to the regular model
            self.env["request"].create(
                {
                    "reason": self.reason,
                    "record_id": record.id,
                    "enumerator_id": enumerators.id,
                    "requester_id": self.env.user.id,
                    "status": "pending",
                    "type": "edit",
                }
            )

        return True
