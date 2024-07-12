# Copyright 2024 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class FiscalDocumentLineMixinMethods(models.AbstractModel):

    _inherit = "l10n_br_fiscal.document.line.mixin.methods"

    def _remove_all_fiscal_tax_ids(self):
        if self._is_fiscal_tax_engine_disabled():
            return
        super()._remove_all_fiscal_tax_ids()

    def _apply_tax_fields(self, compute_result):
        if self._is_fiscal_tax_engine_disabled():
            return
        super()._apply_tax_fields(compute_result)

    def _process_fiscal_mapping(self, mapping_result):
        if self._is_fiscal_tax_engine_disabled():
            return
        super()._process_fiscal_mapping(mapping_result)

    def _is_fiscal_tax_engine_disabled(self):
        # When the mixin is used for instance
        # in a PO line or SO line, there is no document_id
        # and we consider the document is not fiscal_tax_engine_disabled
        return (
            hasattr(self, "document_id") and self.document_id.fiscal_tax_engine_disabled
        )
