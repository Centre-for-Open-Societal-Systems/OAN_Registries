import json

from odoo import fields, models

from ..json_encoder import CustomJSONEncoder


class ResPartner(models.Model):
    _inherit = "res.partner"
    # _inherit = ['mail.thread', 'mail.activity.mixin']

    approval_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        track_visibility="onchange",
    )

    edit_state = fields.Selection(selection=[("open", "Open"), ("locked", "Locked")], default="open")

    edit_count = fields.Integer(default=0)

    update_request_ids = fields.One2many("res.partner.change.request", "partner_id", string="Update Requests")
    edit_suggestion_ids = fields.One2many("request", "record_id", string="Edit Suggestions")

    def _sanitize_vals(self, vals):
        sanitized = {}
        for key, value in vals.items():
            # Check if value is an Odoo recordset
            if isinstance(value, models.BaseModel):
                sanitized[key] = value.id  # Store the ID instead of the recordset
            else:
                sanitized[key] = value
        return sanitized

    def write(self, vals):
        state = {"state": "update_requested"}
        sanitized_vals = self._sanitize_vals(vals)
        no_of_edits = self.env["no.of.edits"].search([])
        user = self.env.user
        for record in self:
            if self.env.user.has_group("base.group_portal"):
                if record.edit_count >= no_of_edits.edit_amount + 1:
                    vals["edit_state"] = "locked"
                vals["edit_count"] = record.edit_count + 1

            if self.env.user.has_group("base.group_portal") and record.edit_state == "locked":
                if "given_name" in vals:
                    for partner in self:
                        self.env["res.partner.change.request"].create(
                            {
                                "partner_id": partner.id,
                                "requested_by": user.id,
                                "new_values": CustomJSONEncoder.python_dict_to_json_dict(sanitized_vals),
                                # "update_message": update_message,
                                "state": "pending",
                            }
                        )
                        vals["state"] = "update_requested"
                        # Return a meaningful value; for example, the count of records 'affected'
                    return super().write(state)
                else:
                    return super().write(vals)

            elif (
                self.env.context.get("bypass_write")
                or record.edit_state != "locked"
                or self.env.is_superuser()
                or user.has_group("g2p_ati.group_data_validator")
                or user.has_group("g2p_registry_base.group_g2p_admin")
            ):
                # vals["state"] = "approved"
                # Allow write operations if the bypass context is set
                return super().write(vals)
            else:
                # Create a change request for each record that is being updated
                for partner in self:
                    self.env["res.partner.change.request"].create(
                        {
                            "partner_id": partner.id,
                            "new_values": CustomJSONEncoder.python_dict_to_json_dict(vals),
                            # "update_message": update_message,
                            "state": "pending",
                        }
                    )
                    # Return a meaningful value; for example, the count of records 'affected'
                return super().write(state)


class ResPartnerChangeRequest(models.Model):
    _name = "res.partner.change.request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "partner_id"

    _description = "Update Request"

    name = fields.Char(string="Request")
    partner_id = fields.Many2one("res.partner", string="Record", required=True)
    # new_values = fields.Text(string="New Values", required=True)
    requested_by = fields.Many2one("res.users", default=lambda self: self.env.user)
    validator = fields.Many2one("res.users")
    new_values = fields.Json(string="Changes", required=True)
    update_message = fields.Char(string="Message")
    new_values_display = fields.Char(string="New Values (Preview)", compute="_compute_new_values_display")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="pending",
        string="Status",
    )

    def create(self, vals):
        # Create the change request record
        change_request = super().create(vals)

        # Find the group by external ID (replace with your actual group ID)
        group = self.env.ref("g2p_ati.group_data_validator")  # Replace with the actual module and group name
        if group:
            users = group.users
            for user in users:
                # Send notification to each user in the group
                self.env["mail.activity"].create(
                    {
                        "activity_type_id": self.env.ref(
                            "mail.mail_activity_data_todo"
                        ).id,  # Todo activity type
                        "res_model_id": self.env["ir.model"]
                        .search([("model", "=", "res.partner.change.request")])
                        .id,
                        "res_id": change_request.id,  # The record ID of the res.partner.change.request
                        "user_id": user.id,
                        "date_deadline": fields.Date.context_today(self),  # Deadline in 3 days
                        "summary": "New Update Request",
                        "note": "A new request has been created. Please review and approve it.",
                    }
                )

        return change_request

    def _compute_new_values_display(self):
        for record in self:
            try:
                # Convert JSON to a pretty-printed string for display
                record.new_values_display = json.dumps(record.new_values, indent=2)
            except Exception:
                record.new_values_display = "Error displaying JSON"

    def approve_changes(self):
        for request in self:
            try:
                # Safely parse the new_values string to a dictionary
                new_vals = request.new_values
                new_vals["state"] = "approved"
                if isinstance(new_vals, dict):
                    # Apply the new values directly using the super method
                    request.partner_id.reg_ids.unlink()
                    request.partner_id.phone_number_ids.unlink()
                    request.partner_id.land_information_ids.unlink()
                    request.partner_id.crop_information_ids.unlink()
                    request.partner_id.livestock_information_ids.unlink()
                    request.partner_id.supporting_documents_ids.unlink()
                    request.partner_id.with_context(bypass_write=True).sudo().write(new_vals)
                    # Mark the request as approved
                    request.state = "approved"
                    # Add the user who validated (approved) the request
                    request.validator = self.env.user
                    # Log the applied changes for debugging
                    # request.partner_id.message_post(body=f"Changes approved and applied: {new_vals}")

                else:
                    raise ValueError("Parsed new_values is not a dictionary")
            except Exception as e:
                # Handle any exceptions and log them for debugging
                request.state = "rejected"
                request.validator = self.env.user  # The user who validated (rejected)
                request.partner_id.message_post(body=f"Failed to apply changes: {str(e)}")
                # Optionally, raise the exception if you want to handle it at a higher level
                raise
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "res.partner.change.request"),
                ("res_id", "in", self.ids),
                ("user_id", "=", self.env.user.id),
            ]
        )

        # Mark the activities as done or unlink them (remove them)
        activities.action_done()

        edit_suggestions = self.env["request"].search([("record_id", "=", self.partner_id.id)])
        for suggests in edit_suggestions:
            suggests.status = "updated"

    def reject_changes(self):
        for request in self:
            try:
                # Safely parse the new_values string to a dictionary
                new_vals = request.new_values
                if isinstance(new_vals, dict):
                    # Mark the request as approved
                    request.state = "rejected"
                    request.validator = self.env.user  # The user who validated (rejected)
                    # Log the applied changes for debugging
                    request.partner_id.message_post(body=f"Changes Rejected Please Try again: {new_vals}")
                else:
                    raise ValueError("Parsed new_values is not a dictionary")
            except Exception as e:
                # Handle any exceptions and log them for debugging
                request.state = "rejected"
                request.validator = self.env.user  # The user who validated (rejected)
                request.partner_id.message_post(body=f"Failed to apply changes: {str(e)}")

        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "res.partner.change.request"),
                ("res_id", "in", self.ids),
                ("user_id", "=", self.env.user.id),
            ]
        )
        # Mark the activities as done or unlink them (remove them)
        activities.action_done()
