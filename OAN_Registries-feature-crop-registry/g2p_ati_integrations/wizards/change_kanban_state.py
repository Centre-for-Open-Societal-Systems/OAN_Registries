from odoo import fields, models


class G2PChangeStateWizard(models.TransientModel):
    _name = "change.state.wizard"

    validation_status = fields.Many2one("g2p.validation.status")
    remark = fields.Char(string="Status Remark")

    def change_kanban_state(self):
        active_ids = self._context.get("active_ids")
        self.ensure_one()
        record = self.env["draft.record"].browse(active_ids[0])
        record.write(
            {
                "validation_status": self.validation_status,
                "status_remark": self.remark,
            }
        )
   
