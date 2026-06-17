from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = "res.users"

    consent_parent_partner_id = fields.Many2one(
        "res.partner",
        string="Parent Partner",
        index=True,
        domain=[("is_consent_parent", "=", True)],
    )
    consent_portal_role_ids = fields.Many2many(
        "g2p.consent.portal.role",
        "g2p_consent_portal_role_user_rel",
        "user_id",
        "role_id",
        string="Consent Portal Roles",
        domain="[('consent_parent_partner_id', '=', consent_parent_partner_id)]",
    )
    consent_portal_manager_user_id = fields.Many2one(
        "res.users",
        string="Portal Manager",
        index=True,
        domain="[('consent_parent_partner_id', '=', consent_parent_partner_id)]",
    )
    consent_portal_child_user_ids = fields.One2many(
        "res.users",
        "consent_portal_manager_user_id",
        string="Portal Child Users",
    )
    consent_portal_can_manage_hierarchy = fields.Boolean(
        string="Can Manage Consent Portal Hierarchy",
        help="Allows this portal user to create roles, create portal users, and manage hierarchy in the consent portal.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._sync_partner_parent_from_consent_parent()
        return users

    def write(self, vals):
        result = super().write(vals)
        if {"partner_id", "consent_parent_partner_id"} & set(vals):
            self._sync_partner_parent_from_consent_parent()
        return result

    def _sync_partner_parent_from_consent_parent(self):
        for user in self.filtered(lambda rec: rec.partner_id and rec.consent_parent_partner_id):
            if user.partner_id.parent_id != user.consent_parent_partner_id:
                user.partner_id.sudo().write({"parent_id": user.consent_parent_partner_id.id})

    def _get_consent_portal_descendant_user_ids(self):
        self.ensure_one()
        if not self.consent_parent_partner_id:
            return []

        user_model = self.sudo().with_context(active_test=False)
        descendant_ids = set()
        frontier = {self.id}
        while frontier:
            children = user_model.search(
                [
                    ("consent_parent_partner_id", "=", self.consent_parent_partner_id.id),
                    ("consent_portal_manager_user_id", "in", list(frontier)),
                ]
            )
            frontier = set(children.ids) - descendant_ids
            descendant_ids.update(frontier)
        return sorted(descendant_ids)

    def _get_consent_portal_visible_user_ids(self):
        self.ensure_one()
        return [self.id] + self._get_consent_portal_descendant_user_ids()

    @api.constrains(
        "consent_parent_partner_id",
        "consent_portal_manager_user_id",
        "consent_portal_role_ids",
    )
    def _check_consent_portal_hierarchy(self):
        for user in self:
            manager = user.consent_portal_manager_user_id
            if manager:
                if manager == user:
                    raise ValidationError(_("A portal user cannot manage themselves."))
                if not user.consent_parent_partner_id:
                    raise ValidationError(
                        _("Portal hierarchy requires a consent parent partner on the user.")
                    )
                if manager.consent_parent_partner_id != user.consent_parent_partner_id:
                    raise ValidationError(
                        _("Portal manager must belong to the same consent parent partner.")
                    )
                ancestor = manager
                while ancestor:
                    if ancestor == user:
                        raise ValidationError(_("Portal user hierarchy cannot contain cycles."))
                    ancestor = ancestor.consent_portal_manager_user_id

            invalid_roles = user.consent_portal_role_ids.filtered(
                lambda role: role.consent_parent_partner_id != user.consent_parent_partner_id
            )
            if invalid_roles:
                raise ValidationError(
                    _("All assigned portal roles must belong to the same consent parent partner as the user.")
                )
