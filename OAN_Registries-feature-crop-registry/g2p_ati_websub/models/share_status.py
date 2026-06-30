# Part of OpenG2P. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class G2PPartnerWebsubShareStatus(models.Model):
    _name = "g2p.partner.websub.share.status"
    _description = "Partner WebSub Share Status"
    _order = "last_shared_at desc, id desc"

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        ondelete="cascade",
        index=True,
    )
    config_id = fields.Many2one(
        "g2p.datashare.config.websub",
        required=True,
        ondelete="cascade",
        index=True,
    )
    publisher_type = fields.Selection(
        related="config_id.publisher_type",
        string="Publisher Type",
        store=True,
        readonly=True,
    )
    last_event_type = fields.Selection(
        selection=[
            ("WEBSUB_GROUP_CREATED", "Group Created"),
            ("WEBSUB_GROUP_UPDATED", "Group Updated"),
            ("WEBSUB_GROUP_DELETED", "Group Deleted"),
            ("WEBSUB_INDIVIDUAL_CREATED", "Individual Created"),
            ("WEBSUB_INDIVIDUAL_UPDATED", "Individual Updated"),
            ("WEBSUB_INDIVIDUAL_DELETED", "Individual Deleted"),
        ],
        string="Last Event",
        readonly=True,
    )
    last_shared_at = fields.Datetime(
        required=True,
        readonly=True,
    )
    successful_share_count = fields.Integer(
        default=0,
        readonly=True,
    )

    _sql_constraints = [
        (
            "g2p_partner_websub_share_status_partner_config_uniq",
            "unique(partner_id, config_id)",
            "Each partner can only have one successful-share status row per WebSub config.",
        ),
    ]


class ResPartnerWebsubShareStatus(models.Model):
    _inherit = "res.partner"

    websub_last_shared_at = fields.Datetime(
        string="Last Shared",
        readonly=True,
        copy=False,
    )
    websub_share_status_ids = fields.One2many(
        "g2p.partner.websub.share.status",
        "partner_id",
        string="WebSub Share Status",
        readonly=True,
        copy=False,
    )

    def _mark_websub_share_success(self, config, shared_at=None):
        shared_at = shared_at or fields.Datetime.now()
        status_model = self.env["g2p.partner.websub.share.status"].sudo()
        for partner in self.sudo():
            if not partner.exists() or not config:
                continue

            status = status_model.search(
                [
                    ("partner_id", "=", partner.id),
                    ("config_id", "=", config.id),
                ],
                limit=1,
            )
            values = {
                "partner_id": partner.id,
                "config_id": config.id,
                "last_event_type": config.event_type,
                "last_shared_at": shared_at,
            }
            if status:
                values["successful_share_count"] = status.successful_share_count + 1
                status.write(values)
            else:
                values["successful_share_count"] = 1
                status_model.create(values)

            partner.with_context(ati_skip_websub_enqueue=True).write({"websub_last_shared_at": shared_at})
