from odoo import models


class Document(models.Model):
    _inherit = "l10n_br_fiscal.document"

    def _document_comment(self):
        for d in self:
            if d.partner_id:
                d.manual_fiscal_additional_data = d.partner_id.fiscal_comments
            else:
                d.manual_fiscal_additional_data = False
        return super()._document_comment()
