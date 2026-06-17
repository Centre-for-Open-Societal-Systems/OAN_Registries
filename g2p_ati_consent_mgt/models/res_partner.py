from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    consent_request_ids = fields.One2many("g2p.consent.request", "farmer_id", string="Consent Requests")
    consent_request_count = fields.Integer(compute="_compute_consent_request_count", string="Consent Count")
    consent_receipt_ids = fields.One2many("g2p.consent.receipt", "partner_id", string="Consent Receipts")
    consent_receipt_count = fields.Integer(compute="_compute_consent_receipt_count", string="Receipt Count")

    is_consent_parent = fields.Boolean(string="Consent Parent", default=False, index=True)
    consent_websub_config_id = fields.Many2one(
        "g2p.datashare.config.websub",
        string="WebSub Configuration",
        domain="[('event_type', '=', 'WEBSUB_INDIVIDUAL_UPDATED'), ('active', '=', True), ('publisher_type', '=', 'external')]",
        help="Selected WebSub configuration used when this partner's consent requests are approved.",
    )
    allowed_data_field_ids = fields.Many2many(
        "g2p.consent.data.field",
        "g2p_consent_parent_data_field_rel",
        "partner_id",
        "field_id",
        string="Allowed Data Fields",
        help="Fields this consent partner can request in consent requests.",
    )
    consent_portal_user_ids = fields.One2many(
        "res.users",
        "consent_parent_partner_id",
        string="Portal Users",
    )
    consent_portal_user_count = fields.Integer(
        string="Portal Users",
        compute="_compute_consent_portal_user_count",
    )
    consent_portal_role_ids = fields.One2many(
        "g2p.consent.portal.role",
        "consent_parent_partner_id",
        string="Portal Roles",
    )
    consent_portal_role_count = fields.Integer(
        string="Portal Roles",
        compute="_compute_consent_portal_role_count",
    )

    def _compute_consent_request_count(self):
        consent_obj = self.env["g2p.consent.request"]
        for rec in self:
            rec.consent_request_count = consent_obj.search_count([("farmer_id", "=", rec.id)])

    def _compute_consent_receipt_count(self):
        receipt_obj = self.env["g2p.consent.receipt"]
        for rec in self:
            rec.consent_receipt_count = receipt_obj.search_count([("partner_id", "=", rec.id)])

    @api.depends("consent_portal_user_ids")
    def _compute_consent_portal_user_count(self):
        grouped_data = self.env["res.users"].sudo().read_group(
            [("consent_parent_partner_id", "in", self.ids)],
            ["consent_parent_partner_id"],
            ["consent_parent_partner_id"],
        )
        counts = {
            item["consent_parent_partner_id"][0]: item["consent_parent_partner_id_count"]
            for item in grouped_data
        }
        for partner in self:
            partner.consent_portal_user_count = counts.get(partner.id, 0)

    @api.depends("consent_portal_role_ids")
    def _compute_consent_portal_role_count(self):
        grouped_data = self.env["g2p.consent.portal.role"].sudo().read_group(
            [("consent_parent_partner_id", "in", self.ids)],
            ["consent_parent_partner_id"],
            ["consent_parent_partner_id"],
        )
        counts = {
            item["consent_parent_partner_id"][0]: item["consent_parent_partner_id_count"]
            for item in grouped_data
        }
        for partner in self:
            partner.consent_portal_role_count = counts.get(partner.id, 0)

    def action_view_consent_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent Requests"),
            "res_model": "g2p.consent.request",
            "view_mode": "tree,form",
            "domain": [("farmer_id", "=", self.id)],
            "context": {"default_farmer_id": self.id, "search_default_group_by_status": 1},
        }

    def action_open_consent_portal_users(self):
        self.ensure_one()
        tree_view = self.env.ref(
            "g2p_ati_consent_mgt.view_g2p_ati_consent_portal_users_tree", raise_if_not_found=False
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Portal Users"),
            "res_model": "res.users",
            "view_mode": "tree,form",
            "views": [(tree_view.id, "tree"), (False, "form")] if tree_view else [(False, "tree"), (False, "form")],
            "domain": [("consent_parent_partner_id", "=", self.id)],
            "context": {"default_consent_parent_partner_id": self.id},
        }

    def action_open_consent_portal_roles(self):
        self.ensure_one()
        tree_view = self.env.ref(
            "g2p_ati_consent_mgt.view_g2p_ati_consent_portal_role_tree", raise_if_not_found=False
        )
        form_view = self.env.ref(
            "g2p_ati_consent_mgt.view_g2p_ati_consent_portal_role_form", raise_if_not_found=False
        )
        views = []
        if tree_view:
            views.append((tree_view.id, "tree"))
        else:
            views.append((False, "tree"))
        if form_view:
            views.append((form_view.id, "form"))
        else:
            views.append((False, "form"))
        return {
            "type": "ir.actions.act_window",
            "name": _("Portal Roles"),
            "res_model": "g2p.consent.portal.role",
            "view_mode": "tree,form",
            "views": views,
            "domain": [("consent_parent_partner_id", "=", self.id)],
            "context": {"default_consent_parent_partner_id": self.id},
        }

    def action_open_create_portal_user_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Portal User"),
            "res_model": "g2p.ati.create.portal.user.wizard",
            "view_mode": "form",
            "view_id": self.env.ref(
                "g2p_ati_consent_mgt.view_g2p_ati_create_portal_user_wizard_form"
            ).id,
            "target": "new",
            "context": {"default_parent_partner_id": self.id},
        }

    def action_view_consent_receipts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent Receipts"),
            "res_model": "g2p.consent.receipt",
            "view_mode": "tree,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }
