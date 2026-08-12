# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class ChartlessAccountCommon(TransactionCase):
    """Self-sufficient accounting fixtures.

    Creates the minimal chart bits (accounts, journals, partner
    properties, outstanding payment accounts) instead of relying on a
    demo chart of accounts: the BR localization demo chain does not
    install on isolated databases, so these tests must not depend on it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("base.main_company")

        Account = cls.env["account.account"]
        cls.account_expense = Account.create(
            {
                "name": "Test Expenses",
                "code": "ENGT.EXP",
                "account_type": "expense",
                "company_id": cls.company.id,
            }
        )
        cls.account_income = Account.create(
            {
                "name": "Test Income",
                "code": "ENGT.INC",
                "account_type": "income",
                "company_id": cls.company.id,
            }
        )
        cls.account_receivable = Account.create(
            {
                "name": "Test Receivable",
                "code": "ENGT.REC",
                "account_type": "asset_receivable",
                "reconcile": True,
                "company_id": cls.company.id,
            }
        )
        cls.account_payable = Account.create(
            {
                "name": "Test Payable",
                "code": "ENGT.PAY",
                "account_type": "liability_payable",
                "reconcile": True,
                "company_id": cls.company.id,
            }
        )
        cls.account_bank = Account.create(
            {
                "name": "Test Bank",
                "code": "ENGT.BNK",
                "account_type": "asset_cash",
                "company_id": cls.company.id,
            }
        )
        cls.account_outstanding_in = Account.create(
            {
                "name": "Test Outstanding Receipts",
                "code": "ENGT.OSR",
                "account_type": "asset_current",
                "reconcile": True,
                "company_id": cls.company.id,
            }
        )
        cls.account_outstanding_out = Account.create(
            {
                "name": "Test Outstanding Payments",
                "code": "ENGT.OSP",
                "account_type": "asset_current",
                "reconcile": True,
                "company_id": cls.company.id,
            }
        )

        Journal = cls.env["account.journal"]
        cls.journal_sale = Journal.create(
            {
                "name": "Test Sales Journal",
                "code": "TSAL",
                "type": "sale",
                "company_id": cls.company.id,
                "default_account_id": cls.account_income.id,
            }
        )
        cls.journal_purchase = Journal.create(
            {
                "name": "Test Purchases Journal",
                "code": "TPUR",
                "type": "purchase",
                "company_id": cls.company.id,
                "default_account_id": cls.account_expense.id,
            }
        )
        cls.journal_bank = Journal.create(
            {
                "name": "Test Bank Journal",
                "code": "TBNK",
                "type": "bank",
                "company_id": cls.company.id,
                "default_account_id": cls.account_bank.id,
            }
        )
        cls.company.write(
            {
                "account_journal_payment_debit_account_id": (
                    cls.account_outstanding_in.id
                ),
                "account_journal_payment_credit_account_id": (
                    cls.account_outstanding_out.id
                ),
            }
        )

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "company_id": cls.company.id,
            }
        )
        partner_in_company = cls.partner.with_company(cls.company)
        partner_in_company.property_account_receivable_id = cls.account_receivable
        partner_in_company.property_account_payable_id = cls.account_payable

    @classmethod
    def _journal_for(cls, move_type):
        return (
            cls.journal_purchase
            if move_type in ("in_invoice", "in_receipt")
            else cls.journal_sale
        )
