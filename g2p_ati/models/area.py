from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Region(models.Model):
    _inherit = "g2p.region"

    name = fields.Char("Region")

    # Spatial / MOA Admin Fields
    admin0_name = fields.Char("Admin 0 Name")
    admin0_pcod = fields.Char("Admin 0 P-Code")
    admin1_pcod = fields.Char("Admin 1 P-Code")
    admin1_refn = fields.Char("Admin 1 Reference Name")
    admin1_altn = fields.Char("Admin 1 Alternate Name")
    admin1_al_1 = fields.Char("Admin 1 Alternate Name 1")
    shape_length = fields.Float("Shape Length")
    shape_area = fields.Float("Shape Area")
    date = fields.Date("Date")
    valid_on = fields.Date("Valid On")
    valid_to = fields.Date("Valid To")
    geom = fields.Text("Geometry")

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name:
                error_message = _("Region name should not empty.")
                raise ValidationError(error_message)

    @api.constrains("code")
    def _check_code(self):
        regions = self.search([])
        for record in self:
            if not record.code:
                error_message = _("Region Code should not empty.")
                raise ValidationError(error_message)
        for region in regions:
            if str(self.code.lower()) == str(region.code.lower()) and self.id != region.id:
                raise ValidationError(_("The code must be unique!"))

    @api.constrains("iso_code")
    def _check_iso_code(self):
        regions = self.search([])
        for record in self:
            if not record.iso_code:
                error_message = _("Region International Code should not empty.")
                raise ValidationError(error_message)
        for region in regions:
            if record.iso_code:
                if self.iso_code.lower() == region.iso_code.lower() and self.id != region.id:
                    raise ValidationError(_("The International code must be unique!"))

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=100):
        args = args or []
        domain = ["|", ("code", operator, name), ("name", operator, name)] + args
        return self.search(domain, limit=limit).name_get()


class Zone(models.Model):
    _name = "g2p.zone"

    region = fields.Many2one("g2p.region", required=True)
    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, string="Zone")

    # Spatial / MOA Admin Fields
    admin2_pcod = fields.Char("Admin 2 P-Code")
    admin2_refn = fields.Char("Admin 2 Reference Name")
    admin2_altn = fields.Char("Admin 2 Alternate Name")
    admin2_al_1 = fields.Char("Admin 2 Alternate Name 1")
    lat = fields.Float("Latitude")
    long = fields.Float("Longitude")
    shape_length = fields.Float("Shape Length")
    shape_area = fields.Float("Shape Area")

    date = fields.Date("Date")
    valid_on = fields.Date("Valid On")
    valid_to = fields.Date("Valid To")
    geom = fields.Text("Geometry")

    # Related Admin Fields
    admin1_name = fields.Char(related="region.name", string="Admin 1 Name", readonly=True)
    admin1_pcod = fields.Char(related="region.admin1_pcod", string="Admin 1 P-Code", readonly=True)
    admin0_name = fields.Char(related="region.admin0_name", string="Admin 0 Name", readonly=True)
    admin0_pcod = fields.Char(related="region.admin0_pcod", string="Admin 0 P-Code", readonly=True)
    @api.constrains("region")
    def _check_zone(self):
        for record in self:
            if not record.region:
                error_message = _("Region should not empty.")
                raise ValidationError(error_message)

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name:
                error_message = _("Zone name should not empty.")
                raise ValidationError(error_message)

    @api.constrains("code")
    def _check_code(self):
        zones = self.search([])
        for record in self:
            if not record.code:
                error_message = _("Zone Code should not empty.")
                raise ValidationError(error_message)

        for zone in zones:
            if self.code.lower() == zone.code.lower() and self.id != zone.id:
                raise ValidationError(_("The code must be unique!"))

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=100):
        args = args or []
        domain = ["|", ("code", operator, name), ("name", operator, name)] + args
        return self.search(domain, limit=limit).name_get()


class Woreda(models.Model):
    _name = "g2p.woreda"

    zone = fields.Many2one("g2p.zone", required=True)
    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, string="Woreda")

    # Spatial / MOA Admin Fields
    admin3_pcod = fields.Char("Admin 3 P-Code")
    admin3_refn = fields.Char("Admin 3 Reference Name")
    admin3_altn = fields.Char("Admin 3 Alternate Name")
    admin3_al_1 = fields.Char("Admin 3 Alternate Name 1")
    shape_length = fields.Float("Shape Length")
    shape_area = fields.Float("Shape Area")

    date = fields.Date("Date")
    valid_on = fields.Date("Valid On")
    valid_to = fields.Date("Valid To")
    geom = fields.Text("Geometry")

    # Related Admin Fields
    admin2_name = fields.Char(related="zone.name", string="Admin 2 Name", readonly=True)
    admin2_pcod = fields.Char(related="zone.admin2_pcod", string="Admin 2 P-Code", readonly=True)
    admin1_name = fields.Char(related="zone.region.name", string="Admin 1 Name", readonly=True)
    admin1_pcod = fields.Char(related="zone.region.admin1_pcod", string="Admin 1 P-Code", readonly=True)
    admin0_name = fields.Char(related="zone.region.admin0_name", string="Admin 0 Name", readonly=True)
    admin0_pcod = fields.Char(related="zone.region.admin0_pcod", string="Admin 0 P-Code", readonly=True)
    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=100):
        args = args or []
        domain = ["|", ("code", operator, name), ("name", operator, name)] + args
        return self.search(domain, limit=limit).name_get()

    @api.constrains("zone")
    def _check_woreda(self):
        for record in self:
            if not record.zone:
                error_message = _("Zone should not empty.")
                raise ValidationError(error_message)

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name:
                error_message = _("Woreda name should not empty.")
                raise ValidationError(error_message)

    @api.constrains("code")
    def _check_code(self):
        woredas = self.search([])
        for record in self:
            if not record.code:
                error_message = _("Woreda Code should not empty.")
                raise ValidationError(error_message)

        for woreda in woredas:
            if self.code.lower() == woreda.code.lower() and self.id != woreda.id:
                raise ValidationError(_("The code must be unique!"))


class Kebele(models.Model):
    _name = "g2p.kebele"

    woreda = fields.Many2one("g2p.woreda", required=True)
    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, string="Kebele")

    @api.constrains("woreda")
    def _check_woreda(self):
        for record in self:
            if not record.woreda:
                error_message = _("Woreda should not empty.")
                raise ValidationError(error_message)

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name:
                error_message = _("kebele name should not empty.")
                raise ValidationError(error_message)

    @api.constrains("code")
    def _check_code(self):
        kebeles = self.search([])
        for record in self:
            if not record.code:
                error_message = _("kebele Code should not empty.")
                raise ValidationError(error_message)

        for kebele in kebeles:
            if self.code.lower() == kebele.code.lower() and self.id != kebele.id:
                raise ValidationError(_("The code must be unique!"))
