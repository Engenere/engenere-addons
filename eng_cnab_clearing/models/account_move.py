# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date


class AccountMove(models.Model):
    _inherit = "account.move"

    eng_cnab_clearing = fields.Boolean(
        string="CNAB Clearing Entry",
        copy=False,
        readonly=True,
        help="Settlement of a CNAB return liquidation by the clearing flow: "
        "posted on the occurrence date, against the clearing account.",
    )
    eng_cnab_return_event_id = fields.Many2one(
        comodel_name="l10n_br_cnab.return.event",
        string="CNAB Return Event",
        copy=False,
        readonly=True,
    )
    eng_cnab_occurrence_date = fields.Date(
        string="CNAB Occurrence Date",
        copy=False,
        readonly=True,
        help="Date the customer paid, which the clearing entry must keep as "
        "its accounting date.",
    )
    eng_cnab_credit_date = fields.Date(
        string="CNAB Credit Date",
        copy=False,
        readonly=True,
        help="Date the bank credits the payment, due date of the clearing line.",
    )

    def _post(self, soft=True):
        clearing_moves = self.filtered("eng_cnab_clearing")
        clearing_moves._eng_check_cnab_clearing_lock_dates()
        posted = super()._post(soft=soft)
        clearing_moves._eng_check_cnab_clearing_dates()
        return posted

    def _eng_check_cnab_clearing_lock_dates(self):
        """Refuse what the core _post() would do silently.

        Same evaluation as the core: on a lock date, _post() replaces the
        accounting date of the entry, so a clearing entry would no longer be
        on the occurrence date.
        """
        for move in self:
            affects_tax_report = move._affect_tax_report()
            lock_dates = move._get_violated_lock_dates(move.date, affects_tax_report)
            if lock_dates:
                lock_date, lock_type = lock_dates[-1]
                accounting_date = move._get_accounting_date(
                    move.invoice_date or move.date, affects_tax_report
                )
                raise UserError(
                    _(
                        "The CNAB clearing entry %(entry)s cannot be posted: its "
                        "occurrence date %(occurrence_date)s is not after the "
                        "%(lock_type)s lock date %(lock_date)s, and posting would "
                        "move it to %(accounting_date)s. Review the lock date or "
                        "the return file with the accounting team.",
                        entry=move.display_name,
                        occurrence_date=format_date(self.env, move.date),
                        lock_type=lock_type,
                        lock_date=format_date(self.env, lock_date),
                        accounting_date=format_date(self.env, accounting_date),
                    )
                )

    def _eng_check_cnab_clearing_dates(self):
        for move in self:
            if move.date != move.eng_cnab_occurrence_date:
                raise UserError(
                    _(
                        "The CNAB clearing entry %(entry)s was posted on %(date)s "
                        "instead of its occurrence date %(occurrence_date)s, so "
                        "the posting was cancelled. Check the modules that "
                        "change the accounting date when posting.",
                        entry=move.display_name,
                        date=format_date(self.env, move.date),
                        occurrence_date=format_date(
                            self.env, move.eng_cnab_occurrence_date
                        ),
                    )
                )
