from odoo import models

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        result = super(IrHttp, self).session_info()
        user = self.env.user
        result['consent_parent_partner_id'] = user.consent_parent_partner_id.id if user.consent_parent_partner_id else False
        return result
