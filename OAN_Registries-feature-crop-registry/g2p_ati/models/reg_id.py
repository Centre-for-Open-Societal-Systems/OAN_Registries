import re

from odoo import _, api, models
from odoo.exceptions import ValidationError


class G2PRegistrantID(models.Model):
    _inherit = "g2p.reg.id"

    @api.constrains("id_type", "value")
    def _check_value_format(self):
        self.check_value()

    def check_value(self):
        for record in self:
            if record.id_type.name == "UID":
                pattern = r"^\d{4} \d{4} \d{4}$"
                if not re.match(pattern, record.value):
                    raise ValidationError(_("Invalid format for UID. Correct format is '0000 0000 0000'"))

            elif record.id_type.name in ["Farmer ODK ACK ID", "Member ODK ACK ID"]:
                pattern = r"^[a-zA-Z]{3}-\d{4}-\d{4}-\d{4}-\d{4}-\d{6}$"
                if not re.match(pattern, record.value):
                    raise models.ValidationError(
                        _(
                            "Invalid format for ODK ACK ID:\n"
                            "Valid format is as follows:\n"
                            "xxx-0000-0000-0000-0000-000000\n"
                            "Where x is a letter, 0 is a digit"
                        )
                    )

            elif record.id_type.name == "RID":
                pattern = r"^\d{29}$"
                if not re.match(pattern, record.value):
                    raise ValidationError(_("RID should be exactly 29 digits"))
