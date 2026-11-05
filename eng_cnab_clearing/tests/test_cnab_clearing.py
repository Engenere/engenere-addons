# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import hashlib
from datetime import date, datetime, timedelta
from unittest import mock

from freezegun import freeze_time
from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.tools.misc import format_date

from odoo.addons.account_move_base_import.parser.parser import new_move_parser
from odoo.addons.l10n_br_account_payment_brcobranca.models.account_journal import (
    AccountJournal as BrcobrancaAccountJournal,
)
from odoo.addons.l10n_br_account_payment_brcobranca.models.account_move import (
    AccountMove as BrcobrancaAccountMove,
)
from odoo.addons.l10n_br_account_payment_brcobranca.parser.cnab_file_parser import (
    CNABFileParser,
)

from ..parser.cnab_clearing_parser import EngClearingCNABParser
from .common import (
    AILOS_CREDIT_UNION,
    CREDIT_DATE,
    CUTOVER_DATE,
    FILE_NAME,
    OCCURRENCE_DATE,
    OTHER_AILOS_CREDIT_UNION,
    CnabClearingCommon,
)


class _ImportRolledBack(Exception):
    """Carries what an import produced out of its rolled back savepoint."""

    def __init__(self, snapshot):
        super().__init__()
        self.snapshot = snapshot


@tagged("post_install", "-at_install")
class TestCnabClearing(CnabClearingCommon):
    def _import_rolled_back(self, journal, records):
        """Import the records, describe the result and roll it back."""
        try:
            with self.env.cr.savepoint():
                moves = self._import(journal, records)
                raise _ImportRolledBack(
                    {
                        "entries": [
                            (
                                move.date,
                                sorted(
                                    (
                                        line.account_id.code,
                                        line.debit,
                                        line.credit,
                                        str(line.date_maturity),
                                    )
                                    for line in move.line_ids
                                ),
                            )
                            for move in moves
                        ],
                        "log_import_date": moves.cnab_return_log_id.cnab_date_import,
                    }
                )
        except _ImportRolledBack as rollback:
            return rollback.snapshot

    @staticmethod
    def _listed_record(position):
        """Reference of a record without sequence number in an error."""
        return (
            f"Record in position {position} of the records read from the file, "
            "which has no sequence number"
        )

    # Plan, test 1
    def test_liquidation_posts_on_occurrence_date_against_clearing_account(self):
        records = [self._bb_record(self.installment_bb), self._bb_trailer()]
        move = self._import(self.journal_bb, records)

        self.assertEqual(move.state, "posted")
        self.assertEqual(move.date, OCCURRENCE_DATE)
        clearing_line = self._clearing_line(move)
        self.assertEqual(clearing_line.account_id, self.account_clearing_bb)
        self.assertEqual(clearing_line.debit, 100.0)
        self.assertEqual(clearing_line.date_maturity, CREDIT_DATE)
        self.assertFalse(
            move.line_ids.filtered(
                lambda line: line.account_id == self.journal_bb.default_account_id
            )
        )
        self.assertEqual(self.installment_bb.amount_residual, 0.0)
        self.assertEqual(self.installment_bb.move_id.payment_state, "paid")

        # Markers and traceability of the clearing entry
        event = move.eng_cnab_return_event_id
        self.assertTrue(move.eng_cnab_clearing)
        self.assertEqual(move.eng_cnab_occurrence_date, OCCURRENCE_DATE)
        self.assertEqual(move.eng_cnab_credit_date, CREDIT_DATE)
        self.assertEqual(event.eng_move_id, move)
        self.assertEqual(event.eng_record_position, 1)
        self.assertEqual(event.occurrence_date, OCCURRENCE_DATE)
        self.assertEqual(event.real_payment_date, CREDIT_DATE)
        self.assertEqual(event.eng_receiving_bank_code, "001")
        self.assertEqual(clearing_line.eng_cnab_return_event_id, event)
        self.assertEqual(clearing_line.eng_cnab_receiving_bank_class, "own")
        self.assertEqual(clearing_line.partner_id, self.partner)
        # Only the installment line keeps the reference _post() reconciles by
        self.assertEqual(
            move.line_ids.filtered("cnab_returned_ref").cnab_returned_ref,
            self.installment_bb.own_number,
        )
        log = move.cnab_return_log_id
        # The trailer of the file is skipped, as by the original parser
        self.assertEqual(log.event_ids, event)
        self.assertEqual(log.eng_journal_id, self.journal_bb)
        self.assertEqual(
            log.eng_file_hash,
            hashlib.sha256(self._file_content(records)).hexdigest(),
        )

    # Plan, test 2
    def test_same_file_imported_on_another_day_keeps_accounting_dates(self):
        records = [self._bb_record(self.installment_bb)]
        with freeze_time("2025-11-03 09:00:00"):
            first_import = self._import_rolled_back(self.journal_bb, records)
        with freeze_time("2025-11-24 17:00:00"):
            later_import = self._import_rolled_back(self.journal_bb, records)

        self.assertEqual(first_import["entries"], later_import["entries"])
        self.assertEqual(
            [entry_date for entry_date, _lines in first_import["entries"]],
            [OCCURRENCE_DATE],
        )
        self.assertIn(
            str(CREDIT_DATE),
            [line[3] for line in first_import["entries"][0][1]],
        )
        # Only the log tells the import day
        self.assertEqual(first_import["log_import_date"], datetime(2025, 11, 3, 9))
        self.assertEqual(later_import["log_import_date"], datetime(2025, 11, 24, 17))

    # Plan, test 3
    def test_interest_is_credited_and_clearing_gets_the_received_amount(self):
        move = self._import(
            self.journal_bb,
            [self._bb_record(self.installment_bb, received=110.0, interest=10.0)],
        )

        self.assertEqual(
            self._amounts_by_account(move),
            {
                self.account_clearing_bb: (110.0, 0.0),
                self.account_receivable: (0.0, 100.0),
                self.account_interest: (0.0, 10.0),
            },
        )

    # Plan, test 4
    def test_discount_and_rebate_are_debited_and_installment_is_settled(self):
        move = self._import(
            self.journal_bb,
            [
                self._bb_record(
                    self.installment_bb, received=85.0, discount=10.0, rebate=5.0
                )
            ],
        )

        self.assertEqual(
            self._amounts_by_account(move),
            {
                self.account_clearing_bb: (85.0, 0.0),
                self.account_discount: (10.0, 0.0),
                self.account_rebate: (5.0, 0.0),
                self.account_receivable: (0.0, 100.0),
            },
        )
        self.assertEqual(self.installment_bb.amount_residual, 0.0)

    # Plan, test 5
    def test_cnab_tariff_stays_on_the_event_only(self):
        move = self._import(
            self.journal_bb, [self._bb_record(self.installment_bb, tariff=2.0)]
        )

        self.assertEqual(move.eng_cnab_return_event_id.tariff_charge, 2.0)
        self.assertFalse(
            move.line_ids.filtered(
                lambda line: line.account_id
                in (self.account_tariff | self.account_bank_bb)
            )
        )
        self.assertEqual(
            self._amounts_by_account(move),
            {
                self.account_clearing_bb: (100.0, 0.0),
                self.account_receivable: (0.0, 100.0),
            },
        )

    # Plan, test 6
    def test_tariff_only_event_creates_no_entry(self):
        counts = self._count_import_records()
        log = self._import(
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

        self.assertEqual(log._name, "l10n_br_cnab.return.log")
        self.assertEqual(len(log.event_ids), 1)
        self.assertEqual(log.event_ids.eng_record_position, 1)
        self.assertTrue(log.event_ids.occurrences.startswith("28-"))
        self.assertFalse(log.move_ids)
        self.assertEqual(self._count_import_records()["moves"], counts["moves"])

    # Plan, test 7
    def test_record_without_occurrence_date_blocks_file_before_processing(self):
        original_cnab_state = self.installment_bb.cnab_state
        counts = self._count_import_records()
        record_without_date = self._bb_record(self.installment_bb_2)
        del record_without_date["data_ocorrencia"]
        records = [
            # Valid entry confirmation: processed, it would write cnab_state
            self._bb_record(self.installment_bb, codigo_ocorrencia="02", received=0.0),
            record_without_date,
        ]

        with mock.patch.object(
            CNABFileParser,
            "process_return_file",
            autospec=True,
            side_effect=CNABFileParser.process_return_file,
        ) as base_processing:
            with self.assertRaises(UserError) as error:
                self._import(self.journal_bb, records)

        message = str(error.exception)
        self.assertIn(FILE_NAME, message)
        self.assertIn(
            f"{self._listed_record(2)} "
            f"(own number {record_without_date['nosso_numero']}): "
            "the occurrence date is missing",
            message,
        )
        self.assertNotIn(self._listed_record(1), message)
        base_processing.assert_not_called()
        self.assertEqual(self._count_import_records(), counts)
        self.assertEqual(self.installment_bb.cnab_state, original_cnab_state)

    # Plan, test 8
    def test_empty_zeroed_or_invalid_occurrence_date_blocks_without_fallback(self):
        counts = self._count_import_records()
        # Every record has a valid credit date: it must not replace the
        # occurrence date
        records = [
            self._bb_record(self.installment_bb, data_ocorrencia=""),
            self._bb_record(self.installment_bb, data_ocorrencia="000000"),
            self._bb_record(self.installment_bb, data_ocorrencia="321025"),
        ]

        with self.assertRaises(UserError) as error:
            self._import(self.journal_bb, records)

        message = str(error.exception)
        own_number = records[0]["nosso_numero"]
        self.assertIn(
            f"{self._listed_record(1)} (own number {own_number}): "
            "the occurrence date is missing",
            message,
        )
        self.assertIn(
            f"{self._listed_record(2)} (own number {own_number}): "
            "the occurrence date is zeroed",
            message,
        )
        self.assertIn(
            f"{self._listed_record(3)} (own number {own_number}): "
            "the occurrence date 321025 is invalid",
            message,
        )
        self.assertEqual(self._count_import_records(), counts)

    # Plan, test 9
    def test_liquidation_without_credit_date_raises_user_error(self):
        counts = self._count_import_records()
        records = [
            self._bb_record(self.installment_bb, data_credito="000000"),
            self._bb_record(self.installment_bb_2, data_credito=None),
        ]

        # An AttributeError would not be caught here and fail the test
        with self.assertRaises(UserError) as error:
            self._import(self.journal_bb, records)

        message = str(error.exception)
        for position, record in enumerate(records, start=1):
            self.assertIn(
                f"{self._listed_record(position)} "
                f"(own number {record['nosso_numero']}): "
                "the liquidation has no valid credit date",
                message,
            )
        self.assertEqual(self._count_import_records(), counts)

    # Plan, test 10
    def test_ailos_liquidation_without_receiving_bank_is_blocked(self):
        counts = self._count_import_records()
        # Neither blank nor zeroed is taken as "other banks"
        records = [
            self._ailos_record(self.installment_ailos, banco_recebedor=None),
            self._ailos_record(self.installment_ailos_2, banco_recebedor="000"),
        ]

        with self.assertRaises(UserError) as error:
            self._import(self.journal_ailos, records)

        message = str(error.exception)
        for position, record in enumerate(records, start=1):
            self.assertIn(
                f"{self._listed_record(position)} "
                f"(own number {record['nosso_numero']}): "
                "the liquidation has no receiving bank",
                message,
            )
        self.assertEqual(self._count_import_records(), counts)

    def test_ailos_liquidation_at_its_bank_without_branch_is_blocked(self):
        counts = self._count_import_records()
        # Nothing tells the credit union that received them
        records = [
            self._ailos_record(self.installment_ailos, agencia_recebedora_com_dv=None),
            self._ailos_record(self.installment_ailos_2, agencia_com_dv="000000"),
        ]

        with self.assertRaises(UserError) as error:
            self._import(self.journal_ailos, records)

        message = str(error.exception)
        for position, record in enumerate(records, start=1):
            self.assertIn(
                f"{self._listed_record(position)} "
                f"(own number {record['nosso_numero']}): "
                "the liquidation has no receiving branch",
                message,
            )
        self.assertEqual(self._count_import_records(), counts)

    # Plan, test 11
    def test_two_events_of_the_same_installment_link_each_entry_to_its_event(self):
        moves = self._import(
            self.journal_bb,
            [
                self._bb_record(self.installment_bb, received=40.0),
                self._bb_record(self.installment_bb, received=60.0),
            ],
        )

        self.assertEqual(len(moves), 2)
        moves_by_amount = {self._clearing_line(move).debit: move for move in moves}
        for position, amount in ((1, 40.0), (2, 60.0)):
            move = moves_by_amount[amount]
            event = move.eng_cnab_return_event_id
            self.assertEqual(event.eng_record_position, position)
            self.assertEqual(event.payment_value, amount)
            self.assertEqual(event.eng_move_id, move)
            self.assertEqual(self._clearing_line(move).eng_cnab_return_event_id, event)
        self.assertEqual(self.installment_bb.amount_residual, 0.0)

    # Plan, test 12
    def test_without_auto_reconcile_entry_stays_draft_out_of_matching(self):
        self.journal_bb.return_auto_reconcile = False

        move = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])

        self.assertEqual(move.state, "draft")
        self.assertTrue(self._clearing_line(move))
        # The statement matcher only selects posted, open clearing lines
        matchable_lines = self.env["account.move.line"].search(
            [
                ("eng_cnab_clearing", "=", True),
                ("parent_state", "=", "posted"),
                ("account_id", "=", self.account_clearing_bb.id),
                ("date_maturity", "=", CREDIT_DATE),
                ("amount_residual", ">", 0.0),
            ]
        )
        self.assertFalse(matchable_lines)
        self.assertEqual(self.installment_bb.amount_residual, 100.0)

    # Plan, test 13
    def test_occurrence_on_or_before_lock_date_blocks_import(self):
        lock_date = date(2025, 10, 31)
        self._set_lock_date(lock_date)
        counts = self._count_import_records()

        with self.assertRaises(UserError) as error:
            self._import(self.journal_bb, [self._bb_record(self.installment_bb)])

        message = str(error.exception)
        self.assertIn(
            f"occurrence date {format_date(self.env, OCCURRENCE_DATE)}", message
        )
        self.assertIn(f"lock date {format_date(self.env, lock_date)}", message)
        self.assertRegex(message, r"posting would move it to \S+")
        self.assertEqual(self._count_import_records(), counts)
        self.assertEqual(self.installment_bb.amount_residual, 100.0)

    # Plan, test 14
    def test_post_override_changing_the_date_is_reverted(self):
        counts = self._count_import_records()
        original_post = BrcobrancaAccountMove._post
        # Same year: the sequence of the bank journal still matches
        shifted_date = date(2025, 10, 31)

        def post_and_shift_date(moves, soft=True):
            posted = original_post(moves, soft=soft)
            posted.write({"date": shifted_date})
            return posted

        with mock.patch.object(BrcobrancaAccountMove, "_post", post_and_shift_date):
            with self.assertRaises(UserError) as error:
                self._import(self.journal_bb, [self._bb_record(self.installment_bb)])

        message = str(error.exception)
        self.assertIn("the posting was cancelled", message)
        self.assertIn(f"posted on {format_date(self.env, shifted_date)}", message)
        self.assertEqual(self._count_import_records(), counts)
        self.assertEqual(self.installment_bb.amount_residual, 100.0)

    # Plan, test 15
    def test_credit_before_cutover_keeps_the_legacy_bank_flow(self):
        credit_date = date(2025, 10, 31)
        move = self._import(
            self.journal_bb,
            [
                self._bb_record(
                    self.installment_bb,
                    data_credito=credit_date.strftime("%d%m%y"),
                    tariff=2.0,
                )
            ],
        )

        self.assertFalse(move.eng_cnab_clearing)
        self.assertFalse(self._clearing_line(move))
        self.assertEqual(move.date, credit_date)
        self.assertEqual(
            self._amounts_by_account(move),
            {
                self.account_bank_bb: (100.0, 2.0),
                self.account_tariff: (2.0, 0.0),
                self.account_receivable: (0.0, 100.0),
            },
        )
        self.assertEqual(self.installment_bb.amount_residual, 0.0)

    # Plan, test 16
    def test_credit_on_cutover_date_uses_the_clearing_flow(self):
        move = self._import(
            self.journal_bb,
            [
                self._bb_record(
                    self.installment_bb, data_credito=CUTOVER_DATE.strftime("%d%m%y")
                )
            ],
        )

        self.assertTrue(move.eng_cnab_clearing)
        self.assertEqual(move.date, OCCURRENCE_DATE)
        self.assertEqual(self._clearing_line(move).date_maturity, CUTOVER_DATE)
        self.assertFalse(
            move.line_ids.filtered(lambda line: line.account_id == self.account_bank_bb)
        )

    # Plan, test 17
    def test_disabled_journal_keeps_the_original_import(self):
        self.journal_bb.eng_cnab_clearing_enabled = False

        with mock.patch.object(
            BrcobrancaAccountJournal,
            "multi_move_import",
            autospec=True,
            side_effect=BrcobrancaAccountJournal.multi_move_import,
        ) as original_import:
            move = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])

        original_import.assert_called_once()
        self.assertFalse(move.eng_cnab_clearing)
        self.assertEqual(move.date, CREDIT_DATE)
        self.assertEqual(
            self._amounts_by_account(move),
            {
                self.account_bank_bb: (100.0, 0.0),
                self.account_receivable: (0.0, 100.0),
            },
        )
        self.assertEqual(self.installment_bb.amount_residual, 0.0)
        log = move.cnab_return_log_id
        self.assertFalse(log.eng_file_hash)
        self.assertFalse(log.event_ids.eng_record_position)

    # Plan, test 18
    def test_same_file_hash_cannot_be_imported_twice(self):
        records = [self._bb_record(self.installment_bb)]
        move = self._import(self.journal_bb, records)
        counts = self._count_import_records()

        with self._mock_brcobranca(records) as brcobranca_api:
            with self.assertRaisesRegex(UserError, "was already imported"):
                self._run_import(self.journal_bb, records)

        brcobranca_api.assert_not_called()
        self.assertEqual(self._count_import_records(), counts)
        # The database refuses a second log of the same file as well
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self.env["l10n_br_cnab.return.log"].create(
                {
                    "name": "Synthetic duplicate",
                    "eng_journal_id": self.journal_bb.id,
                    "eng_file_hash": move.cnab_return_log_id.eng_file_hash,
                }
            )
            self.env.flush_all()

    # Beyond the numbered scenarios of the plan

    def test_receiving_bank_class_follows_the_bank_of_the_journal(self):
        moves = self._import(
            self.journal_ailos,
            [
                self._ailos_record(self.installment_ailos, banco_recebedor="085"),
                self._ailos_record(
                    self.installment_ailos_2, banco_recebedor="237", tariff=1.5
                ),
            ],
        )

        classes = {
            move.eng_cnab_return_event_id.eng_receiving_bank_code: (
                self._clearing_line(move).eng_cnab_receiving_bank_class
            )
            for move in moves
        }
        self.assertEqual(classes, {"085": "own", "237": "other"})
        for move in moves:
            self.assertEqual(move.date, OCCURRENCE_DATE)
            self.assertEqual(self._clearing_line(move).date_maturity, CREDIT_DATE)
            self.assertEqual(
                self._amounts_by_account(move),
                {
                    self.account_clearing_ailos: (100.0, 0.0),
                    self.account_receivable: (0.0, 100.0),
                },
            )

    def test_ailos_title_paid_at_another_credit_union_is_of_the_other_banks(self):
        moves = self._import(
            self.journal_ailos,
            [
                self._ailos_record(self.installment_ailos),
                self._ailos_record(
                    self.installment_ailos_2,
                    agencia_recebedora_com_dv=OTHER_AILOS_CREDIT_UNION,
                ),
            ],
        )

        events = moves.mapped("eng_cnab_return_event_id")
        self.assertEqual(set(events.mapped("eng_receiving_bank_code")), {"085"})
        classes = {
            move.eng_cnab_return_event_id.eng_receiving_branch_code: (
                self._clearing_line(move).eng_cnab_receiving_bank_class
            )
            for move in moves
        }
        self.assertEqual(
            classes, {AILOS_CREDIT_UNION: "own", OTHER_AILOS_CREDIT_UNION: "other"}
        )

    def test_ailos_title_paid_at_another_bank_needs_no_branch(self):
        move = self._import(
            self.journal_ailos,
            [
                self._ailos_record(
                    self.installment_ailos,
                    banco_recebedor="237",
                    agencia_recebedora_com_dv=None,
                )
            ],
        )

        self.assertEqual(
            self._clearing_line(move).eng_cnab_receiving_bank_class, "other"
        )
        self.assertFalse(move.eng_cnab_return_event_id.eng_receiving_branch_code)

    def test_receiving_branch_does_not_change_the_class_outside_ailos(self):
        # Banco do Brasil credits the collection of a day at once, and its
        # return gives the two branches in different formats
        move = self._import(
            self.journal_bb,
            [
                self._bb_record(
                    self.installment_bb,
                    agencia_com_dv="11119",
                    agencia_recebedora_com_dv="00022",
                )
            ],
        )

        self.assertEqual(self._clearing_line(move).eng_cnab_receiving_bank_class, "own")

    def test_missing_receiving_bank_outside_ailos_leaves_the_class_empty(self):
        move = self._import(
            self.journal_bb,
            [self._bb_record(self.installment_bb, banco_recebedor=None)],
        )

        clearing_line = self._clearing_line(move)
        self.assertEqual(clearing_line.debit, 100.0)
        self.assertFalse(clearing_line.eng_cnab_receiving_bank_class)
        self.assertFalse(move.eng_cnab_return_event_id.eng_receiving_bank_code)

    def test_manual_post_of_a_draft_clearing_entry_is_protected_too(self):
        self.journal_bb.return_auto_reconcile = False
        self._set_lock_date(date(2025, 10, 31))
        move = self._import(self.journal_bb, [self._bb_record(self.installment_bb)])
        self.assertEqual(move.state, "draft")

        with self.assertRaisesRegex(UserError, "cannot be posted"):
            move.action_post()

        self._set_lock_date(False)
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.date, OCCURRENCE_DATE)

    def test_liquidation_settling_no_installment_amount_blocks_file(self):
        counts = self._count_import_records()

        with self.assertRaisesRegex(
            UserError,
            r"Record in position 1 of the records read from the file, which has "
            r"no sequence number \(own number \d+\) is a liquidation that settles "
            "no amount of the installment",
        ):
            self._import(
                self.journal_bb, [self._bb_record(self.installment_bb, received=0.0)]
            )

        self.assertEqual(self._count_import_records(), counts)

    def test_error_points_to_the_sequence_number_of_the_record(self):
        counts = self._count_import_records()
        # Bank B: the API leaves the header (line 1 of the file) out and keeps
        # the trailer, so the second detail record is line 3 of the file
        bb_record_without_date = self._bb_record(
            self.installment_bb_2, sequencial="000003"
        )
        del bb_record_without_date["data_ocorrencia"]
        bb_records = [
            self._bb_record(
                self.installment_bb,
                codigo_ocorrencia="02",
                received=0.0,
                sequencial="000002",
            ),
            bb_record_without_date,
            dict(self._bb_trailer(), sequencial="000004"),
        ]
        # Bank A: the number of segment T in its batch, where each detail
        # record has a segment T and a segment U
        ailos_record_without_bank = self._ailos_record(
            self.installment_ailos_2, banco_recebedor=None, sequencial="00003"
        )
        ailos_records = [
            self._ailos_record(self.installment_ailos, sequencial="00001"),
            ailos_record_without_bank,
        ]

        for journal, records, faulty_record, reason in (
            (
                self.journal_bb,
                bb_records,
                bb_record_without_date,
                "the occurrence date is missing",
            ),
            (
                self.journal_ailos,
                ailos_records,
                ailos_record_without_bank,
                "the liquidation has no receiving bank",
            ),
        ):
            with self.assertRaises(UserError) as error:
                self._import(journal, records)
            message = str(error.exception)
            # Not the position 2 of the record in the list read from the file
            self.assertIn(
                "Record with sequence number 3 "
                f"(own number {faulty_record['nosso_numero']}): {reason}",
                message,
            )
            self.assertNotIn("Record in position", message)
        self.assertEqual(self._count_import_records(), counts)

    def test_import_rechecks_the_configuration_before_parsing(self):
        self.journal_bb.eng_cnab_receipt_method_line_id.payment_account_id = False
        records = [self._bb_record(self.installment_bb)]

        with self._mock_brcobranca(records) as brcobranca_api:
            with self.assertRaisesRegex(
                ValidationError, "must have its own outstanding receipts account"
            ):
                self._run_import(self.journal_bb, records)

        brcobranca_api.assert_not_called()

    def test_clearing_configuration_of_the_journal_is_validated(self):
        journal = self.journal_bb
        receipt_method_line = journal.eng_cnab_receipt_method_line_id
        other_company = self.env["res.company"].create(
            {"name": "Synthetic Other Company"}
        )
        other_company_account = self.env["account.account"].create(
            {
                "code": "ENGCC.OTH",
                "name": "Synthetic Other Clearing",
                "account_type": "asset_current",
                "reconcile": True,
                "company_id": other_company.id,
            }
        )
        unreconcilable_account = self._create_account(
            "ENGCC.NRC", "Synthetic Unreconcilable", "asset_cash"
        )

        # assertRaises, not assertRaisesRegex: only the former rolls the
        # refused write back, so that each case starts from a valid journal
        with self.assertRaises(ValidationError) as error:
            journal.import_type = "cnab240"
        self.assertIn("supports only", str(error.exception))
        with self.assertRaises(ValidationError) as error:
            journal.eng_bank_cutover_date = False
        self.assertIn("Set the bank cutover date", str(error.exception))
        for wrong_method_line in (
            self.journal_ailos.eng_cnab_receipt_method_line_id,
            journal.outbound_payment_method_line_ids[:1],
        ):
            with self.assertRaises(ValidationError) as error:
                journal.eng_cnab_receipt_method_line_id = wrong_method_line
            self.assertIn(
                "must be one of its inbound payment methods", str(error.exception)
            )
        for clearing_account, message in (
            (journal.default_account_id, "cannot be its bank account"),
            (other_company_account, "must belong to the company"),
            (unreconcilable_account, "must allow reconciliation"),
        ):
            with self.assertRaises(ValidationError) as error:
                receipt_method_line.payment_account_id = clearing_account
                journal.eng_cnab_receipt_method_line_id = receipt_method_line
            self.assertIn(message, str(error.exception))

    def test_generic_parser_lookup_never_returns_the_clearing_parser(self):
        self.assertFalse(EngClearingCNABParser.parser_for("cnab400"))
        self.assertFalse(EngClearingCNABParser.parser_for("cnab240"))
        self.assertIs(type(new_move_parser(self.journal_bb)), CNABFileParser)


@tagged("post_install", "-at_install")
class TestPaymentBeforeCutover(CnabClearingCommon):
    def setUp(self):
        super().setUp()
        # The synthetic company has no chart template, so no default account
        self.debit_account = self._create_account(
            "ENGCC.ODB", "Synthetic Outstanding Receipts", "asset_current", True
        )
        self.credit_account = self._create_account(
            "ENGCC.OCR", "Synthetic Outstanding Payments", "asset_current", True
        )
        self.company.write(
            {
                "account_journal_payment_debit_account_id": self.debit_account.id,
                "account_journal_payment_credit_account_id": self.credit_account.id,
                "transfer_account_id": self._create_account(
                    "ENGCC.TRA", "Synthetic Transfers", "asset_current", True
                ).id,
            }
        )
        self.assertTrue(self.company.account_journal_payment_debit_account_id)
        self.partner.with_company(
            self.company
        ).property_account_payable_id = self._create_account(
            "ENGCC.PAY", "Synthetic Payable", "liability_payable", True
        )
        self.manual_method = self.journal_bb.inbound_payment_method_line_ids.filtered(
            lambda method_line: method_line.code == "manual"
        )
        self.manual_method.payment_account_id = self.account_clearing_bb
        self.before = CUTOVER_DATE - timedelta(days=1)

    def _payment_values(self, payment_date, **values):
        return {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": 100.0,
            "date": payment_date,
            "journal_id": self.journal_bb.id,
            "payment_method_line_id": self.manual_method.id,
            **values,
        }

    def _create_payment(self, payment_date, **values):
        return self.env["account.payment"].create(
            self._payment_values(payment_date, **values)
        )

    def _receive_payment(self, payment_date, **values):
        payment = self._create_payment(payment_date, **values)
        payment.action_post()
        return payment

    @staticmethod
    def _liquidity_line(payment):
        return payment._seek_for_lines()[0]

    def _assert_outstanding_account(self, payment, account):
        self.assertEqual(payment.outstanding_account_id, account)
        liquidity_line = self._liquidity_line(payment)
        self.assertEqual(len(liquidity_line), 1)
        self.assertEqual(liquidity_line.account_id, account)

    def test_receipt_before_cutover_goes_to_outstanding_account(self):
        payment = self._receive_payment(self.before)

        self._assert_outstanding_account(payment, self.debit_account)
        self.assertEqual(self._liquidity_line(payment).debit, 100.0)
        lines = payment.move_id.line_ids
        self.assertFalse(
            lines.filtered(lambda line: line.account_id == self.account_clearing_bb)
        )
        self.assertFalse(lines.filtered("eng_cnab_clearing"))

    def test_receipt_on_cutover_date_goes_to_clearing_account(self):
        payment = self._receive_payment(CUTOVER_DATE)

        self._assert_outstanding_account(payment, self.account_clearing_bb)
        self.assertFalse(self._liquidity_line(payment).eng_cnab_clearing)

    def test_outbound_payment_before_cutover_keeps_its_account(self):
        outbound_method = self.journal_bb.outbound_payment_method_line_ids.filtered(
            lambda method_line: method_line.code == "manual"
        )
        payment = self._receive_payment(
            self.before,
            payment_type="outbound",
            partner_type="supplier",
            payment_method_line_id=outbound_method.id,
        )

        self._assert_outstanding_account(payment, self.credit_account)

    def test_receipt_of_journal_out_of_flow_keeps_its_account(self):
        self.journal_bb.eng_cnab_clearing_enabled = False

        payment = self._receive_payment(self.before)

        self._assert_outstanding_account(payment, self.account_clearing_bb)

    def test_receipt_before_cutover_through_the_wizard_keeps_the_discount(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": self.before,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Synthetic product",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.account_income.id,
                            "tax_ids": [(5, 0, 0)],
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "journal_id": self.journal_bb.id,
                    "payment_method_line_id": self.manual_method.id,
                    "payment_date": self.before,
                    "amount": 90.0,
                    "payment_difference_handling": "reconcile",
                    "writeoff_account_id": self.account_discount.id,
                    "writeoff_label": "Discount",
                }
            )
        )

        payment = wizard._create_payments()

        self._assert_outstanding_account(payment, self.debit_account)
        lines = payment.move_id.line_ids
        self.assertEqual(self._liquidity_line(payment).debit, 90.0)
        self.assertEqual(
            lines.filtered(lambda line: line.account_id == self.account_discount).debit,
            10.0,
        )
        self.assertEqual(
            lines.filtered(
                lambda line: line.account_id == self.account_receivable
            ).credit,
            100.0,
        )
        self.assertEqual(invoice.amount_residual, 0.0)

    def test_draft_receipt_follows_its_date_across_the_cutover(self):
        payment = self._create_payment(CUTOVER_DATE)
        self._assert_outstanding_account(payment, self.account_clearing_bb)
        self.assertEqual(len(payment.move_id.line_ids), 2)

        payment.date = self.before
        self._assert_outstanding_account(payment, self.debit_account)
        self.assertEqual(len(payment.move_id.line_ids), 2)

        payment.date = CUTOVER_DATE
        self._assert_outstanding_account(payment, self.account_clearing_bb)
        self.assertEqual(len(payment.move_id.line_ids), 2)

    def test_receipt_before_cutover_in_another_account_stays_there(self):
        other_account = self._create_account(
            "ENGCC.OTH", "Synthetic Other Outstanding", "asset_current", True
        )
        self.manual_method.payment_account_id = other_account

        payment = self._receive_payment(self.before)

        self._assert_outstanding_account(payment, other_account)

    def test_changing_the_cutover_does_not_touch_posted_receipts(self):
        payment = self._receive_payment(CUTOVER_DATE)

        self.journal_bb.eng_bank_cutover_date = CUTOVER_DATE + timedelta(days=5)
        payment.flush_recordset()
        payment.invalidate_recordset()

        self.assertEqual(payment.state, "posted")
        self._assert_outstanding_account(payment, self.account_clearing_bb)

    def test_supplier_refund_before_cutover_goes_to_outstanding_account(self):
        before = self._receive_payment(self.before, partner_type="supplier")
        on_cutover = self._receive_payment(CUTOVER_DATE, partner_type="supplier")

        self._assert_outstanding_account(before, self.debit_account)
        self._assert_outstanding_account(on_cutover, self.account_clearing_bb)

    def test_internal_transfer_before_cutover(self):
        # The paired payment takes the default method line of the journal
        self.journal_bb.inbound_payment_method_line_ids.payment_account_id = (
            self.account_clearing_bb
        )
        plain_journal = self.env["account.journal"].create(
            {
                "name": "Synthetic plain bank",
                "code": "ECPLN",
                "type": "bank",
                "company_id": self.company.id,
                "default_account_id": self._create_account(
                    "ENGCC.PLN", "Synthetic Plain Bank", "asset_cash"
                ).id,
            }
        )
        outbound_method = plain_journal.outbound_payment_method_line_ids.filtered(
            lambda method_line: method_line.code == "manual"
        )

        def transfer(payment_date):
            payment = self.env["account.payment"].create(
                {
                    "payment_type": "outbound",
                    "is_internal_transfer": True,
                    "journal_id": plain_journal.id,
                    "destination_journal_id": self.journal_bb.id,
                    "payment_method_line_id": outbound_method.id,
                    "amount": 100.0,
                    "date": payment_date,
                }
            )
            payment.action_post()
            return payment.paired_internal_transfer_payment_id

        before = transfer(self.before)
        on_cutover = transfer(CUTOVER_DATE)

        for paired in before | on_cutover:
            self.assertEqual(paired.payment_type, "inbound")
            self.assertEqual(paired.journal_id, self.journal_bb)
            self.assertEqual(
                paired.payment_method_line_id.payment_account_id,
                self.account_clearing_bb,
            )
        self._assert_outstanding_account(before, self.debit_account)
        self._assert_outstanding_account(on_cutover, self.account_clearing_bb)

    def test_copy_follows_a_date_edited_on_the_copy(self):
        # The copy takes the lines of the original, and the method line is not
        # copied: it is the edit of the date that moves the line
        old_payment = self._receive_payment(self.before)
        new_payment = self._receive_payment(CUTOVER_DATE)
        self.assertEqual(
            self.manual_method.payment_account_id, self.account_clearing_bb
        )
        method_values = {"payment_method_line_id": self.manual_method.id}
        copy_on_cutover = old_payment.copy(method_values)
        copy_before = new_payment.copy(method_values)

        copy_on_cutover.date = CUTOVER_DATE
        copy_before.date = self.before

        self._assert_outstanding_account(copy_on_cutover, self.account_clearing_bb)
        self._assert_outstanding_account(copy_before, self.debit_account)

    def _legacy_account(self):
        return self._create_account(
            "ENGCC.LEG", "Synthetic Legacy Outstanding", "asset_current", True
        )

    def _assert_payment_stays_in(self, payment, account):
        self.assertEqual(payment.outstanding_account_id, account)
        self.assertEqual(len(payment.move_id.line_ids), 2)
        self.assertEqual(
            payment.move_id.line_ids.filtered(
                lambda line: line.account_id == account
            ).balance,
            payment.amount if payment.payment_type == "inbound" else -payment.amount,
        )

    def test_date_change_out_of_the_flow_keeps_the_legacy_account(self):
        legacy_account = self._legacy_account()
        self.journal_bb.eng_cnab_clearing_enabled = False
        self.manual_method.payment_account_id = legacy_account
        payment = self._receive_payment(CUTOVER_DATE)
        self.manual_method.payment_account_id = False

        payment.action_draft()
        payment.date = CUTOVER_DATE + timedelta(days=1)

        self._assert_payment_stays_in(payment, legacy_account)

    def test_date_change_of_an_outbound_payment_keeps_the_legacy_account(self):
        legacy_account = self._legacy_account()
        outbound_method = self.journal_bb.outbound_payment_method_line_ids.filtered(
            lambda method_line: method_line.code == "manual"
        )
        outbound_method.payment_account_id = legacy_account
        payment = self._receive_payment(
            CUTOVER_DATE,
            payment_type="outbound",
            partner_type="supplier",
            payment_method_line_id=outbound_method.id,
        )
        outbound_method.payment_account_id = False

        payment.action_draft()
        payment.date = self.before

        self._assert_payment_stays_in(payment, legacy_account)

    def test_date_change_in_the_flow_keeps_a_legacy_account(self):
        legacy_account = self._legacy_account()
        self.manual_method.payment_account_id = legacy_account
        payment = self._receive_payment(CUTOVER_DATE)
        self.manual_method.payment_account_id = self.account_clearing_bb

        payment.action_draft()
        payment.date = CUTOVER_DATE + timedelta(days=1)

        self._assert_payment_stays_in(payment, legacy_account)

    def test_date_changed_on_the_entry_keeps_field_and_line_together(self):
        # The date is corrected on the payment: on the entry, nothing follows it
        payment = self._create_payment(CUTOVER_DATE)

        payment.move_id.date = self.before

        self._assert_outstanding_account(payment, self.account_clearing_bb)

    def test_redraft_keeps_account_and_lines_of_an_old_payment(self):
        # Posted before the method was pointed to the clearing account
        self.manual_method.payment_account_id = False
        payment = self._receive_payment(CUTOVER_DATE)
        self._assert_outstanding_account(payment, self.debit_account)
        self.manual_method.payment_account_id = self.account_clearing_bb

        payment.action_draft()
        payment.action_post()

        self._assert_outstanding_account(payment, self.debit_account)

    def test_batch_create_decides_payment_by_payment(self):
        before, on_cutover = self.env["account.payment"].create(
            [self._payment_values(self.before), self._payment_values(CUTOVER_DATE)]
        )

        self._assert_outstanding_account(before, self.debit_account)
        self._assert_outstanding_account(on_cutover, self.account_clearing_bb)

    def test_default_account_comes_from_the_company_of_the_journal(self):
        other_company = self.env["res.company"].create(
            {"name": "Synthetic Other Company"}
        )
        self.env.user.write({"company_ids": [(4, other_company.id)]})
        other_account = self.env["account.account"].create(
            {
                "code": "ENGOT.ODB",
                "name": "Synthetic Other Outstanding Receipts",
                "account_type": "asset_current",
                "reconcile": True,
                "company_id": other_company.id,
            }
        )
        other_company.account_journal_payment_debit_account_id = other_account

        payment = (
            self.env["account.payment"]
            .with_context(allowed_company_ids=[other_company.id, self.company.id])
            .create(self._payment_values(self.before))
        )

        self.assertEqual(payment.outstanding_account_id, self.debit_account)
        self.assertNotEqual(payment.outstanding_account_id, other_account)

    def test_foreign_currency_receipt_before_cutover(self):
        currency = self.env.ref("base.EUR")
        currency.active = True
        self.env["res.currency.rate"].create(
            {
                "name": self.before,
                "rate": 2.0,
                "currency_id": currency.id,
                "company_id": self.company.id,
            }
        )

        payment = self._receive_payment(self.before, currency_id=currency.id)

        self._assert_outstanding_account(payment, self.debit_account)

    def test_receipt_before_cutover_without_default_account_is_refused(self):
        self.company.account_journal_payment_debit_account_id = False

        with self.assertRaises(UserError):
            self._create_payment(self.before)
