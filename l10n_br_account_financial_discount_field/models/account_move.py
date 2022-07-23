from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = "account.move"

    invoice_discount_percent_until_due = fields.Float(
        string="Disc. Until Due (%)",
        help="The discount is granted if the invoice is paid by the due date."
    )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        res = super(AccountMove, self)._onchange_partner_id()
        self.invoice_discount_percent_until_due = self.partner_id.discount_percent_until_due
        return res
