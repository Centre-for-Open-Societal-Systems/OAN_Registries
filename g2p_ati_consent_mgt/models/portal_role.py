from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class G2PConsentPortalRole(models.Model):
    _name = "g2p.consent.portal.role"
    _description = "Consent Portal Role"
    _order = "name"

    name = fields.Char(required=True)
    consent_parent_partner_id = fields.Many2one(
        "res.partner",
        string="Consent Parent",
        required=True,
        index=True,
        ondelete="cascade",
        domain=[("is_consent_parent", "=", True)],
    )
    parent_id = fields.Many2one(
        "g2p.consent.portal.role",
        string="Parent Role",
        domain="[('consent_parent_partner_id', '=', consent_parent_partner_id)]",
        ondelete="restrict",
    )
    child_ids = fields.One2many("g2p.consent.portal.role", "parent_id", string="Child Roles")
    description = fields.Text()
    active = fields.Boolean(default=True)
    user_ids = fields.Many2many(
        "res.users",
        "g2p_consent_portal_role_user_rel",
        "role_id",
        "user_id",
        string="Portal Users",
    )
    user_count = fields.Integer(string="Assigned Users", compute="_compute_user_count")

    _sql_constraints = [
        (
            "g2p_consent_portal_role_name_parent_uniq",
            "unique(name, consent_parent_partner_id)",
            "Role names must be unique inside the same consent parent.",
        ),
    ]

    @api.depends("user_ids")
    def _compute_user_count(self):
        for rec in self:
            rec.user_count = len(rec.user_ids)

    @api.constrains("parent_id", "consent_parent_partner_id")
    def _check_parent_hierarchy(self):
        for rec in self:
            parent = rec.parent_id
            if not parent:
                continue
            if parent == rec:
                raise ValidationError(_("A portal role cannot be its own parent."))
            if parent.consent_parent_partner_id != rec.consent_parent_partner_id:
                raise ValidationError(
                    _("Parent role must belong to the same consent parent as the child role.")
                )
            ancestor = parent
            while ancestor:
                if ancestor == rec:
                    raise ValidationError(_("Portal role hierarchy cannot contain cycles."))
                ancestor = ancestor.parent_id
