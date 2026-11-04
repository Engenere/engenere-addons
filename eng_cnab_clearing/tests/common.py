# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import copy
import json
from datetime import date
from unittest import mock

from odoo import Command
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_br_account_payment_brcobranca.parser.cnab_file_parser import (
    CNABFileParser,
)

INVOICE_DATE = date(2025, 10, 1)
DUE_DATE = date(2025, 10, 11)
OCCURRENCE_DATE = date(2025, 10, 30)
CREDIT_DATE = date(2025, 11, 3)
CUTOVER_DATE = date(2025, 11, 1)
FILE_NAME = "SYNTHETIC.RET"
# Each Ailos credit union is a branch of bank 085
AILOS_CREDIT_UNION = "000011"
OTHER_AILOS_CREDIT_UNION = "000022"


class CnabClearingCommon(TransactionCase):
    """Synthetic company, accounts, CNAB journals and posted installments.

    Self-sufficient on purpose: no chart template and no demo data. Only the
    BRCobranca API is simulated, with the JSON it returns for a return file;
    the import, the posting and the reconciliation run for real.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {"name": "Synthetic Clearing Company"}
        )
        cls.env.user.write({"company_ids": [Command.link(cls.company.id)]})
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                allowed_company_ids=[cls.company.id],
            )
        )

        cls.account_receivable = cls._create_account(
            "ENGCC.REC", "Synthetic Receivable", "asset_receivable", reconcile=True
        )
        cls.account_income = cls._create_account(
            "ENGCC.INC", "Synthetic Sales", "income"
        )
        cls.account_interest = cls._create_account(
            "ENGCC.INT", "Synthetic Interest Received", "income"
        )
        cls.account_discount = cls._create_account(
            "ENGCC.DSC", "Synthetic Discounts Granted", "expense"
        )
        cls.account_rebate = cls._create_account(
            "ENGCC.RBT", "Synthetic Rebates Granted", "expense"
        )
        cls.account_tariff = cls._create_account(
            "ENGCC.TRF", "Synthetic Bank Tariffs", "expense"
        )
        cls.account_bank_bb = cls._create_account(
            "ENGCC.BKB", "Synthetic Bank B", "asset_cash"
        )
        cls.account_bank_ailos = cls._create_account(
            "ENGCC.BKA", "Synthetic Bank A", "asset_cash"
        )
        cls.account_clearing_bb = cls._create_account(
            "ENGCC.CLB", "Synthetic Clearing B", "asset_current", reconcile=True
        )
        cls.account_clearing_ailos = cls._create_account(
            "ENGCC.CLA", "Synthetic Clearing A", "asset_current", reconcile=True
        )

        cls.partner = cls.env["res.partner"].create(
            {"name": "Synthetic Customer", "company_id": cls.company.id}
        )
        cls.partner.with_company(
            cls.company
        ).property_account_receivable_id = cls.account_receivable
        cls.journal_sale = cls.env["account.journal"].create(
            {
                "name": "Synthetic Sales",
                "code": "ECSAL",
                "type": "sale",
                "company_id": cls.company.id,
                "default_account_id": cls.account_income.id,
            }
        )

        cls.method_cnab400 = cls.env.ref(
            "l10n_br_account_payment_order.payment_mode_type_cnab400"
        )
        cls.method_cnab240 = cls.env.ref(
            "l10n_br_account_payment_order.payment_mode_type_cnab240"
        )
        cls.journal_bb = cls._create_cnab_journal(
            "ECBB",
            cls.env.ref("l10n_br_base.res_bank_001"),
            "90001",
            "cnab400",
            cls.method_cnab400,
            cls.account_bank_bb,
            cls.account_clearing_bb,
        )
        cls.journal_ailos = cls._create_cnab_journal(
            "ECAIL",
            cls.env.ref("l10n_br_base.res_bank_085"),
            "90002",
            "cnab240",
            cls.method_cnab240,
            cls.account_bank_ailos,
            cls.account_clearing_ailos,
        )
        payment_mode_bb = cls._create_payment_mode(
            cls.journal_bb,
            cls.method_cnab400,
            "l10n_br_account_payment_order.brasil_400_return_06",
        )
        payment_mode_ailos = cls._create_payment_mode(
            cls.journal_ailos,
            cls.method_cnab240,
            "l10n_br_account_payment_order.ailos_240_return_06",
        )
        cls.installment_bb = cls._create_installment(payment_mode_bb)
        cls.installment_bb_2 = cls._create_installment(payment_mode_bb)
        cls.installment_ailos = cls._create_installment(payment_mode_ailos)
        cls.installment_ailos_2 = cls._create_installment(payment_mode_ailos)

    @classmethod
    def _create_account(cls, code, name, account_type, reconcile=False):
        return cls.env["account.account"].create(
            {
                "code": code,
                "name": name,
                "account_type": account_type,
                "reconcile": reconcile,
                "company_id": cls.company.id,
            }
        )

    @classmethod
    def _create_cnab_journal(
        cls,
        code,
        bank,
        acc_number,
        import_type,
        cnab_method,
        bank_account,
        clearing_account,
    ):
        partner_bank = cls.env["res.partner.bank"].create(
            {
                "acc_number": acc_number,
                "acc_number_dig": "0",
                "bra_number": "1234",
                "bra_number_dig": "0",
                "bank_id": bank.id,
                "partner_id": cls.company.partner_id.id,
            }
        )
        journal = cls.env["account.journal"].create(
            {
                "name": f"Synthetic {code} Journal",
                "code": code,
                "type": "bank",
                "company_id": cls.company.id,
                "default_account_id": bank_account.id,
                "bank_account_id": partner_bank.id,
                "used_for_import": True,
                "import_type": import_type,
                "return_auto_reconcile": True,
            }
        )
        # account_payment_mode gives every new bank journal one line per
        # inbound payment method, the CNAB ones included
        receipt_method_line = journal.inbound_payment_method_line_ids.filtered(
            lambda method_line: method_line.payment_method_id == cnab_method
        )
        receipt_method_line.payment_account_id = clearing_account
        journal.write(
            {
                "eng_cnab_clearing_enabled": True,
                "eng_bank_cutover_date": CUTOVER_DATE,
                "eng_cnab_receipt_method_line_id": receipt_method_line.id,
            }
        )
        return journal

    @classmethod
    def _create_payment_mode(cls, journal, cnab_method, liquidation_code_xmlid):
        own_number_sequence = cls.env["ir.sequence"].create(
            {
                "name": f"Synthetic {journal.code} own number",
                "implementation": "no_gap",
                "padding": 0,
                "company_id": cls.company.id,
            }
        )
        cnab_config = cls.env["l10n_br_cnab.config"].create(
            {
                "name": f"Synthetic {journal.code} CNAB",
                "company_id": cls.company.id,
                "bank_id": journal.bank_account_id.bank_id.id,
                "payment_method_id": cnab_method.id,
                "cnab_processor": "brcobranca",
                "own_number_sequence_id": own_number_sequence.id,
                "generate_own_number": True,
                "interest_fee_account_id": cls.account_interest.id,
                "discount_account_id": cls.account_discount.id,
                "rebate_account_id": cls.account_rebate.id,
                "tariff_charge_account_id": cls.account_tariff.id,
                "liq_return_move_code_ids": [
                    Command.set(cls.env.ref(liquidation_code_xmlid).ids)
                ],
            }
        )
        return cls.env["account.payment.mode"].create(
            {
                "name": f"Synthetic {journal.code} Collection",
                "company_id": cls.company.id,
                "bank_account_link": "fixed",
                "fixed_journal_id": journal.id,
                "payment_method_id": cnab_method.id,
                "payment_order_ok": True,
                "auto_create_payment_order": False,
                "group_lines": False,
                "cnab_config_id": cnab_config.id,
            }
        )

    @classmethod
    def _create_installment(cls, payment_mode):
        """Post a customer invoice of 100 and return its installment line."""
        invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.partner.id,
                "journal_id": cls.journal_sale.id,
                "invoice_date": INVOICE_DATE,
                "invoice_date_due": DUE_DATE,
                "payment_mode_id": payment_mode.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Synthetic product",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": cls.account_income.id,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )

    # Synthetic records, as returned by the BRCobranca API

    @staticmethod
    def _cnab_amount(amount, width):
        return str(round(amount * 100)).zfill(width)

    def _bb_record(
        self,
        installment,
        received=100.0,
        interest=0.0,
        discount=0.0,
        rebate=0.0,
        tariff=0.0,
        **values,
    ):
        """Detail record of a Banco do Brasil CNAB 400 return."""
        record = {
            "codigo_registro": "7",
            "nosso_numero": "7654321" + installment.own_number.zfill(10),
            "documento_numero": installment.document_number,
            "codigo_ocorrencia": "06",
            "data_ocorrencia": OCCURRENCE_DATE.strftime("%d%m%y"),
            "data_credito": CREDIT_DATE.strftime("%d%m%y"),
            "data_vencimento": DUE_DATE.strftime("%d%m%y"),
            "valor_titulo": self._cnab_amount(100.0, 13),
            "valor_recebido": self._cnab_amount(received, 13),
            "juros_mora": self._cnab_amount(interest, 13),
            "desconto": self._cnab_amount(discount, 13),
            "desconto_concedito": None,
            "valor_abatimento": self._cnab_amount(rebate, 13),
            "valor_tarifa": self._cnab_amount(tariff, 7),
            "banco_recebedor": "001",
        }
        record.update(values)
        return record

    @staticmethod
    def _bb_trailer():
        """Trailer of a Banco do Brasil CNAB 400 return, not a detail record.

        The BRCobranca API skips the header of the file but returns the
        trailer, with the fields of a detail record read from its positions.
        """
        return {"codigo_registro": "9", "nosso_numero": None}

    def _ailos_record(self, installment, received=100.0, tariff=0.0, **values):
        """Detail record (segments T and U) of an Ailos CNAB 240 return."""
        record = {
            "codigo_registro": "3",
            "nosso_numero": installment.own_number.zfill(20),
            "documento_numero": None,
            "codigo_ocorrencia": "06",
            "data_ocorrencia": OCCURRENCE_DATE.strftime("%d%m%Y"),
            "data_credito": CREDIT_DATE.strftime("%d%m%Y"),
            "data_vencimento": DUE_DATE.strftime("%d%m%Y"),
            "valor_titulo": self._cnab_amount(100.0, 15),
            "valor_recebido": self._cnab_amount(received, 15),
            "juros_mora": self._cnab_amount(0.0, 15),
            "desconto": None,
            "desconto_concedito": self._cnab_amount(0.0, 15),
            "valor_abatimento": self._cnab_amount(0.0, 15),
            "valor_tarifa": self._cnab_amount(tariff, 15),
            "banco_recebedor": "085",
            "agencia_com_dv": AILOS_CREDIT_UNION,
            "agencia_recebedora_com_dv": AILOS_CREDIT_UNION,
        }
        record.update(values)
        return record

    # Import helpers

    @staticmethod
    def _file_content(records):
        """Synthetic return file: one distinct content per list of records."""
        return json.dumps(records, sort_keys=True).encode()

    @staticmethod
    def _mock_brcobranca(records):
        return mock.patch.object(
            CNABFileParser,
            "_get_brcobranca_retorno",
            return_value=copy.deepcopy(records),
        )

    def _run_import(self, journal, records):
        """Import the file of records, with the API already simulated."""
        return journal.with_context(file_name=FILE_NAME).multi_move_import(
            base64.b64encode(self._file_content(records)), "RET"
        )

    def _import(self, journal, records):
        with self._mock_brcobranca(records):
            return self._run_import(journal, records)

    def _count_import_records(self):
        return {
            "logs": self.env["l10n_br_cnab.return.log"].search_count([]),
            "attachments": self.env["ir.attachment"].search_count(
                [("res_model", "=", "l10n_br_cnab.return.log")]
            ),
            "events": self.env["l10n_br_cnab.return.event"].search_count([]),
            "moves": self.env["account.move"].search_count([]),
        }

    def _set_lock_date(self, lock_date):
        # Both dates: the user lock date of an accounting manager is the
        # fiscal year one, the period one applies to everyone else
        self.company.write(
            {"period_lock_date": lock_date, "fiscalyear_lock_date": lock_date}
        )

    @staticmethod
    def _amounts_by_account(move):
        amounts = {}
        for line in move.line_ids:
            debit, credit = amounts.get(line.account_id, (0.0, 0.0))
            amounts[line.account_id] = (debit + line.debit, credit + line.credit)
        return amounts

    @staticmethod
    def _clearing_line(move):
        return move.line_ids.filtered("eng_cnab_clearing")
