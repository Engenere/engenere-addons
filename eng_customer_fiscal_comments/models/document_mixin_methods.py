from odoo import models


class DocumentMixinMethods(models.AbstractModel):
    _inherit = "l10n_br_fiscal.document.mixin.methods"

    def _document_comment(self):
        for d in self:
            if d.partner_id:
                d.manual_fiscal_additional_data = d.partner_id.fiscal_comments
                super()._document_comment()
            else:
                d.manual_fiscal_additional_data = False
