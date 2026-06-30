# Part of OpenG2P. See LICENSE file for full copyright and licensing details.
from odoo import http
from odoo.http import request

from odoo.addons.g2p_registration_portal_base.controllers.main import G2PregistrationPortalBase


class ConsentPortalController(G2PregistrationPortalBase):
    """Consent portal routing on top of the G2P registry portal stack."""

    @http.route(["/portal/home"], type="http", auth="user")
    def portal_home(self, **kwargs):
        if request.env.user.consent_parent_partner_id:
            return request.redirect("/consent/management")
        return super().portal_home(**kwargs)

    @http.route(["/my", "/my/home"], type="http", auth="user", website=True)
    def my_home_redirect(self, **kwargs):
        if request.env.user.consent_parent_partner_id:
            return request.redirect("/consent/management")
        return request.redirect("/portal/home")
