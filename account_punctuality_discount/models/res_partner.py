from odoo import models, fields


class Partner(models.Model):
    _inherit = "res.partner"

    punctuality_discount = fields.Float(
        string="Punctuality Discount (%)",
        help="This discount percentage will be used instead of the default for "
        "sales orders, customer invoices. The discount is granted if the invoice "
        "is paid by the due date."
    )
