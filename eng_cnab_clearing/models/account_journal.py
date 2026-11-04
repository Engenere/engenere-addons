# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import hashlib

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..parser.cnab_clearing_parser import EngClearingCNABParser

# (bank code, import type) of the return layouts homologated for the clearing
# flow. Any other layout needs its own tests first: Itau, for instance,
# returns the received amount net of the tariff.
SUPPORTED_CLEARING_LAYOUTS = {
    ("001", "cnab400"),
    ("085", "cnab240"),
}


class AccountJournal(models.Model):
    _inherit = "account.journal"

    eng_cnab_clearing_enabled = fields.Boolean(
        string="CNAB Clearing Flow",
        help="CNAB return liquidations credited on or after the bank cutover "
        "date are settled on the occurrence date against the clearing account "
        "of the CNAB receipt method, with no bank and no tariff lines. The "
        "bank statement then reconciles the clearing account.",
    )
    eng_bank_cutover_date = fields.Date(
        string="Bank Cutover Date",
        help="Liquidations credited before this date keep the legacy flow, "
        "through the bank account of the journal.",
    )
    eng_cnab_receipt_method_line_id = fields.Many2one(
        comodel_name="account.payment.method.line",
        string="CNAB Receipt Method",
        domain="[('journal_id', '=', id), ('payment_type', '=', 'inbound')]",
        help="Inbound payment method of this journal whose outstanding "
        "receipts account is the clearing account of the bank.",
    )
    eng_cnab_clearing_account_id = fields.Many2one(
        related="eng_cnab_receipt_method_line_id.payment_account_id",
        string="CNAB Clearing Account",
    )

    @api.constrains(
        "eng_cnab_clearing_enabled",
        "eng_bank_cutover_date",
        "eng_cnab_receipt_method_line_id",
        "default_account_id",
        "bank_account_id",
        "import_type",
    )
    def _check_eng_cnab_clearing(self):
        for journal in self.filtered("eng_cnab_clearing_enabled"):
            layout = (journal.bank_account_id.bank_id.code_bc, journal.import_type)
            if layout not in SUPPORTED_CLEARING_LAYOUTS:
                raise ValidationError(
                    _(
                        "The CNAB clearing flow of the journal %(journal)s "
                        "supports only Banco do Brasil (001) CNAB 400 and Ailos "
                        "(085) CNAB 240 return files. Any other layout needs "
                        "its own tests first.",
                        journal=journal.display_name,
                    )
                )
            if not journal.eng_bank_cutover_date:
                raise ValidationError(
                    _(
                        "Set the bank cutover date of the journal %(journal)s to "
                        "enable its CNAB clearing flow.",
                        journal=journal.display_name,
                    )
                )
            method_line = journal.eng_cnab_receipt_method_line_id
            if (
                method_line.journal_id != journal
                or method_line.payment_type != "inbound"
            ):
                raise ValidationError(
                    _(
                        "The CNAB receipt method of the journal %(journal)s must "
                        "be one of its inbound payment methods.",
                        journal=journal.display_name,
                    )
                )
            clearing_account = method_line.payment_account_id
            # No fallback to the outstanding receipts account of the company
            if not clearing_account:
                raise ValidationError(
                    _(
                        "The CNAB receipt method %(method)s of the journal "
                        "%(journal)s must have its own outstanding receipts "
                        "account: the default account of the company is not "
                        "used as a fallback.",
                        method=method_line.display_name,
                        journal=journal.display_name,
                    )
                )
            if clearing_account == journal.default_account_id:
                raise ValidationError(
                    _(
                        "The clearing account %(account)s of the journal "
                        "%(journal)s cannot be its bank account.",
                        account=clearing_account.display_name,
                        journal=journal.display_name,
                    )
                )
            if clearing_account.company_id != journal.company_id:
                raise ValidationError(
                    _(
                        "The clearing account %(account)s must belong to the "
                        "company of the journal %(journal)s.",
                        account=clearing_account.display_name,
                        journal=journal.display_name,
                    )
                )
            if not clearing_account.reconcile:
                raise ValidationError(
                    _(
                        "The clearing account %(account)s of the journal "
                        "%(journal)s must allow reconciliation.",
                        account=clearing_account.display_name,
                        journal=journal.display_name,
                    )
                )

    def multi_move_import(self, file_stream, ftype="csv"):
        """Import a CNAB return file in a journal with the clearing flow.

        Reimplemented, not extended: the inherited method gets its parser
        from new_move_parser(), which returns CNABFileParser itself. Journals
        without the clearing flow keep the original import.

        The import is atomic: any error rolls back the log, the attachment,
        the events, the entries and the CNAB states. There is no commit here.
        """
        if not self.eng_cnab_clearing_enabled:
            return super().multi_move_import(file_stream, ftype=ftype)
        # The configuration may have changed since it was saved (on the receipt
        # method, for instance): never import against a wrong account
        self._check_eng_cnab_clearing()
        file_hash = hashlib.sha256(base64.b64decode(file_stream)).hexdigest()
        self._eng_check_cnab_file_not_imported(file_hash)
        parser = EngClearingCNABParser(self, file_hash=file_hash)
        moves = self.env["account.move"]
        cnab_logs = self.env["l10n_br_cnab.return.log"]
        for result_row_list in parser.parse(file_stream):
            result = self._move_import(
                parser,
                file_stream,
                result_row_list=result_row_list,
                ftype=ftype,
            )
            if result._name == "account.move":
                moves |= result
            else:
                cnab_logs |= result
        return moves or cnab_logs

    def _eng_check_cnab_file_not_imported(self, file_hash):
        imported_log = self.env["l10n_br_cnab.return.log"].search(
            [
                ("eng_company_id", "=", self.company_id.id),
                ("eng_journal_id", "=", self.id),
                ("eng_file_hash", "=", file_hash),
            ],
            limit=1,
        )
        if imported_log:
            raise UserError(
                _(
                    "The CNAB return file %(file_name)s was already imported in "
                    "the journal %(journal)s (return log %(log)s). Importing it "
                    "again would duplicate its entries.",
                    file_name=self.env.context.get("file_name") or "",
                    journal=self.display_name,
                    log=imported_log.display_name,
                )
            )

    def _create_cnab_return_log(self, parser):
        cnab_return_log, file_name = super()._create_cnab_return_log(parser)
        if isinstance(parser, EngClearingCNABParser):
            cnab_return_log.write(
                {"eng_journal_id": self.id, "eng_file_hash": parser.file_hash}
            )
            parser.eng_set_return_log(cnab_return_log)
        return cnab_return_log, file_name

    def prepare_move_vals(self, result_row_list, parser):
        vals = super().prepare_move_vals(result_row_list, parser)
        if isinstance(parser, EngClearingCNABParser):
            vals.update(parser.eng_get_move_vals(result_row_list))
        return vals

    def _get_counterpart_vals_list(self, parser, move, line_vals_list):
        # A clearing entry has no counterpart in the bank account: the parser
        # builds its clearing row, due on the credit date (no "today" fallback)
        if move.eng_cnab_clearing:
            return []
        return super()._get_counterpart_vals_list(parser, move, line_vals_list)

    def _get_moves(self, parser, result_row_list):
        moves = super()._get_moves(parser, result_row_list)
        for move in moves.filtered("eng_cnab_return_event_id"):
            move.eng_cnab_return_event_id.eng_move_id = move
        return moves
