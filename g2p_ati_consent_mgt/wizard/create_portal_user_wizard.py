from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class G2PATICreatePortalUserWizard(models.TransientModel):
    _name = "g2p.ati.create.portal.user.wizard"
    _description = "Create Portal User for Consent Parent"

    parent_partner_id = fields.Many2one("res.partner", string="Parent Partner", required=True, readonly=True)
    name = fields.Char(string="Name", required=True)
    login = fields.Char(string="Login", required=True)
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    manager_user_id = fields.Many2one(
        "res.users",
        string="Portal Manager",
        domain="[('consent_parent_partner_id', '=', parent_partner_id)]",
    )
    role_ids = fields.Many2many(
        "g2p.consent.portal.role",
        string="Portal Roles",
        domain="[('consent_parent_partner_id', '=', parent_partner_id)]",
    )
    can_manage_hierarchy = fields.Boolean(
        string="Can Create Users & Manage Hierarchy",
        help="Allows this portal user to create portal users, create roles, and manage user hierarchy in the consent portal.",
    )
    send_reset_password = fields.Boolean(string="Send Reset Password Email", default=False)

    @api.model
    def default_get(self, field_list):
        result = super().default_get(field_list)
        if not result.get("parent_partner_id"):
            active_model = self.env.context.get("active_model")
            active_id = self.env.context.get("active_id")
            if active_model == "res.partner" and active_id:
                result["parent_partner_id"] = active_id
        return result

    def action_create_portal_user(self):
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only Settings users can create portal users from this wizard."))

        login = (self.login or "").strip()
        if not login:
            raise UserError(_("Login is required."))
        if self.env["res.users"].sudo().search_count([("login", "=", login)]):
            raise UserError(_("Login '%s' already exists. Please use a different login.") % login)

        parent_partner = self.parent_partner_id.sudo()
        if not parent_partner.is_consent_parent:
            parent_partner.write({"is_consent_parent": True})

        if self.manager_user_id and self.manager_user_id.consent_parent_partner_id != parent_partner:
            raise UserError(_("Selected portal manager does not belong to this consent parent."))

        role_ids = self.role_ids.filtered(
            lambda role: role.consent_parent_partner_id == parent_partner
        ).ids

        child_partner = self.env["res.partner"].sudo().create(
            {
                "name": self.name,
                "email": self.email or False,
                "phone": self.phone or False,
                "type": "contact",
                "parent_id": parent_partner.id,
            }
        )

        portal_group = self.env.ref("base.group_portal")
        user = self.env["res.users"].sudo().with_context(no_reset_password=True).create(
            {
                "name": self.name,
                "login": login,
                "email": self.email or False,
                "partner_id": child_partner.id,
                "consent_parent_partner_id": parent_partner.id,
                "consent_portal_manager_user_id": self.manager_user_id.id or False,
                "consent_portal_role_ids": [(6, 0, role_ids)],
                "consent_portal_can_manage_hierarchy": self.can_manage_hierarchy,
                "groups_id": [(6, 0, [portal_group.id])],
            }
        )

        if self.send_reset_password:
            user.action_reset_password()

        return {"type": "ir.actions.act_window_close"}
