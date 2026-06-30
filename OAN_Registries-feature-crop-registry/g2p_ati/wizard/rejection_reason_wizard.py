from odoo import fields, models


class G2PRejectionReasonWizard(models.TransientModel):
    _name = "g2p.rejection.reason.wizard"
    _description = "Rejection Reason Wizard"

    reason = fields.Text(required=True)

    def confirm_rejection(self):
        active_ids = self.env.context.get("active_ids", [])
        partners_to_update = self.env["res.partner"].browse(active_ids)

        # Iterate over each partner and update the rejection_reason field
        for partner in partners_to_update:
            partner.write({"state": "rejected", "rejection_reason": self.reason})

        return {"type": "ir.actions.act_window_close"}
