from odoo import models, fields


class Partner(models.Model):
    _inherit = "res.partner"

    discount_percent_until_due = fields.Float(
        string="Disc. Until Due (%)",
        help="This discount percentage will be used instead of the default for "
        "sales orders, customer invoices. The discount is granted if the invoice "
        "is paid by the due date."
    )
