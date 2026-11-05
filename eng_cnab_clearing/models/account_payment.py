# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _compute_outstanding_account_id(self):
        res = super()._compute_outstanding_account_id()
        for payment in self:
            journal = payment.journal_id
            # Before the cutover date the bank statement does not come into the
            # journal, so nothing would ever close this payment in the clearing
            # account: it stays in the outstanding receipts account of the
            # company, as before the clearing flow
            if (
                payment.payment_type == "inbound"
                and journal.eng_cnab_clearing_enabled
                and journal.eng_bank_cutover_date
                and payment.date
                and payment.date < journal.eng_bank_cutover_date
                and payment.outstanding_account_id
                == journal.eng_cnab_clearing_account_id
            ):
                company = journal.company_id
                payment.outstanding_account_id = (
                    company.account_journal_payment_debit_account_id
                )
        return res

    def _eng_cnab_date_decides_outstanding_account(self):
        """Whether the date of this payment decides its outstanding account.

        Only for an inbound payment in the accounts of the clearing flow: any
        other payment keeps the account it was posted with, which may come from
        an older configuration.
        """
        self.ensure_one()
        journal = self.journal_id
        return (
            self.payment_type == "inbound"
            and journal.eng_cnab_clearing_enabled
            and journal.eng_bank_cutover_date
            and self.outstanding_account_id
            in journal.eng_cnab_clearing_account_id
            | journal.company_id.account_journal_payment_debit_account_id
        )

    def _synchronize_to_moves(self, changed_fields):
        if "date" in changed_fields and not self.env.context.get(
            "skip_account_move_synchronization"
        ):
            # The core does not recompute the account when the date changes, and
            # a draft may have crossed the cutover date
            payments = self.filtered(
                lambda payment: payment._eng_cnab_date_decides_outstanding_account()
            )
            if payments:
                self.env.add_to_compute(
                    self._fields["outstanding_account_id"], payments
                )
        return super()._synchronize_to_moves(changed_fields)
