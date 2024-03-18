# Copyright 2024 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import base64

from odoo import _, models
from odoo.exceptions import UserError


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def temp_xml_autorizacao(self, xml_string):
        return super().temp_xml_autorizacao(xml_string=xml_string)

    def _render_qweb_html(self, res_ids, data=None):
        if self.report_name == "eng_report_danfe.main_template_danfe":
            return super()._render_qweb_html(res_ids, data=data)

    def _render_qweb_pdf(self, res_ids, data=None):
        if self.report_name not in ["eng_report_danfe.main_template_danfe"]:
            return super(IrActionsReport, self)._render_qweb_pdf(res_ids, data=data)

        nfe = self.env["account.move"].search([("id", "in", res_ids)])

        return self._render_danfe(nfe)

    def _render_danfe(self, nfe):
        return super()._render_danfe(nfe=nfe)
