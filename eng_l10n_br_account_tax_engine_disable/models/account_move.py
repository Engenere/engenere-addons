# Copyright 2024 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountMove(models.Model):

    _inherit = "account.move"

    @api.model
    def _compute_taxes_mapped(self, base_line):
        balance_taxes_res = super()._compute_taxes_mapped(base_line)

        if self.fiscal_tax_engine_disabled:
            # então força a base manual e os valores dos impostos:
            for tax_item in balance_taxes_res["taxes"]:
                if not tax_item.get("fiscal_tax_id") and not isinstance(
                    tax_item["fiscal_tax_id"], models.NewId
                ):
                    continue
                tax_domain = (
                    self.env["l10n_br_fiscal.tax"]
                    .browse(tax_item["fiscal_tax_id"].origin)
                    .tax_domain
                )
                tax_item["base"] = getattr(base_line, "%s_base" % (tax_domain,))
                tax_item["amount"] = getattr(base_line, "%s_value" % (tax_domain,))
        return balance_taxes_res
