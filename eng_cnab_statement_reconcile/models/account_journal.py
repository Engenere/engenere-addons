# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.exceptions import ValidationError

RECONCILE_CRON_XMLID = "eng_cnab_statement_reconcile.ir_cron_cnab_statement_reconcile"


class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.constrains(
        "eng_cnab_clearing_enabled",
        "eng_cnab_receipt_method_line_id",
        "suspense_account_id",
        "reconcile_mode",
    )
    def _check_eng_cnab_statement_reconcile(self):
        for journal in self.filtered("eng_cnab_clearing_enabled"):
            # The CNAB matching is homologated in the "Edit Move" mode only
            if journal.reconcile_mode != "edit":
                raise ValidationError(
                    _(
                        "The journal %(journal)s has the CNAB clearing flow: its "
                        "bank statement lines must be reconciled in the 'Edit "
                        "Move' mode.",
                        journal=journal.display_name,
                    )
                )
            clearing_account = (
                journal.eng_cnab_receipt_method_line_id.payment_account_id
            )
            if clearing_account and clearing_account == journal.suspense_account_id:
                raise ValidationError(
                    _(
                        "The clearing account %(account)s of the journal "
                        "%(journal)s cannot be its suspense account: the bank "
                        "statement lines reconcile the clearing account.",
                        account=clearing_account.display_name,
                        journal=journal.display_name,
                    )
                )

    def _eng_cnab_get_configuration_error(self):
        """Message of the CNAB clearing constraint the journal fails now, or
        an empty string.

        The constraints run when the journal is saved, but a change made
        elsewhere, such as clearing the outstanding receipts account of its
        CNAB receipt method, can make the configuration invalid later.
        """
        self.ensure_one()
        try:
            self._check_eng_cnab_clearing()
            self._check_eng_cnab_statement_reconcile()
        except ValidationError as error:
            return str(error)
        return ""

    def _move_import(self, parser, file_stream, result_row_list=None, ftype="csv"):
        """Trigger the CNAB matching cron after a CNAB import, never more.

        The matching never runs inside the import: the cron runs after the
        commit, in a transaction of its own, so that a matching problem can
        never roll the import back and the matching never uses the snapshot
        of the import.
        """
        result = super()._move_import(
            parser, file_stream, result_row_list=result_row_list, ftype=ftype
        )
        if result._name == "account.move" and result.filtered(
            lambda move: move.eng_cnab_clearing and move.state == "posted"
        ):
            cron = self.env.ref(RECONCILE_CRON_XMLID, raise_if_not_found=False)
            if cron:
                cron._trigger()
        return result
