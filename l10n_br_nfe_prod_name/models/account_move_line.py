# Copyright 2025 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.onchange("product_id")
    def _onchange_product_id_fiscal(self):
        res = super()._onchange_product_id_fiscal()
        if self.product_id and self.env.company.nfe_product_name:
            self.name = self.product_id.name
        return res
