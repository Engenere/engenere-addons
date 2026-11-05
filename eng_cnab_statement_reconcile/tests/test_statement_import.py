# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import copy
from datetime import datetime, time, timedelta
from unittest import mock

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.misc import format_date

from odoo.addons.eng_cnab_clearing.tests.common import CREDIT_DATE, CUTOVER_DATE

from .common import CnabStatementReconcileCommon


@tagged("post_install", "-at_install")
class TestStatementImport(CnabStatementReconcileCommon):
    """Import of a bank statement file of the bank B journal.

    Only the file format is simulated, as the OFX format module provides
    it: the format the journals offer and the reading of the file, with the
    transactions an OFX file of the bank would give. The import itself
    (journal lookup, transaction ids, duplicates, statements and lines) runs
    for real.
    """

    def setUp(self):
        super().setUp()
        # For the whole test, up to the flush of the journal source that the
        # import sets: without a format, the file import is no valid source
        self.startPatcher(
            mock.patch.object(
                type(self.journal_bb),
                "_get_bank_statements_available_import_formats",
                return_value=["OFX"],
            )
        )

    def _import_statement(self, transactions):
        wizard = self.env["account.statement.import"].create(
            {
                "statement_file": base64.b64encode(b"SYNTHETIC STATEMENT FILE"),
                "statement_filename": "SYNTHETIC.OFX",
            }
        )
        parsed_file = [
            (
                self.company.currency_id.name,
                self.journal_bb.bank_account_id.acc_number,
                [
                    {
                        "name": "SYNTHETIC STATEMENT",
                        "date": CREDIT_DATE,
                        "transactions": copy.deepcopy(transactions),
                    }
                ],
            )
        ]
        with mock.patch.object(type(wizard), "_parse_file", return_value=parsed_file):
            return wizard._import_file()

    def _journal_st_lines(self):
        return self.env["account.bank.statement.line"].search(
            [("journal_id", "=", self.journal_bb.id)]
        )

    # Plan, test 28
    def test_transaction_id_imported_again_with_the_same_content_is_skipped(self):
        transfer = {
            "payment_ref": "TRANSFER RECEIVED",
            "date": CREDIT_DATE,
            "amount": 100.0,
            "unique_import_id": "SYNTHETIC-FITID-1",
        }
        self._import_statement(
            [
                transfer,
                # A format without transaction ids: never taken as a duplicate
                {"payment_ref": "TRANSFER SENT", "date": CREDIT_DATE, "amount": -2.0},
            ]
        )

        result = self._import_statement(
            [
                transfer,
                {"payment_ref": "TRANSFER SENT", "date": CREDIT_DATE, "amount": -2.0},
                {
                    "payment_ref": "TRANSFER RECEIVED AGAIN",
                    "date": CREDIT_DATE,
                    "amount": 30.0,
                    "unique_import_id": "SYNTHETIC-FITID-2",
                },
            ]
        )

        st_lines = self._journal_st_lines()
        self.assertEqual(
            sorted(st_lines.mapped("payment_ref")),
            [
                "TRANSFER RECEIVED",
                "TRANSFER RECEIVED AGAIN",
                "TRANSFER SENT",
                "TRANSFER SENT",
            ],
        )
        self.assertEqual(
            len(
                st_lines.filtered(
                    lambda line: (line.unique_import_id or "").endswith(
                        "-SYNTHETIC-FITID-1"
                    )
                )
            ),
            1,
        )
        self.assertIn(
            "1 transaction had already been imported and was ignored.",
            result["notifications"],
        )

    # Plan, test 29
    def test_transaction_id_imported_again_with_another_content_is_a_conflict(self):
        transfer = {
            "payment_ref": "TRANSFER RECEIVED",
            "date": CREDIT_DATE,
            "amount": 100.0,
            "unique_import_id": "SYNTHETIC-FITID-1",
        }
        self._import_statement([transfer])
        st_lines = self._journal_st_lines()
        statements = st_lines.statement_id

        for changed_values in (
            {"amount": 120.0},
            {"date": CREDIT_DATE + timedelta(days=1)},
        ):
            with self.assertRaises(UserError) as error:
                self._import_statement(
                    [
                        dict(transfer, **changed_values),
                        {
                            "payment_ref": "TRANSFER RECEIVED AGAIN",
                            "date": CREDIT_DATE,
                            "amount": 30.0,
                            "unique_import_id": "SYNTHETIC-FITID-2",
                        },
                    ]
                )
            message = str(error.exception)
            self.assertIn("same identifier but another date or amount", message)
            self.assertIn("SYNTHETIC-FITID-1", message)
            self.assertNotIn("SYNTHETIC-FITID-2", message)

        # The whole file is refused: nothing new, nothing changed
        self.assertEqual(self._journal_st_lines(), st_lines)
        self.assertEqual(self._journal_st_lines().statement_id, statements)
        self.assertEqual((st_lines.amount, st_lines.date), (100.0, CREDIT_DATE))

    @staticmethod
    def _transaction(line_date, fitid, amount=30.0):
        """A transaction as the OFX format gives it, dated with a datetime."""
        return {
            "payment_ref": f"TRANSFER {fitid}",
            "date": datetime.combine(line_date, time()),
            "amount": amount,
            "unique_import_id": fitid,
        }

    def test_file_with_lines_before_the_cutover_is_refused_whole(self):
        day_before = CUTOVER_DATE - timedelta(days=1)
        two_days_before = CUTOVER_DATE - timedelta(days=2)

        with self.assertRaises(UserError) as error:
            self._import_statement(
                [
                    self._transaction(CREDIT_DATE, "SYNTHETIC-FITID-1"),
                    self._transaction(day_before, "SYNTHETIC-FITID-2"),
                    self._transaction(two_days_before, "SYNTHETIC-FITID-3"),
                ]
            )

        message = str(error.exception)
        self.assertIn("SYNTHETIC.OFX", message)
        self.assertIn("it has lines dated before", message)
        self.assertIn("number of lines: 2", message)
        self.assertIn(format_date(self.env, CUTOVER_DATE), message)
        self.assertIn(self.journal_bb.display_name, message)
        self.assertIn(f"first date: {format_date(self.env, two_days_before)}", message)
        self.assertFalse(self._journal_st_lines())

    def test_file_with_lines_from_the_cutover_date_on_is_imported(self):
        self._import_statement(
            [
                self._transaction(CUTOVER_DATE, "SYNTHETIC-FITID-1"),
                self._transaction(CREDIT_DATE, "SYNTHETIC-FITID-2"),
            ]
        )

        self.assertEqual(len(self._journal_st_lines()), 2)

    def test_file_before_the_cutover_date_is_imported_without_the_flow(self):
        self.journal_bb.eng_cnab_clearing_enabled = False

        self._import_statement(
            [self._transaction(CUTOVER_DATE - timedelta(days=1), "SYNTHETIC-FITID-1")]
        )

        self.assertEqual(len(self._journal_st_lines()), 1)
