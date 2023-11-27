# Copyright 2023 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from .danfe import danfe
from odoo import models
import pytz
import base64
import logging
from lxml import etree
from io import BytesIO
from erpbrasil.edoc.pdf import base

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_html(self, res_ids, data=None):
        if self.report_name == "engenere_danfe.main_template_danfe":
            return

        return super(IrActionsReport, self)._render_qweb_html(res_ids, data=data)

    def _render_qweb_pdf(self, res_ids, data=None):
        if self.report_name == "engenere_danfe.main_template_danfe_oca":
            return self.print_danfe_oca(res_ids)
        elif self.report_name != "engenere_danfe.main_template_danfe":
            return super(IrActionsReport, self)._render_qweb_pdf(res_ids, data=data)

        nfe = self.env["account.move"].search([("id", "in", res_ids)])

        nfe_xml = None
        if nfe.authorization_file_id:
            nfe_xml = base64.b64decode(nfe.authorization_file_id.datas)
        elif nfe.send_file_id:
            nfe_xml = base64.b64decode(nfe.send_file_id.datas)

        if not nfe_xml:
            # Handle the error
            raise ValueError("No file was found.")

        logo = False
        if nfe.issuer == "company" and nfe.company_id.logo:
            logo = base64.b64decode(nfe.company_id.logo)
        elif nfe.issuer != "company" and nfe.company_id.logo_web:
            logo = base64.b64decode(nfe.company_id.logo_web)

        if logo:
            tmpLogo = BytesIO()
            tmpLogo.write(logo)
            tmpLogo.seek(0)
        else:
            tmpLogo = False

        timezone = pytz.timezone(self.env.context.get("tz") or "UTC")

        xml_element = etree.fromstring(nfe_xml)
        oDanfe = danfe(
            list_xml=[xml_element],
            logo=tmpLogo,
            timezone=timezone,
        )

        tmpDanfe = BytesIO()
        oDanfe.writeto_pdf(tmpDanfe)
        danfe_file = tmpDanfe.getvalue()
        tmpDanfe.close()

        return danfe_file, "pdf"

    def print_danfe_oca(self, res_ids):

        nfe = self.env["account.move"].search([("id", "in", res_ids)])

        if nfe.authorization_file_id:
            arquivo = nfe.authorization_file_id
            xml_string = base64.b64decode(arquivo.datas).decode()
        else:
            arquivo = nfe.send_file_id
            xml_string = base64.b64decode(arquivo.datas).decode()
            xml_string = nfe.temp_xml_autorizacao(xml_string)

        pdf = base.ImprimirXml.imprimir(
            string_xml=xml_string,
            # output_dir=self.authorization_event_id.file_path
        )

        return pdf, "pdf"
