# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date, timedelta
from unittest import mock

from psycopg2.errors import SerializationFailure

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tools.misc import formatLang

from odoo.addons.eng_cnab_clearing.tests.common import (
    CREDIT_DATE,
    CUTOVER_DATE,
    OTHER_AILOS_CREDIT_UNION,
)

from .common import (
    COLLECTION_LABEL,
    OTHER_BANKS_LABEL,
    OWN_BANK_LABEL,
    TRANSFER_LABEL,
    CnabStatementReconcileCommon,
)

SYNTHETIC_BUSINESS_ERROR = "Synthetic business error"


@tagged("post_install", "-at_install")
class TestCnabStatementReconcile(CnabStatementReconcileCommon):
    # Plan, test 19
    def test_statement_credit_reconciles_the_whole_group_of_its_date(self):
        moves = self._import(
            self.journal_bb,
            [
                self._bb_record(self.installment_bb, received=40.0),
                self._bb_record(self.installment_bb, received=60.0),
            ],
        )
        clearing_lines = self._clearing_lines(moves)
        self.assertEqual(clearing_lines.mapped("date_maturity"), [CREDIT_DATE] * 2)

        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)

        self.assertTrue(st_line.is_reconciled)
        self.assertEqual(clearing_lines.mapped("amount_residual"), [0.0, 0.0])
        self.assertTrue(all(clearing_lines.mapped("reconciled")))
        self.assertEqual(self._counterpart_moves(clearing_lines), st_line.move_id)
        # The statement brings the bank line; the clearing account nets out
        self.assertEqual(
            self._amounts_by_account(st_line.move_id),
            {
                self.account_bank_bb: (100.0, 0.0),
                self.account_clearing_bb: (0.0, 100.0),
            },
        )
        self.assertEqual(st_line.eng_cnab_reconcile_status, "reconciled")

    # Plan, test 20
    def test_group_one_cent_short_reconciles_nothing_and_shows_the_difference(self):
        # Neither the tolerance nor the counterpart lines of the rule are used
        self.rule_bb.write(
            {
                "payment_tolerance_type": "fixed_amount",
                "payment_tolerance_param": 1.0,
                "line_ids": [Command.create({"account_id": self.account_tariff.id})],
            }
        )
        moves = self._import(
            self.journal_bb,
            [
                self._bb_record(self.installment_bb, received=40.0),
                self._bb_record(self.installment_bb, received=59.99),
            ],
        )
        clearing_lines = self._clearing_lines(moves)

        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)

        self.assertFalse(st_line.is_reconciled)
        self.assertEqual(
            sorted(clearing_lines.mapped("amount_residual")), [40.0, 59.99]
        )
        self.assertEqual(st_line.eng_cnab_reconcile_status, "difference")
        self.assertEqual(st_line.eng_cnab_reconcile_difference, 0.01)
        self.assertIn(
            "Amount difference of "
            + formatLang(self.env, 0.01, currency_obj=st_line.currency_id),
            st_line.eng_cnab_reconcile_message,
        )
        # No write-off: the statement entry keeps its bank and suspense lines
        self.assertEqual(
            st_line.move_id.line_ids.account_id,
            self.account_bank_bb | self.account_suspense,
        )

    # Plan, test 21
    def test_collection_credit_without_exact_group_leaves_manual_payment_open(self):
        generic_rule = self._create_generic_rule()
        payment_line = self._receive_manual_payment(100.0)
        moves = self._import(
            self.journal_bb,
            [
                self._bb_record(self.installment_bb, received=40.0),
                self._bb_record(self.installment_bb, received=50.0),
            ],
        )
        other_installments = (
            self.installment_bb_2 | self.installment_ailos | self.installment_ailos_2
        )

        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)

        # Without the exclusive routing, the generic rule would propose the
        # payment, among the open items of the same amount
        self.assertIn(
            payment_line,
            generic_rule._get_invoice_matching_amls_candidates(
                st_line, self.env["res.partner"]
            )["amls"],
        )
        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(payment_line.reconciled)
        self.assertEqual(payment_line.amount_residual, 100.0)
        self.assertEqual(other_installments.mapped("amount_residual"), [100.0] * 3)
        self.assertFalse(any(self._clearing_lines(moves).mapped("reconciled")))
        self.assertEqual(st_line.eng_cnab_reconcile_status, "difference")
        self.assertEqual(st_line.eng_cnab_reconcile_difference, 10.0)

    # Plan, test 22
    def test_same_amount_in_another_journal_company_or_date_is_not_consumed(self):
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        clearing_line = self._clearing_lines(moves)
        other_company_journal = self._create_other_company_journal()

        other_st_lines = (
            self._create_statement_line(self.journal_ailos, 100.0, OWN_BANK_LABEL)
            | self._create_statement_line(
                other_company_journal, 100.0, COLLECTION_LABEL
            )
            | self._create_statement_line(
                self.journal_bb,
                100.0,
                COLLECTION_LABEL,
                line_date=CREDIT_DATE + timedelta(days=1),
            )
        )
        self._run_cron_method()

        self.assertFalse(any(other_st_lines.mapped("is_reconciled")))
        self.assertEqual(
            other_st_lines.mapped("eng_cnab_reconcile_status"), ["awaiting"] * 3
        )
        self.assertFalse(clearing_line.reconciled)
        # The statement line of its own journal and date takes it
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        self.assertTrue(st_line.is_reconciled)
        self.assertTrue(clearing_line.reconciled)
        self.assertEqual(self._counterpart_moves(clearing_line), st_line.move_id)

    # Plan, test 23
    def test_receiving_bank_filter_splits_the_credits_of_the_same_day(self):
        moves = self._import(
            self.journal_ailos,
            [
                self._ailos_record(
                    self.installment_ailos, received=30.0, banco_recebedor="085"
                ),
                self._ailos_record(
                    self.installment_ailos_2, received=70.0, banco_recebedor="237"
                ),
            ],
        )
        clearing_lines = self._clearing_lines(moves)
        own_bank_line = clearing_lines.filtered(
            lambda line: line.eng_cnab_receiving_bank_class == "own"
        )
        other_banks_line = clearing_lines - own_bank_line
        self.assertEqual((own_bank_line.debit, other_banks_line.debit), (30.0, 70.0))
        self.assertEqual(other_banks_line.eng_cnab_receiving_bank_class, "other")

        own_bank_st_line = self._create_statement_line(
            self.journal_ailos, 30.0, OWN_BANK_LABEL
        )
        other_banks_st_line = self._create_statement_line(
            self.journal_ailos, 70.0, OTHER_BANKS_LABEL
        )

        self.assertTrue(own_bank_st_line.is_reconciled)
        self.assertTrue(other_banks_st_line.is_reconciled)
        self.assertEqual(
            self._counterpart_moves(own_bank_line), own_bank_st_line.move_id
        )
        self.assertEqual(
            self._counterpart_moves(other_banks_line), other_banks_st_line.move_id
        )

    def test_title_paid_at_another_credit_union_is_credited_with_the_other_banks(self):
        moves = self._import(
            self.journal_ailos,
            [
                self._ailos_record(self.installment_ailos, received=30.0),
                self._ailos_record(
                    self.installment_ailos_2,
                    received=70.0,
                    agencia_recebedora_com_dv=OTHER_AILOS_CREDIT_UNION,
                ),
            ],
        )
        clearing_lines = self._clearing_lines(moves)
        own_bank_line = clearing_lines.filtered(lambda line: line.debit == 30.0)
        other_banks_line = clearing_lines - own_bank_line

        own_bank_st_line = self._create_statement_line(
            self.journal_ailos, 30.0, OWN_BANK_LABEL
        )
        other_banks_st_line = self._create_statement_line(
            self.journal_ailos, 70.0, OTHER_BANKS_LABEL
        )

        self.assertTrue(own_bank_st_line.is_reconciled)
        self.assertTrue(other_banks_st_line.is_reconciled)
        self.assertEqual(
            self._counterpart_moves(own_bank_line), own_bank_st_line.move_id
        )
        self.assertEqual(
            self._counterpart_moves(other_banks_line), other_banks_st_line.move_id
        )

    def test_cron_writes_the_reason_in_the_language_of_the_company(self):
        # The user of the scheduled action has no say: the reason stays on the
        # line as text, for the users of the company
        self.env["res.lang"]._activate_lang("pt_BR")
        self.company.partner_id.lang = "pt_BR"
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "awaiting")

        self.env["account.bank.statement.line"]._eng_cron_cnab_reconcile()

        self.assertTrue(
            st_line.eng_cnab_reconcile_message.startswith("Aguardando o retorno CNAB"),
            st_line.eng_cnab_reconcile_message,
        )

    def test_cron_writes_the_error_in_the_language_of_the_company(self):
        self.env["res.lang"]._activate_lang("pt_BR")
        self.company.partner_id.lang = "pt_BR"
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)

        with mock.patch.object(
            type(st_line),
            "_eng_cnab_try_reconcile",
            side_effect=UserError(SYNTHETIC_BUSINESS_ERROR),
        ):
            self.env["account.bank.statement.line"]._eng_cron_cnab_reconcile()

        self.assertEqual(st_line.eng_cnab_reconcile_status, "error")
        self.assertTrue(
            st_line.eng_cnab_reconcile_message.startswith("Erro:"),
            st_line.eng_cnab_reconcile_message,
        )
        self.assertIn(SYNTHETIC_BUSINESS_ERROR, st_line.eng_cnab_reconcile_message)

    # Plan, test 24
    def test_statement_before_cnab_waits_then_the_cron_reconciles_it(self):
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        self.assertFalse(st_line.is_reconciled)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "awaiting")
        self.assertTrue(
            st_line.eng_cnab_reconcile_message.startswith("Awaiting the CNAB return")
        )

        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        self.assertFalse(st_line.is_reconciled)
        self._run_cron_method()

        self.assertTrue(st_line.is_reconciled)
        self.assertTrue(self._clearing_lines(moves).reconciled)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "reconciled")
        self.assertTrue(
            st_line.eng_cnab_reconcile_message.startswith(
                "Reconciled with the whole group"
            )
        )
        self.assertTrue(st_line.eng_cnab_reconcile_message.endswith(": 1 line(s)."))

    # Plan, test 25
    def test_cnab_before_statement_reconciles_when_the_line_is_created(self):
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        clearing_line = self._clearing_lines(moves)

        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)

        # Reconciled by the creation itself, with no cron run
        self.assertTrue(st_line.is_reconciled)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "reconciled")
        self.assertEqual(self._counterpart_moves(clearing_line), st_line.move_id)
        self.assertEqual(
            self._amounts_by_account(st_line.move_id),
            {
                self.account_bank_bb: (100.0, 0.0),
                self.account_clearing_bb: (0.0, 100.0),
            },
        )

    # Plan, test 26
    def test_return_in_two_parts_reconciles_when_the_group_is_complete(self):
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        first_moves = self._import(
            self.journal_bb, [self._bb_record(self.installment_bb, received=40.0)]
        )
        self._run_cron_method()

        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(self._clearing_lines(first_moves).reconciled)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "difference")
        self.assertEqual(st_line.eng_cnab_reconcile_difference, 60.0)

        second_moves = self._import(
            self.journal_bb, [self._bb_record(self.installment_bb, received=60.0)]
        )
        self._run_cron_method()

        clearing_lines = self._clearing_lines(first_moves | second_moves)
        self.assertTrue(st_line.is_reconciled)
        self.assertTrue(all(clearing_lines.mapped("reconciled")))
        self.assertEqual(self._counterpart_moves(clearing_lines), st_line.move_id)
        self.assertEqual(st_line.eng_cnab_reconcile_difference, 0.0)

    # Plan, test 27
    def test_matching_twice_reconciles_only_once(self):
        moves = self._import(
            self.journal_bb,
            [
                self._bb_record(self.installment_bb, received=40.0),
                self._bb_record(self.installment_bb, received=60.0),
            ],
        )
        clearing_lines = self._clearing_lines(moves)
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        partials = clearing_lines.matched_credit_ids
        statement_entry_lines = st_line.move_id.line_ids

        st_line._eng_cnab_try_reconcile()
        st_line.action_eng_cnab_retry()
        self._run_cron_method()

        self.assertEqual(len(partials), 2)
        self.assertEqual(clearing_lines.matched_credit_ids, partials)
        self.assertEqual(st_line.move_id.line_ids, statement_entry_lines)
        self.assertFalse(
            self.rule_bb._apply_rules(st_line, self.env["res.partner"]),
            "A reconciled statement line gets no new proposal",
        )
        self.assertEqual(st_line.eng_cnab_reconcile_status, "reconciled")

    # Plan, test 32
    def test_user_of_another_company_neither_sees_nor_reconciles(self):
        other_company_journal = self._create_other_company_journal()
        other_company = other_company_journal.company_id
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        clearing_line = self._clearing_lines(moves)
        other_company_st_line = self._create_statement_line(
            other_company_journal, 100.0, COLLECTION_LABEL
        )
        other_company_user = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Synthetic Other Company Accountant",
                    "login": "synthetic.other.company.accountant",
                    "company_id": other_company.id,
                    "company_ids": [Command.set(other_company.ids)],
                    "groups_id": [
                        Command.set(
                            [
                                self.env.ref("base.group_user").id,
                                self.env.ref("account.group_account_user").id,
                            ]
                        )
                    ],
                }
            )
        )
        other_company_env = self.env(
            user=other_company_user,
            context={
                "allowed_company_ids": other_company.ids,
                "tracking_disable": True,
            },
        )

        visible_st_lines = other_company_env["account.bank.statement.line"].search(
            [("id", "in", (st_line | other_company_st_line).ids)]
        )
        self.assertEqual(visible_st_lines, other_company_st_line)
        self.assertFalse(
            other_company_env["account.move.line"].search(
                [("id", "=", clearing_line.id)]
            )
        )
        with self.assertRaises(AccessError):
            st_line.with_env(other_company_env).action_eng_cnab_retry()
        other_company_st_line.with_env(other_company_env).action_eng_cnab_retry()

        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(clearing_line.reconciled)
        self.assertFalse(other_company_st_line.is_reconciled)
        self.assertEqual(other_company_st_line.eng_cnab_reconcile_status, "awaiting")

    # Plan, test 33
    def test_statement_line_reconciled_in_part_by_hand_is_left_out(self):
        payment_line = self._receive_manual_payment(40.0)
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        self._reconcile_by_hand(st_line, payment_line)
        self.assertTrue(payment_line.reconciled)
        self.assertFalse(st_line.is_reconciled)
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        clearing_line = self._clearing_lines(moves)

        self._run_cron_method()

        self.assertFalse(clearing_line.reconciled)
        self.assertEqual(clearing_line.amount_residual, 100.0)
        self.assertFalse(st_line.is_reconciled)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "partial")
        self.assertTrue(
            st_line.eng_cnab_reconcile_message.startswith("Partially reconciled")
        )

    # Plan, test 34
    def test_concurrency_error_on_the_lock_raises_and_records_nothing(self):
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        reason_before = (
            st_line.eng_cnab_reconcile_status,
            st_line.eng_cnab_reconcile_message,
        )

        # The rollback of assertRaises would hide a reason written before the
        # error: spy on the only writer of the reason as well
        with mock.patch.object(
            type(st_line), "_eng_cnab_write_outcome", autospec=True
        ) as write_outcome, self._serialization_failure_on_lock(), self.assertRaises(
            SerializationFailure
        ):
            st_line.action_eng_cnab_retry()

        write_outcome.assert_not_called()
        self.assertEqual(
            (st_line.eng_cnab_reconcile_status, st_line.eng_cnab_reconcile_message),
            reason_before,
        )
        self.assertEqual(reason_before[0], "awaiting")
        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(self._clearing_lines(moves).reconciled)

    # Plan, test 35
    def test_candidate_clearing_lines_are_locked_in_id_order(self):
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        moves = self._import(
            self.journal_bb,
            [
                self._bb_record(self.installment_bb, received=40.0),
                self._bb_record(self.installment_bb, received=60.0),
            ],
        )
        clearing_lines = self._clearing_lines(moves)

        with mock.patch.object(
            self.env.cr, "execute", wraps=self.env.cr.execute
        ) as execute_spy:
            st_line.action_eng_cnab_retry()

        lock_calls = [
            call.args
            for call in execute_spy.call_args_list
            if call.args
            and "FOR UPDATE" in str(call.args[0])
            and (
                "account_move_line" in str(call.args[0])
                or "account_bank_statement_line" in str(call.args[0])
            )
        ]
        self.assertEqual(
            [query for query, _params in lock_calls],
            [
                "SELECT id FROM account_bank_statement_line WHERE id IN %s "
                "FOR UPDATE",
                "SELECT id FROM account_move_line WHERE id IN %s "
                "ORDER BY id FOR UPDATE",
            ],
        )
        self.assertEqual(lock_calls[0][1], [(st_line.id,)])
        self.assertEqual(set(lock_calls[1][1][0]), set(clearing_lines.ids))
        self.assertTrue(st_line.is_reconciled)

    # Plan, test 36
    def test_open_statement_line_residual_has_the_suspense_sign(self):
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        self.assertEqual(st_line.amount, 100.0)
        self.assertEqual(st_line.amount_residual, -100.0)
        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(st_line._seek_for_lines()[2])
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])

        st_line.action_eng_cnab_retry()

        self.assertTrue(st_line.is_reconciled)
        self.assertTrue(self._clearing_lines(moves).reconciled)

    # Plan, test 37
    def test_cnab_import_only_triggers_the_cron_that_reconciles_later(self):
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        triggers_before = self.env["ir.cron.trigger"].search(
            [("cron_id", "=", self.cron.id)]
        )

        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])

        clearing_line = self._clearing_lines(moves)
        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(clearing_line.reconciled)
        new_triggers = (
            self.env["ir.cron.trigger"].search([("cron_id", "=", self.cron.id)])
            - triggers_before
        )
        self.assertEqual(len(new_triggers), 1)
        self.assertLessEqual(new_triggers.call_at, fields.Datetime.now())

        self.cron.method_direct_trigger()

        self.assertTrue(st_line.is_reconciled)
        self.assertTrue(clearing_line.reconciled)

    # Plan, test 38
    def test_failed_cron_run_is_retried_by_the_next_one(self):
        self.assertTrue(self.cron.active)
        self.assertEqual(self.cron.numbercall, -1)
        self.assertEqual(
            (self.cron.interval_number, self.cron.interval_type), (30, "minutes")
        )
        self.assertFalse(self.cron.doall)
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])

        with self._serialization_failure_on_lock(), self.assertRaises(
            SerializationFailure
        ):
            self.cron.method_direct_trigger()
        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(self._clearing_lines(moves).reconciled)

        self.cron.method_direct_trigger()

        self.assertTrue(st_line.is_reconciled)
        self.assertTrue(self._clearing_lines(moves).reconciled)

    # Other automatic rules of the bank statement

    # Plan, test 30
    def test_statement_tariff_goes_to_the_tariff_expense_on_the_debit_date(self):
        self._create_writeoff_rule(
            "Synthetic bank tariffs", "TARIFF", "amount_paid", self.account_tariff
        )
        debit_date = CREDIT_DATE + timedelta(days=1)

        st_line = self._create_statement_line(
            self.journal_bb, -2.0, "TARIFF COLLECTION", line_date=debit_date
        )

        self.assertTrue(st_line.is_reconciled)
        tariff_line = st_line.move_id.line_ids.filtered(
            lambda line: line.account_id == self.account_tariff
        )
        self.assertEqual(
            (tariff_line.debit, tariff_line.credit, tariff_line.date),
            (2.0, 0.0, debit_date),
        )
        self.assertEqual(
            self._amounts_by_account(st_line.move_id),
            {self.account_bank_bb: (0.0, 2.0), self.account_tariff: (2.0, 0.0)},
        )
        # A tariff is not a collection credit
        self.assertFalse(st_line.eng_cnab_reconcile_status)

    # Plan, test 31
    def test_investment_application_and_redemption_post_to_the_investment(self):
        investment_account = self._create_account(
            "ENGSR.INV", "Synthetic Investment", "asset_current"
        )
        self._create_writeoff_rule(
            "Synthetic investment application",
            "INVESTMENT",
            "amount_paid",
            investment_account,
        )
        self._create_writeoff_rule(
            "Synthetic investment redemption",
            "INVESTMENT",
            "amount_received",
            investment_account,
        )

        application = self._create_statement_line(
            self.journal_bb, -1000.0, "INVESTMENT APPLICATION"
        )
        redemption = self._create_statement_line(
            self.journal_bb, 1000.0, "INVESTMENT REDEMPTION"
        )

        self.assertTrue(application.is_reconciled)
        self.assertTrue(redemption.is_reconciled)
        self.assertEqual(
            self._amounts_by_account(application.move_id),
            {self.account_bank_bb: (0.0, 1000.0), investment_account: (1000.0, 0.0)},
        )
        self.assertEqual(
            self._amounts_by_account(redemption.move_id),
            {self.account_bank_bb: (1000.0, 0.0), investment_account: (0.0, 1000.0)},
        )

    # Beyond the numbered scenarios of the plan

    def test_two_open_collection_credits_of_the_same_day_are_ambiguous(self):
        st_lines = self.env["account.bank.statement.line"].create(
            [
                {
                    "journal_id": self.journal_bb.id,
                    "date": CREDIT_DATE,
                    "amount": 100.0,
                    "payment_ref": label,
                }
                for label in (COLLECTION_LABEL, "COLLECTION SECOND CREDIT")
            ]
        )
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])

        self._run_cron_method()

        self.assertFalse(any(st_lines.mapped("is_reconciled")))
        self.assertFalse(self._clearing_lines(moves).reconciled)
        self.assertEqual(
            st_lines.mapped("eng_cnab_reconcile_status"), ["ambiguous", "ambiguous"]
        )
        for st_line in st_lines:
            self.assertIn(
                (st_lines - st_line).display_name, st_line.eng_cnab_reconcile_message
            )

    def test_line_whose_suspense_was_reconciled_in_part_is_left_out(self):
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        miscellaneous_journal = self.env["account.journal"].create(
            {
                "name": "Synthetic Miscellaneous",
                "code": "ECMIS",
                "type": "general",
                "company_id": self.company.id,
            }
        )
        entry = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": miscellaneous_journal.id,
                "date": CREDIT_DATE,
                "line_ids": [
                    Command.create(
                        {
                            "name": "Synthetic suspense",
                            "account_id": self.account_suspense.id,
                            "debit": 40.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Synthetic counterpart",
                            "account_id": self.account_income.id,
                            "credit": 40.0,
                        }
                    ),
                ],
            }
        )
        entry.action_post()
        _liquidity_lines, suspense_line, _other_lines = st_line._seek_for_lines()
        (
            suspense_line
            | entry.line_ids.filtered(
                lambda line: line.account_id == self.account_suspense
            )
        ).reconcile()
        # No counterpart was applied, but the residual is not the whole amount
        self.assertFalse(st_line._seek_for_lines()[2])
        self.assertEqual(st_line.amount_residual, -60.0)
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])

        self._run_cron_method()

        self.assertFalse(self._clearing_lines(moves).reconciled)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "partial")

    def test_draft_clearing_entry_is_not_selected_by_the_matcher(self):
        # Plan, test 12, with the real matcher: without automatic reconcile
        # the clearing entry stays in draft, out of every group
        self.journal_bb.return_auto_reconcile = False
        move = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        self.assertEqual(move.state, "draft")

        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        self._run_cron_method()

        self.assertFalse(st_line.is_reconciled)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "awaiting")
        self.assertFalse(self._clearing_lines(move).reconciled)

    def test_retry_clears_the_reason_once_no_cnab_rule_routes_the_line(self):
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "awaiting")

        self.rule_bb.active = False
        st_line.action_eng_cnab_retry()

        self.assertFalse(st_line.eng_cnab_reconcile_status)
        self.assertFalse(st_line.eng_cnab_reconcile_message)

    def test_lines_outside_the_cnab_routing_keep_the_generic_matching(self):
        # Not automatic: the creation of the lines must not reconcile them
        generic_rule = self._create_generic_rule(auto_reconcile=False)
        rules = generic_rule | self.rule_bb
        no_partner = self.env["res.partner"]
        transfer = self._create_statement_line(self.journal_bb, 100.0, TRANSFER_LABEL)
        before_cutover = self._create_statement_line(
            self.journal_bb,
            100.0,
            COLLECTION_LABEL,
            line_date=CUTOVER_DATE - timedelta(days=1),
        )

        for st_line in transfer | before_cutover:
            self.assertFalse(st_line.eng_cnab_reconcile_status)
            self.assertFalse(
                self.env["account.reconcile.model"]._eng_cnab_get_routing_rules(
                    st_line, no_partner
                )
            )
            result = rules._apply_rules(st_line, no_partner)
            self.assertEqual(result["model"], generic_rule)
            self.assertEqual(result["amls"], self.installment_bb)

    def test_clearing_account_is_empty_out_of_the_clearing_flow(self):
        in_flow = self._create_statement_line(self.journal_bb, 100.0, TRANSFER_LABEL)
        before_cutover = self._create_statement_line(
            self.journal_bb,
            100.0,
            TRANSFER_LABEL,
            line_date=CUTOVER_DATE - timedelta(days=1),
        )

        self.assertEqual(
            in_flow._eng_cnab_get_clearing_account(), self.account_clearing_bb
        )
        # The clearing lines only exist from the cutover date on
        self.assertFalse(before_cutover._eng_cnab_get_clearing_account())

    def test_import_without_clearing_entries_does_not_trigger_the_cron(self):
        trigger_model = self.env["ir.cron.trigger"]
        triggers_before = trigger_model.search([("cron_id", "=", self.cron.id)])
        # A tariff only event, then a liquidation credited before the cutover
        self._import(
            self.journal_bb,
            [
                self._bb_record(
                    self.installment_bb,
                    codigo_ocorrencia="28",
                    received=0.0,
                    tariff=1.5,
                )
            ],
        )
        legacy_move = self._import(
            self.journal_bb,
            [
                self._bb_record(
                    self.installment_bb_2,
                    data_credito=date(2025, 10, 31).strftime("%d%m%y"),
                )
            ],
        )
        self.assertEqual(legacy_move.state, "posted")
        self.assertFalse(legacy_move.eng_cnab_clearing)
        self.assertEqual(
            trigger_model.search([("cron_id", "=", self.cron.id)]), triggers_before
        )
        # Without its cron, the import still works
        self.cron.unlink()
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        self.assertTrue(moves.eng_cnab_clearing)

    def _pending_collection_credits(self):
        """One collection credit of each journal, created before its CNAB
        return, and then the returns: two lines that the cron reconciles,
        bank B first."""
        bb_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        ailos_line = self._create_statement_line(
            self.journal_ailos, 100.0, OWN_BANK_LABEL
        )
        bb_moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        ailos_moves = self._import(
            self.journal_ailos, [self._ailos_record(self.installment_ailos)]
        )
        self.assertEqual(
            (bb_line | ailos_line).mapped("eng_cnab_reconcile_status"),
            ["awaiting", "awaiting"],
        )
        return (
            bb_line,
            ailos_line,
            self._clearing_lines(bb_moves),
            self._clearing_lines(ailos_moves),
        )

    def test_business_error_of_one_line_is_recorded_and_the_cron_goes_on(self):
        (
            bb_line,
            ailos_line,
            bb_clearing_line,
            ailos_clearing_line,
        ) = self._pending_collection_credits()
        st_line_class = type(bb_line)
        reconcile_group = st_line_class._eng_cnab_reconcile_group

        def reconcile_then_fail_on_bank_b(st_line, clearing_lines):
            reconcile_group(st_line, clearing_lines)
            if st_line == bb_line:
                # After the reconciliation, which the savepoint must undo
                raise UserError(SYNTHETIC_BUSINESS_ERROR)

        with mock.patch.object(
            st_line_class,
            "_eng_cnab_reconcile_group",
            autospec=True,
            side_effect=reconcile_then_fail_on_bank_b,
        ) as reconcile_group_spy:
            self.cron.method_direct_trigger()

        # The failing line came first, and the next one went on
        self.assertEqual(
            [call.args[0] for call in reconcile_group_spy.call_args_list],
            [bb_line, ailos_line],
        )
        self.assertFalse(bb_line.is_reconciled)
        self.assertFalse(bb_clearing_line.reconciled)
        self.assertEqual(bb_line.eng_cnab_reconcile_status, "error")
        self.assertIn(SYNTHETIC_BUSINESS_ERROR, bb_line.eng_cnab_reconcile_message)
        self.assertTrue(ailos_line.is_reconciled)
        self.assertTrue(ailos_clearing_line.reconciled)
        self.assertEqual(ailos_line.eng_cnab_reconcile_status, "reconciled")

    def test_concurrency_error_of_one_line_still_fails_the_whole_cron_run(self):
        bb_line, *_other_records = self._pending_collection_credits()
        st_line_class = type(bb_line)

        with mock.patch.object(
            st_line_class,
            "_eng_cnab_reconcile_group",
            autospec=True,
            side_effect=SerializationFailure(
                "could not serialize access due to concurrent update"
            ),
        ) as reconcile_group, mock.patch.object(
            st_line_class, "_eng_cnab_write_outcome", autospec=True
        ) as write_outcome, self.assertRaises(SerializationFailure):
            self.cron.method_direct_trigger()

        # Not taken for a business error of the first line: the run stops
        # there with no reason written, and the next run tries again
        self.assertEqual(reconcile_group.call_count, 1)
        self.assertEqual(reconcile_group.call_args.args[0], bb_line)
        write_outcome.assert_not_called()

    def test_line_unreconciled_by_hand_waits_for_retry(self):
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        clearing_line = self._clearing_lines(moves)
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        self.assertTrue(st_line.is_reconciled)

        st_line.unreconcile_bank_line()

        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(clearing_line.reconciled)
        self.assertTrue(st_line.eng_cnab_excluded)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "excluded")
        # Neither the cron nor the automatic rules, of the line creation and
        # of the reconciliation screen, match it again
        self._run_cron_method()
        self.assertFalse(self.rule_bb._apply_rules(st_line, self.env["res.partner"]))
        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(clearing_line.reconciled)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "excluded")

        st_line.action_eng_cnab_retry()

        self.assertFalse(st_line.eng_cnab_excluded)
        self.assertTrue(st_line.is_reconciled)
        self.assertTrue(clearing_line.reconciled)
        self.assertEqual(self._counterpart_moves(clearing_line), st_line.move_id)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "reconciled")

    def test_reconciliation_reverted_from_the_list_waits_for_retry(self):
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        clearing_line = self._clearing_lines(moves)
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        self.assertTrue(st_line.is_reconciled)

        # The Revert reconciliation button of the list of statement lines,
        # which does not go through the reconciliation screen
        st_line.action_undo_reconciliation()
        self._run_cron_method()

        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(clearing_line.reconciled)
        self.assertTrue(st_line.eng_cnab_excluded)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "excluded")

    def test_matching_drops_the_draft_of_the_reconciliation_screen(self):
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        # The Reset button of the reconciliation screen keeps a draft
        st_line.clean_reconcile()
        self.assertTrue(st_line.reconcile_data)
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])

        self._run_cron_method()

        self.assertTrue(st_line.is_reconciled)
        self.assertTrue(self._clearing_lines(moves).reconciled)
        self.assertFalse(st_line.reconcile_data)

    def test_line_reconciled_on_the_screen_drops_its_cnab_reason(self):
        payment_line = self._receive_manual_payment(100.0)
        st_line = self._create_statement_line(self.journal_bb, 100.0, COLLECTION_LABEL)
        self.assertEqual(st_line.eng_cnab_reconcile_status, "awaiting")

        with Form(
            st_line,
            view="account_reconcile_oca.bank_statement_line_form_reconcile_view",
        ) as reconcile_form:
            reconcile_form.add_account_move_line_id = payment_line
            self.assertTrue(reconcile_form.can_reconcile)
        st_line.reconcile_bank_line()

        self.assertTrue(st_line.is_reconciled)
        self.assertTrue(payment_line.reconciled)
        self.assertFalse(st_line.eng_cnab_reconcile_status)
        self.assertFalse(st_line.eng_cnab_reconcile_message)
        self.assertEqual(st_line.eng_cnab_reconcile_difference, 0.0)

    def test_invalid_configuration_keeps_the_exclusive_routing(self):
        generic_rule = self._create_generic_rule()
        # The only open item of the amount of the collection credit
        payment_line = self._receive_manual_payment(75.0)
        no_partner = self.env["res.partner"]
        # Unlike a change of the journal, it passes no journal constraint
        self.journal_bb.eng_cnab_receipt_method_line_id.payment_account_id = False

        st_line = self._create_statement_line(self.journal_bb, 75.0, COLLECTION_LABEL)

        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(payment_line.reconciled)
        self.assertEqual(payment_line.amount_residual, 75.0)
        # Without the exclusive routing, the generic rule would take it
        self.assertEqual(
            generic_rule._get_invoice_matching_amls_candidates(st_line, no_partner)[
                "amls"
            ],
            payment_line,
        )
        self.assertFalse(
            (generic_rule | self.rule_bb)._apply_rules(st_line, no_partner)
        )
        self.assertEqual(st_line.eng_cnab_reconcile_status, "invalid_config")
        message = st_line.eng_cnab_reconcile_message
        self.assertTrue(message.startswith("Invalid configuration: "))
        self.assertIn("must have its own outstanding receipts account", message)

    def test_cnab_rules_closing_distinct_groups_are_ambiguous(self):
        # Both receiving bank rules of bank A now route the same label, and
        # so does a new rule of any bank
        self.rule_ailos_other.match_label_param = "COLLECTION OWN"
        any_bank_rule = self._create_cnab_rule(
            "Synthetic A collection, any bank",
            self.journal_ailos,
            "contains",
            "COLLECTION",
        )
        moves = self._import(
            self.journal_ailos,
            [
                self._ailos_record(
                    self.installment_ailos, received=50.0, banco_recebedor="085"
                ),
                self._ailos_record(
                    self.installment_ailos_2, received=50.0, banco_recebedor="237"
                ),
            ],
        )
        clearing_lines = self._clearing_lines(moves)

        # Created after the return: the automatic reconciliation of the
        # creation runs first, then the cron and the Retry button
        st_line = self._create_statement_line(self.journal_ailos, 50.0, OWN_BANK_LABEL)
        self.assertFalse(st_line.is_reconciled)
        self._run_cron_method()
        st_line.action_eng_cnab_retry()

        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(any(clearing_lines.mapped("reconciled")))
        self.assertEqual(st_line.eng_cnab_reconcile_status, "ambiguous")
        message = st_line.eng_cnab_reconcile_message
        for rule in self.rule_ailos_own | self.rule_ailos_other:
            self.assertIn(rule.display_name, message)
        # The group of any bank sums 100: not an exact group
        self.assertNotIn(any_bank_rule.display_name, message)

    def _create_same_day_credits(self, amount, labels):
        """Collection credits of bank A created together, as one statement
        import does: the automatic reconciliation of the creation of each
        line already sees the others."""
        return self.env["account.bank.statement.line"].create(
            [
                {
                    "journal_id": self.journal_ailos.id,
                    "date": CREDIT_DATE,
                    "amount": amount,
                    "payment_ref": label,
                }
                for label in labels
            ]
        )

    def test_competitor_of_one_rule_keeps_distinct_exact_groups_ambiguous(self):
        # Both receiving bank rules of bank A route the collection credit,
        # and only the own bank rule routes the second credit of the day
        self.rule_ailos_other.match_label_param = OWN_BANK_LABEL
        moves = self._import(
            self.journal_ailos,
            [
                self._ailos_record(
                    self.installment_ailos, received=50.0, banco_recebedor="085"
                ),
                self._ailos_record(
                    self.installment_ailos_2, received=50.0, banco_recebedor="237"
                ),
            ],
        )
        clearing_lines = self._clearing_lines(moves)

        st_line, second_st_line = self._create_same_day_credits(
            50.0, (OWN_BANK_LABEL, "COLLECTION OWN SECOND CREDIT")
        )

        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(any(clearing_lines.mapped("reconciled")))
        # Each rule closes an exact group of its own, and the second credit
        # competes for the group of the own bank rule only: alone, the other
        # banks rule would reconcile its group
        own_evaluation = self.rule_ailos_own._eng_cnab_evaluate(st_line)
        other_evaluation = self.rule_ailos_other._eng_cnab_evaluate(st_line)
        self.assertTrue(own_evaluation["exact"])
        self.assertEqual(own_evaluation["status"], "ambiguous")
        self.assertEqual(own_evaluation["competitors"], second_st_line)
        self.assertEqual(other_evaluation["status"], "match")
        self.assertNotEqual(own_evaluation["lines"], other_evaluation["lines"])
        self._run_cron_method()
        st_line.action_eng_cnab_retry()

        self.assertFalse((st_line | second_st_line).filtered("is_reconciled"))
        self.assertFalse(any(clearing_lines.mapped("reconciled")))
        self.assertEqual(
            (st_line | second_st_line).mapped("eng_cnab_reconcile_status"),
            ["ambiguous", "ambiguous"],
        )
        message = st_line.eng_cnab_reconcile_message
        for rule in self.rule_ailos_own | self.rule_ailos_other:
            self.assertIn(rule.display_name, message)
        self.assertIn(st_line.display_name, second_st_line.eng_cnab_reconcile_message)

    def test_exact_group_contested_under_one_rule_is_not_won_by_another(self):
        # A rule of any bank routes the own bank credit too, with the same
        # group, and also routes the second credit of the day
        any_bank_rule = self._create_cnab_rule(
            "Synthetic A collection, any bank",
            self.journal_ailos,
            "contains",
            "COLLECTION",
        )
        moves = self._import(
            self.journal_ailos, [self._ailos_record(self.installment_ailos)]
        )
        clearing_line = self._clearing_lines(moves)

        st_line, second_st_line = self._create_same_day_credits(
            100.0, (OWN_BANK_LABEL, "COLLECTION SECOND CREDIT")
        )

        self.assertFalse(st_line.is_reconciled)
        self.assertFalse(clearing_line.reconciled)
        # Alone, the own bank rule would reconcile the group, which the
        # second credit competes for under the rule of any bank
        own_evaluation = self.rule_ailos_own._eng_cnab_evaluate(st_line)
        any_evaluation = any_bank_rule._eng_cnab_evaluate(st_line)
        self.assertEqual(own_evaluation["status"], "match")
        self.assertEqual(any_evaluation["lines"], own_evaluation["lines"])
        self.assertTrue(any_evaluation["exact"])
        self.assertEqual(any_evaluation["competitors"], second_st_line)
        self._run_cron_method()
        st_line.action_eng_cnab_retry()

        self.assertFalse((st_line | second_st_line).filtered("is_reconciled"))
        self.assertFalse(clearing_line.reconciled)
        self.assertEqual(
            (st_line | second_st_line).mapped("eng_cnab_reconcile_status"),
            ["ambiguous", "ambiguous"],
        )
        message = st_line.eng_cnab_reconcile_message
        self.assertIn(any_bank_rule.display_name, message)
        self.assertIn(second_st_line.display_name, message)

    def test_line_reconciled_in_part_does_not_compete_for_the_group(self):
        payment_line = self._receive_manual_payment(40.0)
        partial_st_line = self._create_statement_line(
            self.journal_bb, 100.0, COLLECTION_LABEL
        )
        self._reconcile_by_hand(partial_st_line, payment_line)
        full_st_line = self._create_statement_line(
            self.journal_bb, 100.0, "COLLECTION SECOND CREDIT"
        )
        moves = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        clearing_line = self._clearing_lines(moves)

        self._run_cron_method()

        self.assertTrue(full_st_line.is_reconciled)
        self.assertTrue(clearing_line.reconciled)
        self.assertEqual(self._counterpart_moves(clearing_line), full_st_line.move_id)
        self.assertEqual(full_st_line.eng_cnab_reconcile_status, "reconciled")
        self.assertFalse(partial_st_line.is_reconciled)
        self.assertEqual(partial_st_line.eng_cnab_reconcile_status, "partial")

    # assertRaises, not assertRaisesRegex: only the former rolls the refused
    # write back, so that each case starts from a valid record

    def test_cnab_matching_rule_matches_invoices_and_validates_automatically(self):
        for values, message in (
            ({"rule_type": "writeoff_suggestion"}, "needs the type"),
            ({"auto_reconcile": False}, "enable its Auto-validate option"),
        ):
            with self.assertRaises(ValidationError) as error:
                self.rule_bb.write(values)
            self.assertIn(message, str(error.exception))

    def test_cnab_clearing_journal_edits_moves_and_keeps_its_own_suspense(self):
        for values, message in (
            ({"reconcile_mode": "keep"}, "'Edit Move' mode"),
            (
                {"suspense_account_id": self.account_clearing_bb.id},
                "cannot be its suspense account",
            ),
        ):
            with self.assertRaises(ValidationError) as error:
                self.journal_bb.write(values)
            self.assertIn(message, str(error.exception))
