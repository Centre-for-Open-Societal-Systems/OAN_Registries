from odoo import fields, models


class G2PCropRejectWizard(models.TransientModel):
    _name = "g2p.crop.reject.wizard"
    _description = "Crop Registry Rejection Reason Wizard"

    reason = fields.Text(required=True)

    def confirm_rejection(self):
        active_ids = self.env.context.get("active_ids", [])
        records = self.env["g2p.crop.registry"].browse(active_ids)

        for record in records:
            vals = {"state": "rejected", "rejection_reason": self.reason}
            if record.lifecycle_stage in ["draft", "pending_planning"]:
                active_state = record.planning_state
                vals["planning_state"] = "rejected"
                vals["lifecycle_stage"] = "planning_rejected"
            elif record.lifecycle_stage in ["planning_approved", "pending_cultivation"]:
                active_state = record.cultivation_state
                vals["cultivation_state"] = "rejected"
                vals["lifecycle_stage"] = "cultivation_rejected"
            elif record.lifecycle_stage in ["cultivation_approved", "pending_sowing"]:
                active_state = record.sowing_state
                vals["sowing_state"] = "rejected"
                vals["lifecycle_stage"] = "sowing_rejected"
            elif record.lifecycle_stage in ["sowing_approved", "pending_harvesting"]:
                active_state = record.harvesting_state
                vals["harvesting_state"] = "rejected"
                vals["lifecycle_stage"] = "harvesting_rejected"
            else:
                active_state = False

            if active_state == 'pending_wah':
                vals["rejected_at_stage"] = "wah"
            else:
                vals["rejected_at_stage"] = "sms"

            record.write(vals)

        return {"type": "ir.actions.act_window_close"}
