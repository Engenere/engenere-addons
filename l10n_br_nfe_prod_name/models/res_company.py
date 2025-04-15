from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    nfe_product_name = fields.Boolean(
        string="Product Name",
        help="If enabled, the system will use the product name in the "
        "xProd field of the NF-e instead of the document line description.",
    )
