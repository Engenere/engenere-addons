# Copyright 2025 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models


class NFeLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    def _export_fields_nfe_40_prod(self, xsd_fields, class_obj, export_dict):
        super()._export_fields_nfe_40_prod(xsd_fields, class_obj, export_dict)
        if self.env.company.nfe_product_name:
            nfe40_xProd = self.name or ""
            export_dict["xProd"] = nfe40_xProd[:120].replace("\n", " ").strip()
