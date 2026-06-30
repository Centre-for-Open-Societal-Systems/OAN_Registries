from odoo import models


class ProcessIndividualMixin(models.AbstractModel):
    _inherit = "process_individual.rest.mixin"

    def _process_individual(self, individual):
        res = super()._process_individual(individual)
        fields_to_check = ["gf_name_eng", "first_name_amh", "family_name_amh", "gf_name_amh"]

        for field in fields_to_check:
            value = individual.model_dump().get(field)
            if value:
                res[field] = value

        return res
