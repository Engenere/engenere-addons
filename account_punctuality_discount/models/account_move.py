from odoo import models, fields, api

from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = "account.move"

    invoice_punctuality_discount = fields.Float(
        string="Punctuality Discount (%)",
        help="The discount is granted if the invoice is paid by the due date."
    )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        res = super(AccountMove, self)._onchange_partner_id()
        self.invoice_punctuality_discount = self.partner_id.punctuality_discount
        return res

    @api.constrains("invoice_punctuality_discount")
    def _check_punctuality_discount(self):
        for inv in self:
            if not 0 <= inv.invoice_punctuality_discount <= 100:
                raise UserError(
                    "Punctuality discount must be between 0% and 100%!"
                )
