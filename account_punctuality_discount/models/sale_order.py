from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    punctuality_discount = fields.Float(
        string="Punctuality Discount (%)",
        help="The discount is granted if the invoice is paid by the due date.",
    )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        self.punctuality_discount = self.partner_id.punctuality_discount

    def _prepare_invoice(self):
        self.ensure_one()
        val = super()._prepare_invoice()
        if self.punctuality_discount:
            val.update({"invoice_punctuality_discount": self.punctuality_discount})
        return val
