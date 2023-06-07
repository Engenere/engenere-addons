# Copyright 2023 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
import base64

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    MODELO_FISCAL_NFCE,
    MODELO_FISCAL_NFE,
    PROCESSADOR_OCA,
)

def filter_processador_edoc_nfe(record):
    if record.processador_edoc == PROCESSADOR_OCA and record.document_type_id.code in [
        MODELO_FISCAL_NFE,
        MODELO_FISCAL_NFCE,
    ]:
        return True
    return False


class L10n_br_fiscalDocument(models.Model):

    _inherit = "l10n_br_fiscal.document"

    def make_pdf(self):
        if not self.filtered(filter_processador_edoc_nfe):
            return super().make_pdf()

        report = self.env.ref('engenere_danfe.report_engenere_danfe')
        pdf_data = report._render_qweb_pdf(self.move_ids.ids)  # Gera o PDF

        self.file_report_id = self.env["ir.attachment"].create(
            {
                "name": self.document_key + ".pdf",
                "res_model": self._name,
                "res_id": self.id,
                "datas": base64.b64encode(pdf_data[0]),
                "mimetype": "application/pdf",
                "type": "binary",
            }
        )
