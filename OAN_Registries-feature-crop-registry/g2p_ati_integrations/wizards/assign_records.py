from odoo import _, fields, models
from odoo.exceptions import UserError


class G2PAssignRecordsWizard(models.TransientModel):
    _name = "assign.records.wizard"

    assigned_region = fields.Many2many("g2p.region", string="Regions")
    language_skills = fields.Many2many("g2p.lang", string="Languages")

    def assign_groups(self):
        # domain = []
        
        active_ids = self._context["active_ids"]
        records = self.env["g2p.imported.record"].browse(active_ids)

    
        update_vals = {} 
        if self.assigned_region:
            update_vals["assigned_region"] = [(6, 0, self.assigned_region.ids)]

        if self.language_skills:
            update_vals["assigned_languages"] = [(6, 0, self.language_skills.ids)]

        if records and update_vals:
            records.write(update_vals)
