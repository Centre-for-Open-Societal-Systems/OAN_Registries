import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class RejectWizard(models.TransientModel):
    _inherit = "reject.wizard"

    def confirm_rejection(self):
        result = super().confirm_rejection()

        active_ids = self._context.get("active_ids")
        if not active_ids:
            return result

        record = self.env["draft.record"].browse(active_ids[0])
        if not record:
            return result

        # Close all remaining activities after rejection is finalized.
        record._close_record_activities()
        record._notify_draft_owner_rejected(self.rejection_reason)

        return result
