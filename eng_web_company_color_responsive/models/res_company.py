# Copyright 2025 Engenere
# License AGPL-3.0 (https://www.gnu.org/licenses/agpl).

from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    RESP_SCSS_TEMPLATE = """
    .o_navbar_apps_menu .dropdown-menu-custom {
      background:
        url("/web_responsive/static/src/img/home-menu-bg-overlay.svg"),
        linear-gradient(
          to bottom,%(color_navbar_bg)s,
          desaturate(lighten(%(color_navbar_bg)s,20%%),15)
        );
    }
    """

    # cor_base = darken(color_navbar_bg, 10 %)
    BORDER_SCSS_TEMPLATE = """
    .o_main_navbar {
      border-bottom: 1px solid darken(%(color_navbar_bg)s,10%%) !important;
    }
    """

    BTN_SECONDARY_SCSS_TEMPLATE = """
    .btn-secondary:not(.disabled) {
    color: %(color_button_bg)s !important;
    }
    .btn-secondary:hover:not(.disabled) {
    color: %(color_button_bg_hover)s !important;
    }
    """

    STATUSBAR_SCSS_TEMPLATE = """
    .o_field_statusbar > .o_statusbar_status
    > .o_arrow_button.o_arrow_button_current.disabled {
    background-color: %(color_button_bg)s !important;
    color: %(color_button_text)s !important;
    }
    """

    OUTLINE_PRIMARY_SCSS_TEMPLATE = """
    .btn-outline-primary:not(.disabled) {
    color: %(color_button_bg)s !important;
    border-color: %(color_button_bg)s !important;
    }
    .btn-outline-primary:hover:not(.disabled) {
    color: %(color_button_text)s !important;
    background-color: %(color_button_bg)s !important;
    border-color: %(color_button_bg)s !important;
    }
    """

    URI_SCSS_TEMPLATE = """
    .o_form_view .o_form_uri > span:first-child {
    color: darken(%(color_link_text)s,10%%) !important;
    }
    """

    NAV_LINK_SCSS_TEMPLATE = """
    .nav-link:hover {
    color: darken(%(color_link_text)s,15%%) !important;
    }
    """

    BTN_ODOO_SCSS_TEMPLATE = """
    .btn-odoo:not(.disabled) {
    background-color: %(color_button_bg)s !important;
    border-color: %(color_button_bg)s !important;
    color: %(color_button_text)s !important;
    }
    .btn-odoo:hover:not(.disabled) {
    background-color: %(color_button_bg_hover)s !important;
    border-color: %(color_button_bg_hover)s !important;
    color: %(color_button_text)s !important;
    }
    """
    # ------------------------------------------------------------------ #
    #  Overrides                                                        #
    # ------------------------------------------------------------------ #

    def _scss_generate_content(self):
        self.ensure_one()
        base = super()._scss_generate_content()
        vals = self._scss_get_sanitized_values()
        border = self.BORDER_SCSS_TEMPLATE % vals
        resp = self.RESP_SCSS_TEMPLATE % vals
        btn_sec = self.BTN_SECONDARY_SCSS_TEMPLATE % vals
        status = self.STATUSBAR_SCSS_TEMPLATE % vals
        outline = self.OUTLINE_PRIMARY_SCSS_TEMPLATE % vals
        uri = self.URI_SCSS_TEMPLATE % vals
        nav = self.NAV_LINK_SCSS_TEMPLATE % vals
        odoo = self.BTN_ODOO_SCSS_TEMPLATE % vals  # ← novo
        return (
            f"{base}\n{border}\n{resp}\n{btn_sec}\n{status}\n"
            f"{outline}\n{uri}\n{nav}\n{odoo}\n"
        )
