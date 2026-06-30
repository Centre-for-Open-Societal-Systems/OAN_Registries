from odoo import api, fields, models


class Request(models.TransientModel):
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _name = "request"
    _description = "Request"

    reason = fields.Text(string="Reason Description", required=True)
    record_id = fields.Many2one("res.partner", required=True)
    requester_id = fields.Many2one("res.users", string="Requester", required=True)
    enumerator_id = fields.Many2one("res.users", string="Enumerator", required=True)
    status = fields.Selection(
        [("newSuggestion", "New Suggestion"), ("updated", "Updated")], default="newSuggestion"
    )
    type = fields.Selection(
        [("suggestion", "Suggestion"), ("edit", "Edit Access Request")], string="Edit Type"
    )
    seen = fields.Boolean(default=False)

    def accept_request(self):
        self.record_id.edit_state = "open"
        # self.record_id.write({'edit_state': 'open'})
        self.status = "accepted"

    def reject_request(self):
        self.record_id.edit_state = "locked"
        self.status = "rejected"

    @api.model
    def create(self, vals):
        # Automatically reset seen status on new requests
        vals["status"] = "newSuggestion"
        vals["seen"] = False
        return super().create(vals)

    def update_request(self, vals):
        if self.status == "newSuggestion":
            self.status = "updated"
        return self.write(vals)
