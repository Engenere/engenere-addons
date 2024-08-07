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

    def _update_taxes(self):
        super()._update_taxes()
        if self._is_fiscal_tax_engine_disabled():
            self._update_taxes_when_disabled()

    def _update_taxes_when_disabled(self):
        tax_groups = self.env["l10n_br_fiscal.tax.group"].search([])

        for line in self:
            amount_tax_included = 0
            amount_tax_not_included = 0
            amount_tax_withholding = 0
            for group in tax_groups:
                tax_domain_value = group.tax_domain + "_value"

                if hasattr(line, tax_domain_value):
                    tax_value = getattr(line, tax_domain_value)
                    if group.tax_include:
                        amount_tax_included += tax_value
                    else:
                        amount_tax_not_included += tax_value
                    if group.tax_withholding:
                        amount_tax_withholding += tax_value

            line.amount_tax_included = amount_tax_included
            line.amount_tax_not_included = amount_tax_not_included
            line.amount_tax_withholding = amount_tax_withholding
