# Copyright 2024 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
from io import BytesIO

from PyPDF2 import PdfFileMerger

from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nBrFiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    payment_method_code = fields.Char(
        related="move_ids.payment_mode_id.payment_method_code"
    )

    def view_boleto_pdf(self):
        if not self.move_ids.file_boleto_pdf_id:
            return self.move_ids.generate_boleto_pdf()
        return self.move_ids._target_new_tab(self.move_ids.file_boleto_pdf_id)

    def generate_combined_pdf(self):
        if self.state != "posted":
            raise UserError(
                _("PDF can only be generated if the document status is posted.")
            )
        if self.state_edoc != "autorizada":
            raise UserError(
                _("PDF can only be generated if the document status is authorized.")
            )
        if not self.move_ids.file_boleto_pdf_id:
            return self.move_ids.generate_boleto_pdf()

        if not self.file_report_id:
            self.make_pdf()
            return self.move_ids._target_new_tab(self.file_report_id)

        boleto_pdf = base64.b64decode(self.move_ids.file_boleto_pdf_id.datas)
        danfe_pdf = base64.b64decode(self.file_report_id.datas)

        combined_pdf = self._combine_pdfs(boleto_pdf, danfe_pdf)
        inv_number = self.document_number.zfill(8)
        file_name = f"boleto_danfe_nf-{inv_number}.pdf"
        combined_pdf_attachment = self.env["ir.attachment"].create(
            {
                "name": file_name,
                "store_fname": file_name,
                "res_model": self._name,
                "res_id": self.id,
                "datas": base64.b64encode(combined_pdf),
                "mimetype": "application/pdf",
                "type": "binary",
            }
        )

        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/{id}/{nome}".format(
                id=combined_pdf_attachment.id, nome=combined_pdf_attachment.name
            ),
            "target": "new",
        }

    def _combine_pdfs(self, boleto_pdf, danfe_pdf):
        merger = PdfFileMerger()
        merger.append(BytesIO(danfe_pdf))
        merger.append(BytesIO(boleto_pdf))
        output = BytesIO()
        merger.write(output)
        output.seek(0)
        return output.read()
