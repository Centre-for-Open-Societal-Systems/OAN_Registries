import logging
import re
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .utils import eth_date

_logger = logging.getLogger(__name__)


class G2PCropInformation(models.Model):
    _name = "g2p.crop.information"
    _rec_name = "partner_id"

    partner_id = fields.Many2one("res.partner", string="Farmer", required=True, index=True)
    farmer_id = fields.Char(string="Farmer ID", readonly=True)
    farmer_fyda_id = fields.Char(string="Fyda ID")
    crop = fields.Many2one("g2p.crop", required=True, index=True)

    collected_gc = fields.Date(string="Planted date in GC")
    collected_ec = fields.Char(string="Planted date in EC")
    season = fields.Many2one("g2p.season", store=True)
    is_diseased = fields.Selection(
        string="Has this crop been affected by illness?", selection=[("yes", "Yes"), ("no", "No")]
    )
    illness_type = fields.Many2many("g2p.illness.type", string="Disease")

    @api.constrains("is_diseased", "illness_type")
    def _check_illness_type_required(self):
        """Ensure illness_type is required if is_diseased is 'yes'."""
        for record in self:
            if record.is_diseased == "yes" and not record.illness_type:
                error_message = _("Illness type is required when the crop is diseased.")
                raise ValidationError(error_message)

    @api.constrains("collected_gc")
    def _add_collected_gc(self):
        self._update_ec_constraint()

    @api.onchange("collected_gc")
    def _onchange_collected_gc(self):
        self._update_ec_onchange()

    @api.constrains("collected_ec")
    def _add_collected_ec(self):
        self._update_gc_constraint()

    @api.onchange("collected_ec")
    def _onchange_collected_ec(self):
        self._update_gc_onchange()

    def _update_gc_onchange(self):
        for record in self:
            if record.collected_ec:
                self._update_gc(record)

    def _update_gc_constraint(self):
        for record in self:
            if record.collected_ec and not record.collected_gc:
                self._update_gc(record)

    def _update_gc(self, record):
        eth_date.check_ethipian_date_str(record.collected_ec)
        date_list = re.split("[-/,]", record.collected_ec)
        gc_date = eth_date.to_gregorian(int(date_list[2]), int(date_list[1]), int(date_list[0]))
        record.collected_gc = gc_date

    def _update_ec_onchange(self):
        for record in self:
            if record.collected_gc:
                self._update_ec(record)

    def _update_ec_constraint(self):
        for record in self:
            if record.collected_gc and not record.collected_ec:
                self._update_ec(record)

    def _update_ec(self, record):
        cdate = date(record.collected_gc.year, record.collected_gc.month, record.collected_gc.day)
        ethiopian_date_str = eth_date.to_ethiopian(cdate.year, cdate.month, cdate.day)
        record.collected_ec = eth_date.convert_tuple_to_string_with_separator(ethiopian_date_str)

        season = self.env["g2p.season"].search(
            [
                ("start_month", "<=", record.collected_gc.month),
                ("end_month", ">=", record.collected_gc.month),
                ("start_day", "<=", record.collected_gc.day),
                ("end_day", ">=", record.collected_gc.day),
            ],
            limit=1,
        )

        if season:
            _logger.info("found a  season")
            record.season = season.id
