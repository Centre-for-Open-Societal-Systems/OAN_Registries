import logging
import re
from datetime import date, datetime

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .utils import eth_date

_logger = logging.getLogger(__name__)

ETHIOPIAN_MONTH_ORDER = {
    "September": 1,
    "October": 2,
    "November": 3,
    "December": 4,
    "January": 5,
    "February": 6,
    "March": 7,
    "April": 8,
    "May": 9,
    "June": 10,
    "July": 11,
    "August": 12,
    "Pagume": 13,
}


class G2PFarmer(models.Model):
    _inherit = "res.partner"
    _order = "registration_date desc"

    zone = fields.Many2one("g2p.zone", domain="[('region', '=', region)]")
    woreda = fields.Many2one("g2p.woreda", domain="[('zone', '=', zone)]")
    kebele = fields.Many2one("g2p.kebele", domain="[('woreda', '=', woreda)]")

    given_name = fields.Char(string="First Name(English)", translate=False)
    family_name = fields.Char(string="Father's Name(English)", translate=False)
    gf_name_eng = fields.Char(string="Grand Father's Name(English)", translate=False)

    first_name_amh = fields.Char(string="First Name(Amharic)", translate=False)
    family_name_amh = fields.Char(string="Father's Name(Amharic)", translate=False)
    gf_name_amh = fields.Char(string="Grand Father's Name(Amharic)", translate=False)
    first_name_other = fields.Char(string="First Name", translate=False)
    family_name_other = fields.Char(string="Father's Name", translate=False)
    gf_name_other = fields.Char(string="Grand Father's Name", translate=False)

    has_personal_phone = fields.Selection(
        string="Do you have a personal phone number? ", selection=[("yes", "Yes"), ("no", "No")]
    )
    has_national_id = fields.Selection(
        string="Do you have a national id? ", selection=[("yes", "Yes"), ("no", "No")]
    )
    birthdate_ec = fields.Char(string="Date Of Birth (EC)", help="YYYY-MM-DD")
    age = fields.Char(
        compute="_compute_calc_age",
        inverse="_inverse_age",
        size=50,
        readonly=False,
    )
    primary_Language = fields.Many2one("g2p.lang")
    is_farmer = fields.Selection(
        string="Are you a farmer? ", index=True, selection=[("yes", "Yes"), ("no", "No")]
    )
    farming_type = fields.Selection(
        selection=[
            ("crop_farming", "Crop Farming"),
            ("livestock_farming", "Livestock Farming"),
            ("mixed_farming", "Mixed Farming"),
        ]
    )
    is_disabled = fields.Selection(string="Are you disabled? ", selection=[("yes", "Yes"), ("no", "No")])

    # MEMEBERSHIP
    is_member_of_primary_cooperative = fields.Selection(
        string="Is member of primary cooperative? ", selection=[("yes", "Yes"), ("no", "No")]
    )
    primary_cooperatives = fields.Many2one("g2p.primary.cooperative")
    is_member_of_cooperative_union = fields.Selection(
        string="Is member of cooperative union? ", selection=[("yes", "Yes"), ("no", "No")]
    )
    cooperative_unions = fields.Many2one("g2p.cooperative.union")
    is_member_in_farmer_cluster = fields.Selection(
        string="Is member in farmer cluster? ", selection=[("yes", "Yes"), ("no", "No")]
    )
    primary_commodity = fields.Many2one("g2p.primary.commodity")
    role_in_farmer_cluster = fields.Selection(
        selection=[
            ("lead", "Lead"),
            ("deputy", "Deputy"),
            ("secretary", "Secretary"),
            ("accountant", "Accountant"),
            ("member", "Member"),
        ],
    )
    state = fields.Selection(
        tracking=True,
        selection=[
            ("draft", "Draft"),
            ("rejected", "Rejected"),
            ("update_requested", "Update Requested"),
            ("approved", "Approved"),
        ],
        index=True,
        default="draft",
    )

    # AGRICULTURAL RESOURCES
    do_you_use_fertilizer = fields.Selection(
        string="Do you use fertilizer? ", selection=[("yes", "Yes"), ("no", "No")]
    )
    amount_fertilizer_utilized = fields.Float(string="What is The amount Of fertilizer you have(qt)? ")
    do_you_use_pesticide = fields.Selection(
        string="Do you use pesticide? ", selection=[("yes", "Yes"), ("no", "No")]
    )
    amount_pesticide_utilized = fields.Float(string="What is The amount Of pesticide you have(L)? ")
    do_you_use_insecticide = fields.Selection(
        string="Do you use insecticide? ", selection=[("yes", "Yes"), ("no", "No")]
    )
    amount_insecticide_utilized = fields.Float(string="What is The amount Of insecticide you have in(L)? ")
    do_you_use_improved_seed = fields.Selection(
        string="Do you use improved seed? ", selection=[("yes", "Yes"), ("no", "No")]
    )
    amount_improved_seed_utilized = fields.Float(
        string="What is the amount Of improved seed you have used(qt)? "
    )

    # ACCESS TO RESOURCES
    crop_water_sources = fields.Many2many(
        "g2p.water.source",
        "crop_water",
        "crop_water_source_rel",
        string="What water sources do you use for your crops? ",
    )
    livestock_water_sources = fields.Many2many(
        "g2p.water.source",
        "livestock_water",
        "livestock_water_source_rel",
        string="What water sources do you use for your livestock? ",
    )
    access_to_machinery = fields.Selection(
        string="Do you use machinery? ", selection=[("yes", "Yes"), ("no", "No")]
    )
    type_of_machinery = fields.Many2many("g2p.machinery", string="What kind of machinery do you use? ")
    irrigation_types = fields.Selection(
        string="What type of irrigation do you use?", selection=[("pump", "Pump"), ("canal", "canal")]
    )
    has_finance_access = fields.Selection(
        string="Do you have financial access ", selection=[("yes", "Yes"), ("no", "No")], default="no"
    )
    finance_accesses = fields.Many2many(comodel_name="g2p.finance.access")
    other_farmer_in_hh = fields.Selection(
        string="Is there any other farmer in the household who has separate land? ",
        selection=[("yes", "Yes"), ("no", "No")],
    )
    # SOCIO-ECONOMIC DATA
    martial_status = fields.Selection(
        selection=[
            ("single", "Single"),
            ("married", "Married"),
            ("divorced", "Divorced"),
            ("widowed", "Widowed"),
        ],
    )
    education = fields.Selection(
        [
            ("illiterate", "Illiterate"),
            ("read_write", "Can Read and Write"),
            ("basic", "Basic(1-8)"),
            ("intermediary", "Intermediary(9-12)"),
            ("higher_education", "Higher Education(University and College)"),
        ],
        string="Educational Level",
    )
    hh_is_household_head = fields.Selection(
        string="Are you a household head? ", selection=[("yes", "Yes"), ("no", "No")]
    )
    hh_income_type = fields.Many2many(comodel_name="g2p.hh.income", string="House Hold Income")

    size_of_family = fields.Integer(string="Family Size")
    number_of_children_in_family = fields.Integer(string="Number Of Children In The family")
    number_of_males_in_family = fields.Integer(string="Number Of Males In The family")
    number_of_females_in_family = fields.Integer(string="Number Of Females In The family")
    other_family_member_own_land = fields.Selection(
        string="Other Family Member Own Land", selection=[("yes", "Yes"), ("no", "No")]
    )

    mother_included = fields.Boolean()
    father_included = fields.Boolean()

    # Land INFORMATIONS
    land_information_ids = fields.One2many("g2p.land.information", "partner_id", string="Land Information")
    crop_information_ids = fields.One2many("g2p.crop.information", "partner_id", string="Crop Information")

    total_land_area = fields.Float(default=0.0, digits=(16, 6), readonly=True, compute="_compute_total_land_area", store=True)

    total_land_rent_area = fields.Float(
        default=0.0, string="Total Rented Land", digits=(16, 6), readonly=True, compute="_compute_total_land_area", store=True
    )
    total_land_owned_area = fields.Float(
        default=0.0, string="Total Owned Land", digits=(16, 6), readonly=True, compute="_compute_total_land_area", store=True
    )
    total_land_crop_sharing_area = fields.Float(
        default=0.0,
        digits=(16, 6),
        string="Total Crop Sharing Land",
        readonly=True,
        compute="_compute_total_land_area",
        store=True,
    )

    age_int = fields.Integer(compute="_compute_calc_age_int", store=True)
    land_ownership = fields.Selection(
        selection=[("owner", "Owner"), ("tenant", "Tenant"), ("hybrid", "Hybrid")],
        compute="_compute_land_ownership",
        store=True,
        readonly=True,
    )
    livestock_information_ids = fields.One2many(
        "g2p.livestock.information", "partner_id", string="Live stock information"
    )
    rejection_reason = fields.Text()

    farmer_id = fields.Char(string="Farmer ID", compute="_compute_farmer_id", store=True, index=True)
    is_psnp_user = fields.Boolean(default=False, string="PSNP User")
    rec_import_source = fields.Many2one("g2p.import.source", string="Import Source")
    odk_instance_id = fields.Char(string="ODK Instance ID", index=True, copy=False)

    @api.onchange("is_member_of_primary_cooperative")
    def _onchange_is_member_of_primary_cooperative(self):
        if self._is_integration_form():
            return
        self.primary_cooperatives = False

    @api.onchange("is_member_of_cooperative_union")
    def _onchange_is_member_of_cooperative_union(self):
        if self._is_integration_form():
            return
        self.cooperative_unions = False

    @api.onchange("is_member_in_farmer_cluster")
    def _onchange_is_member_in_farmer_cluster(self):
        if self._is_integration_form():
            return
        self.role_in_farmer_cluster = False
        self.primary_commodity = False

    @api.onchange("region")
    def _onchange_region(self):
        if self.zone.region != self.region:
            self.zone = False
            self.woreda = False
            self.kebele = False

    @api.onchange("zone")
    def _onchange_zone(self):
        if self.woreda.zone != self.zone:
            self.woreda = False
            self.kebele = False

    @api.onchange("woreda")
    def _onchange_woreda(self):
        if self.kebele.woreda != self.woreda:
            self.kebele = False

    @api.onchange("number_of_males_in_family", "number_of_females_in_family")
    def _onchange_family_size(self):
        if not self._is_integration_form():
            return
        males = self.number_of_males_in_family or 0
        females = self.number_of_females_in_family or 0
        if males < 0 or females < 0:
            return
        self.size_of_family = males + females
        if (
            self.number_of_children_in_family
            and self.size_of_family
            and self.number_of_children_in_family > self.size_of_family
        ):
            raise ValidationError(_("Number of children must not exceed family size."))

    @api.onchange("number_of_children_in_family", "size_of_family")
    def _onchange_children_count(self):
        if not self._is_integration_form():
            return
        if (
            self.number_of_children_in_family
            and self.size_of_family
            and self.number_of_children_in_family > self.size_of_family
        ):
            raise ValidationError(_("Number of children must not exceed family size."))

    @api.constrains("number_of_children_in_family", "size_of_family")
    def _check_children_count(self):
        for record in self:
            if not record._is_integration_form():
                continue
            if (
                record.number_of_children_in_family
                and record.size_of_family
                and record.number_of_children_in_family > record.size_of_family
            ):
                raise ValidationError(_("Number of children must not exceed family size."))

    @api.onchange(
        "number_of_males_in_family",
        "number_of_females_in_family",
        "number_of_children_in_family",
    )
    def _onchange_household_positive_numbers(self):
        if not self._is_integration_form():
            return
        self._validate_household_positive_numbers()

    @api.constrains(
        "number_of_males_in_family",
        "number_of_females_in_family",
        "number_of_children_in_family",
    )
    def _check_household_positive_numbers(self):
        for record in self:
            if not record._is_integration_form():
                continue
            record._validate_household_positive_numbers()

    def _validate_household_positive_numbers(self):
        field_labels = {
            "number_of_males_in_family": _("Number of males in the family"),
            "number_of_females_in_family": _("Number of females in the family"),
            "number_of_children_in_family": _("Number of children in the family"),
        }
        for field_name, label in field_labels.items():
            value = getattr(self, field_name)
            # In draft wizard context, an unset Integer can appear as boolean False.
            if value is None or isinstance(value, bool):
                continue
            if value < 0:
                raise ValidationError(_("%s must be zero or greater.") % label)

    def _is_integration_form(self):
        active_model = self.env.context.get("active_model", False)
        return active_model and active_model == "draft.record"




            

   

    @api.onchange("is_group", "family_name", "given_name", "gf_name_eng")
    def name_change_farmer(self):
        # vals = {}
        if not self.is_group:
            name = ""
            if self.given_name:
                name += self.given_name + " "
            if self.family_name:
                name += self.family_name + " "
            if self.gf_name_eng:
                name += self.gf_name_eng

            self.name = name.upper()
            # vals.update({"name": name.upper()})
            # self.update(vals)

    @api.depends("land_information_ids.total_land_area")
    def _compute_total_land_area(self):
        for record in self:
            record.total_land_area = sum(land.total_land_area for land in record.land_information_ids)
            record.total_land_owned_area = sum(
                land.total_land_area for land in record.land_information_ids if land.ownership_type == "owner"
            )
            record.total_land_rent_area = sum(
                land.total_land_area
                for land in record.land_information_ids
                if land.ownership_type == "tenant"
            )
            record.total_land_crop_sharing_area = sum(
                land.total_land_area
                for land in record.land_information_ids
                if land.ownership_type == "crop_share"
            )

    @api.depends("land_information_ids.ownership_type")
    def _compute_land_ownership(self):
        for record in self:
            if record.land_information_ids:
                land_info_records = record.land_information_ids
                owner_count = len(land_info_records.filtered(lambda r: r.ownership_type == "owner"))
                tenant_count = len(land_info_records.filtered(lambda r: r.ownership_type == "tenant"))

                if owner_count > 0 and tenant_count == 0:
                    record.land_ownership = "owner"
                elif tenant_count > 0 and owner_count == 0:
                    record.land_ownership = "tenant"
                elif owner_count > 0 and tenant_count > 0:
                    record.land_ownership = "hybrid"
                else:
                    record.land_ownership = False
            else:
                record.land_ownership = False

    @api.onchange("birthdate")
    def _onchange_birthdate(self):
        if self.birthdate:
            bday = date(self.birthdate.year, self.birthdate.month, self.birthdate.day)
            ethiopian_date_str = eth_date.to_ethiopian(bday.year, bday.month, bday.day)
            self.birthdate_ec = eth_date.convert_tuple_to_string_with_separator(ethiopian_date_str)
            age_int = self.compute_age_int_from_dates(self.birthdate)
            self.age = str(age_int) if age_int is not None else False
            # GC DOB explicitly entered by user should be treated as exact.
            self.birthdate_not_exact = False
        else:
            if self.age and self.age.isdigit():
                age_int = int(self.age)
                if age_int >= 0:
                    gc_date = self._get_sep12_gc_birthdate_from_age(age_int)
                    self.birthdate = gc_date
                    self.birthdate_not_exact = True
                    bday = date(gc_date.year, gc_date.month, gc_date.day)
                    ethiopian_date_str = eth_date.to_ethiopian(bday.year, bday.month, bday.day)
                    self.birthdate_ec = eth_date.convert_tuple_to_string_with_separator(ethiopian_date_str)
            else:
                self.age = False

    @api.onchange("age")
    def _onchange_age(self):
        if self.age and self.age.isdigit():
            age_int = int(self.age)
            if age_int < 0:
                return
            # If an exact DOB exists and age matches that DOB, this onchange was
            # triggered by date -> age synchronization. Keep the explicit date.
            if self.birthdate and not self.birthdate_not_exact:
                age_from_birthdate = self.compute_age_int_from_dates(self.birthdate)
                if age_from_birthdate is not None and self.age == str(age_from_birthdate):
                    bday = date(self.birthdate.year, self.birthdate.month, self.birthdate.day)
                    ethiopian_date_str = eth_date.to_ethiopian(bday.year, bday.month, bday.day)
                    self.birthdate_ec = eth_date.convert_tuple_to_string_with_separator(ethiopian_date_str)
                    return
            # Explicit age input means unknown exact DOB; age drives derived DOB.
            gc_date = self._get_sep12_gc_birthdate_from_age(age_int)
            self.birthdate = gc_date
            self.birthdate_not_exact = True
            bday = date(gc_date.year, gc_date.month, gc_date.day)
            ethiopian_date_str = eth_date.to_ethiopian(bday.year, bday.month, bday.day)
            self.birthdate_ec = eth_date.convert_tuple_to_string_with_separator(ethiopian_date_str)
        else:
            if self.birthdate:
                age_int = self.compute_age_int_from_dates(self.birthdate)
                self.age = str(age_int) if age_int is not None else False
            else:
                self.birthdate_ec = False

    def _inverse_age(self):
        for record in self:
            if not record.age or not record.age.isdigit():
                continue
            age_int = int(record.age)
            if age_int < 0:
                continue
            # Preserve explicit GC/EC DOB unless age onchange switched to approximate mode.
            if record.birthdate and not record.birthdate_not_exact:
                continue
            # Keep save behavior consistent with onchange: age drives derived DOB.
            gc_date = record._get_sep12_gc_birthdate_from_age(age_int)
            record.birthdate = gc_date
            record.birthdate_not_exact = True
            bday = date(gc_date.year, gc_date.month, gc_date.day)
            ethiopian_date_str = eth_date.to_ethiopian(bday.year, bday.month, bday.day)
            record.birthdate_ec = eth_date.convert_tuple_to_string_with_separator(ethiopian_date_str)

    @api.onchange(
        "father_included",
        "mother_included",
        "number_of_males_in_family",
        "number_of_females_in_family",
        "number_of_children_in_family",
    )
    def _onchange_parent_included(self):
        if not self._is_integration_form():
            return
        self._validate_parent_included()

    @api.constrains(
        "father_included",
        "mother_included",
        "number_of_males_in_family",
        "number_of_females_in_family",
    )
    def _check_parent_included(self):
        for record in self:
            if not record._is_integration_form():
                continue
            record._validate_parent_included()

    def _validate_parent_included(self):
        males = self.number_of_males_in_family or 0
        females = self.number_of_females_in_family or 0
        children = self.number_of_children_in_family or 0
        adults = max(males + females - children, 0)
        if self.father_included:
            if males < 1:
                raise ValidationError(_("Father included requires at least 1 male in the family."))
            if adults < 1:
                raise ValidationError(
                    _("Father included requires at least 1 adult in the family.")
                )
        if self.mother_included:
            if females < 1:
                raise ValidationError(_("Mother included requires at least 1 female in the family."))
            if adults < 1:
                raise ValidationError(
                    _("Mother included requires at least 1 adult in the family.")
                )
        if self.father_included and self.mother_included and adults < 2:
            raise ValidationError(
                _("Both parents included requires at least 2 adults in the family.")
            )

    @api.constrains("birthdate")
    def _add_birthdate_ec(self):
        if self.birthdate:
            bday = date(self.birthdate.year, self.birthdate.month, self.birthdate.day)
            ethiopian_date_str = eth_date.to_ethiopian(bday.year, bday.month, bday.day)
            self.birthdate_ec = eth_date.convert_tuple_to_string_with_separator(ethiopian_date_str)

    @api.onchange("birthdate_ec")
    def _onchange_birthdate_ec(self):
        if self.birthdate_ec:
            eth_date.check_ethipian_date_str(self.birthdate_ec)
            date_list = re.split("[-/,]", self.birthdate_ec)
            gc_date = eth_date.to_gregorian(int(date_list[2]), int(date_list[1]), int(date_list[0]))
            if gc_date > fields.date.today():
                raise ValidationError(_("You can't select a date of birth greater than today"))
            self.birthdate = gc_date
            self.birthdate_not_exact = False
            age_int = self.compute_age_int_from_dates(self.birthdate)
            self.age = str(age_int) if age_int is not None else False
        else:
            if self.age and self.age.isdigit():
                age_int = int(self.age)
                if age_int >= 0:
                    gc_date = self._get_sep12_gc_birthdate_from_age(age_int)
                    self.birthdate = gc_date
                    self.birthdate_not_exact = True
                    bday = date(gc_date.year, gc_date.month, gc_date.day)
                    ethiopian_date_str = eth_date.to_ethiopian(bday.year, bday.month, bday.day)
                    self.birthdate_ec = eth_date.convert_tuple_to_string_with_separator(ethiopian_date_str)
            elif self.birthdate:
                bday = date(self.birthdate.year, self.birthdate.month, self.birthdate.day)
                ethiopian_date_str = eth_date.to_ethiopian(bday.year, bday.month, bday.day)
                self.birthdate_ec = eth_date.convert_tuple_to_string_with_separator(ethiopian_date_str)
                age_int = self.compute_age_int_from_dates(self.birthdate)
                self.age = str(age_int) if age_int is not None else False
                self.birthdate_not_exact = False
            else:
                self.birthdate = False
                self.age = False

    def _get_sep12_gc_birthdate_from_age(self, age_int):
        """Age-only mode: use a fixed GC day/month (Sep 12) and adjust year to match age."""
        today = fields.Date.today()
        year = today.year - age_int
        if (today.month, today.day) < (9, 12):
            year -= 1
        return date(year, 9, 12)

    @api.onchange("has_finance_access")
    def _onchange_has_finance_access(self):
        if self.has_finance_access == "no":
            return {"finance_accesses": [(6, 0, [])]}

    def set_to_draft(self):
        for record in self:
            record.state = "draft"

    def state_approve(self):
        for record in self:
            record.state = "approved"

    def state_reject(self):
        return {
            "name": _("Enter Rejection Reason"),
            "type": "ir.actions.act_window",
            "res_model": "g2p.rejection.reason.wizard",
            "view_mode": "form",
            "target": "new",
        }

    @api.depends("birthdate")
    def _compute_calc_age_int(self):
        for line in self:
            line.age_int = self.compute_age_int_from_dates(line.birthdate)

    def compute_age_int_from_dates(self, partner_dob):
        now = datetime.strptime(str(fields.Datetime.now())[:10], "%Y-%m-%d")
        years_months_days = None
        if partner_dob:
            dob = partner_dob
            delta = relativedelta(now, dob)
            years_months_days = str(delta.years)
        return years_months_days

    @api.depends("unique_id", "is_farmer")
    def _compute_farmer_id(self):
        for record in self:
            if record.is_farmer == "yes" and record.unique_id:
                record.farmer_id = f"FR-{record.unique_id}"
            else:
                record.farmer_id = False

    # def _ensure_farmer_id(self):
    #     if not self:
    #         return
    #     self.with_context(skip_farmer_id_ensure=True)._compute_farmer_id()
    #     self.flush_recordset(["farmer_id"])

    # def read(self, fields=None, load="_classic_read"):
    #     if not self.env.context.get("skip_farmer_id_ensure"):
    #         if not fields or "farmer_id" in fields or "unique_id" in fields:
    #             self._ensure_farmer_id()
    #     return super().read(fields=fields, load=load)

    def unlink(self):
        if any(record.state == "approved" for record in self):
            raise ValidationError(_("Cannot delete approved records."))

        return super().unlink()

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if record.hh_is_household_head == "yes":
            record._update_group_memberships()
        return record

    def write(self, vals):
        result = super().write(vals)
        if "zone" in vals or "woreda" in vals or "kebele" in vals or "hh_is_household_head" in vals:
            if self.hh_is_household_head == "yes":
                self._update_group_memberships()
        return result

    def _update_group_memberships(self):
        for record in self:
            if record.hh_is_household_head == "yes":
                for membership in record.individual_membership_ids:
                    group = membership.group
                    if group:
                        group.write(
                            {
                                "region": record.region.id,
                                "zone": record.zone.id,
                                "woreda": record.woreda.id,
                                "kebele": record.kebele.id,
                            }
                        )

                    for group_member in group.group_membership_ids:
                        if (
                            group_member.individual != record
                            and group_member.individual.hh_is_household_head != "yes"
                        ):
                            group_member.individual.write(
                                {
                                    "region": record.region.id,
                                    "zone": record.zone.id,
                                    "woreda": record.woreda.id,
                                    "kebele": record.kebele.id,
                                }
                            )
