# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest import mock

from psycopg2.errors import SerializationFailure

from odoo import Command

from odoo.addons.eng_cnab_clearing.tests.common import (
    CREDIT_DATE,
    CUTOVER_DATE,
    CnabClearingCommon,
)
from odoo.addons.eng_cnab_statement_reconcile.models.account_reconcile_model import (
    AccountReconcileModel,
)

# Synthetic labels of the bank statement lines, with no numeric token that
# the generic invoice matching could look for
COLLECTION_LABEL = "COLLECTION CREDIT"
OWN_BANK_LABEL = "COLLECTION OWN CREDIT"
OTHER_BANKS_LABEL = "COLLECTION OTHER CREDIT"
TRANSFER_LABEL = "TRANSFER RECEIVED"


class CnabStatementReconcileCommon(CnabClearingCommon):
    """The CNAB clearing setup plus bank statement lines and matching rules.

    The CNAB returns go through the real import, with only the BRCobranca
    API simulated; the statement lines are created as the statement import
    creates them, so that the automatic reconciliation of
    account_reconcile_oca runs for real.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_suspense = cls._create_account(
            "ENGSR.SUS", "Synthetic Bank Suspense", "asset_current", reconcile=True
        )
        (cls.journal_bb | cls.journal_ailos).write(
            {"suspense_account_id": cls.account_suspense.id}
        )
        cls.rule_bb = cls._create_cnab_rule(
            "Synthetic B collection", cls.journal_bb, "match_regex", "^COLLECTION"
        )
        cls.rule_ailos_own = cls._create_cnab_rule(
            "Synthetic A collection, own bank",
            cls.journal_ailos,
            "contains",
            "COLLECTION OWN",
            bank_filter="own",
        )
        cls.rule_ailos_other = cls._create_cnab_rule(
            "Synthetic A collection, other banks",
            cls.journal_ailos,
            "contains",
            "COLLECTION OTHER",
            bank_filter="other",
        )
        cls.cron = cls.env.ref(
            "eng_cnab_statement_reconcile.ir_cron_cnab_statement_reconcile"
        )

    @classmethod
    def _create_cnab_rule(
        cls, name, journal, match_label, label_param, bank_filter="any"
    ):
        return cls.env["account.reconcile.model"].create(
            {
                "name": name,
                "company_id": journal.company_id.id,
                "rule_type": "invoice_matching",
                "auto_reconcile": True,
                "match_nature": "amount_received",
                "match_journal_ids": [Command.set(journal.ids)],
                "match_label": match_label,
                "match_label_param": label_param,
                "eng_cnab_clearing_match": True,
                "eng_receiving_bank_filter": bank_filter,
            }
        )

    def _create_writeoff_rule(self, name, label_param, match_nature, account):
        return self.env["account.reconcile.model"].create(
            {
                "name": name,
                "rule_type": "writeoff_suggestion",
                "auto_reconcile": True,
                "match_nature": match_nature,
                "match_journal_ids": [Command.set(self.journal_bb.ids)],
                "match_label": "contains",
                "match_label_param": label_param,
                "line_ids": [Command.create({"account_id": account.id})],
            }
        )

    def _create_generic_rule(self, auto_reconcile=True):
        """Invoice matching rule by amount, as a database usually has one."""
        return self.env["account.reconcile.model"].create(
            {
                "name": "Synthetic generic matching",
                "rule_type": "invoice_matching",
                "auto_reconcile": auto_reconcile,
                "match_text_location_label": False,
                "past_months_limit": 0,
            }
        )

    @staticmethod
    def _without_clearing_exclusion():
        """The rule domain as the core has it: what the exclusion prevents."""
        exclusion = ("eng_cnab_clearing", "=", False)
        original = AccountReconcileModel._get_invoice_matching_amls_domain

        def core_domain(rule, st_line, partner):
            return [
                term for term in original(rule, st_line, partner) if term != exclusion
            ]

        return mock.patch.object(
            AccountReconcileModel, "_get_invoice_matching_amls_domain", core_domain
        )

    def _create_statement_line(self, journal, amount, label, line_date=CREDIT_DATE):
        """Create the statement line as the statement import does."""
        return (
            self.env["account.bank.statement.line"]
            .with_company(journal.company_id)
            .create(
                {
                    "journal_id": journal.id,
                    "date": line_date,
                    "amount": amount,
                    "payment_ref": label,
                }
            )
        )

    def _receive_manual_payment(self, amount):
        """Post a manual customer receipt of the bank B journal, which goes to
        its clearing account as well; return its line there."""
        manual_method_line = self.journal_bb.inbound_payment_method_line_ids.filtered(
            lambda method_line: method_line.code == "manual"
        )
        manual_method_line.payment_account_id = self.account_clearing_bb
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "amount": amount,
                "date": CREDIT_DATE,
                "journal_id": self.journal_bb.id,
                "payment_method_line_id": manual_method_line.id,
            }
        )
        payment.action_post()
        return payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.account_clearing_bb
        )

    @staticmethod
    def _reconcile_by_hand(st_line, move_line):
        """Reconcile part of the statement line with move_line, as by hand,
        leaving the rest of its amount in the suspense account."""
        liquidity_lines, _suspense_lines, _other_lines = st_line._seek_for_lines()
        data = st_line._get_reconcile_line(liquidity_lines, "liquidity", move=True)[1]
        data += st_line._get_reconcile_line(
            move_line, "other", is_counterpart=True, move=True
        )[1]
        reconcile_data = st_line._recompute_suspense_line(data, 1, False)
        st_line._reconcile_bank_line_edit(
            st_line._prepare_reconcile_line_data(reconcile_data["data"])
        )

    @staticmethod
    def _clearing_lines(moves):
        return moves.line_ids.filtered("eng_cnab_clearing")

    @staticmethod
    def _counterpart_moves(clearing_lines):
        """Entries whose lines reconciled the clearing lines."""
        return clearing_lines.matched_credit_ids.credit_move_id.move_id

    def _run_cron_method(self):
        self.env["account.bank.statement.line"]._eng_cron_cnab_reconcile()

    def _serialization_failure_on_lock(self):
        """Make the lock of the candidate clearing lines fail, as it does
        when a concurrent transaction changed them after the snapshot."""
        original_execute = self.env.cr.execute

        def execute(query, params=None, log_exceptions=True):
            if "account_move_line" in str(query) and "FOR UPDATE" in str(query):
                raise SerializationFailure(
                    "could not serialize access due to concurrent update"
                )
            return original_execute(query, params, log_exceptions)

        return mock.patch.object(self.env.cr, "execute", side_effect=execute)

    def _create_other_company_journal(self):
        """Bank B journal with the CNAB clearing flow in another company,
        with its own CNAB matching rule."""
        company = self.env["res.company"].create(
            {"name": "Synthetic Other Clearing Company"}
        )
        self.env.user.write({"company_ids": [Command.link(company.id)]})
        bank_account, clearing_account, suspense_account = (
            self.env["account.account"].create(
                {
                    "code": code,
                    "name": name,
                    "account_type": account_type,
                    "reconcile": reconcile,
                    "company_id": company.id,
                }
            )
            for code, name, account_type, reconcile in (
                ("ENGSR.BKO", "Synthetic Other Bank", "asset_cash", False),
                ("ENGSR.CLO", "Synthetic Other Clearing", "asset_current", True),
                ("ENGSR.SUO", "Synthetic Other Suspense", "asset_current", True),
            )
        )
        partner_bank = self.env["res.partner.bank"].create(
            {
                "acc_number": "90003",
                "acc_number_dig": "0",
                "bra_number": "1234",
                "bra_number_dig": "0",
                "bank_id": self.env.ref("l10n_br_base.res_bank_001").id,
                "partner_id": company.partner_id.id,
            }
        )
        journal = (
            self.env["account.journal"]
            .with_company(company)
            .create(
                {
                    "name": "Synthetic Other Company Journal",
                    "code": "ECOTH",
                    "type": "bank",
                    "company_id": company.id,
                    "default_account_id": bank_account.id,
                    "suspense_account_id": suspense_account.id,
                    "bank_account_id": partner_bank.id,
                    "used_for_import": True,
                    "import_type": "cnab400",
                    "return_auto_reconcile": True,
                }
            )
        )
        receipt_method_line = journal.inbound_payment_method_line_ids.filtered(
            lambda method_line: method_line.payment_method_id == self.method_cnab400
        )
        receipt_method_line.payment_account_id = clearing_account
        journal.write(
            {
                "eng_cnab_clearing_enabled": True,
                "eng_bank_cutover_date": CUTOVER_DATE,
                "eng_cnab_receipt_method_line_id": receipt_method_line.id,
            }
        )
        self._create_cnab_rule(
            "Synthetic other company collection", journal, "match_regex", "^COLLECTION"
        )
        return journal
