from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    discount_percent_until_due = fields.Float(
        string="Disc. Until Due (%)",
        help="The discount is granted if the invoice is paid by the due date."
    )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        res = super(SaleOrder, self)._onchange_partner_id()
        self.discount_percent_until_due = self.partner_id.discount_percent_until_due
        return res

    def _create_invoices(self, grouped=False, final=False):
        inv_ids = super()._create_invoices(grouped=grouped, final=final)
        for invoice_id in inv_ids:
            invoice_id.invoice_discount_percent_until_due = self.discount_percent_until_due
        return inv_ids
