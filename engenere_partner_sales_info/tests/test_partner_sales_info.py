# test_partner_sales_info.py
# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import common


class TestPartnerSalesInfo(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner_model = self.env["res.partner"]
        self.sale_model = self.env["sale.order"]
        self.invoice_model = self.env["account.move"]
        self.config_param = self.env["ir.config_parameter"].sudo()

        # Criar contas contábeis necessárias
        self.account_receivable = self.env["account.account"].create(
            {
                "name": "Test Receivable Account",
                "code": "TREC",
                "user_type_id": self.env.ref("account.data_account_type_receivable").id,
                "reconcile": True,
                "company_id": self.env.company.id,
            }
        )

        self.account_income = self.env["account.account"].create(
            {
                "name": "Test Income Account",
                "code": "TIN",
                "user_type_id": self.env.ref("account.data_account_type_revenue").id,
                "company_id": self.env.company.id,
            }
        )

        # Configurar diário de vendas
        self.sale_journal = self.env["account.journal"].create(
            {
                "name": "Test Sale Journal",
                "type": "sale",
                "code": "TSJ",
                "company_id": self.env.company.id,
                "default_account_id": self.account_income.id,
            }
        )

        # Configurar parceiro com conta a receber
        self.customer_partner = self.partner_model.create(
            {
                "name": "Test Customer",
                "customer_rank": 1,
                "property_account_receivable_id": self.account_receivable.id,
            }
        )

        # Configurar parâmetro de meses de análise
        self.config_param.set_param(
            "engenere_partner_sales_info.default_analysis_months", 12
        )

    def test_no_sales_no_invoices(self):
        self.customer_partner._compute_sales_info()
        self.assertFalse(self.customer_partner.last_order_date)
        self.assertFalse(self.customer_partner.last_order_status)
        self.assertFalse(self.customer_partner.last_invoice_date)
        self.assertEqual(self.customer_partner.invoice_count, 0)
        self.assertEqual(self.customer_partner.total_invoiced, 0)
        self.assertEqual(self.customer_partner.average_invoiced, 0)
        self.assertEqual(self.customer_partner.average_invoiced_no_discrepancies, 0)
        self.assertEqual(self.customer_partner.average_time_between_invoices, 0)
        self.assertFalse(self.customer_partner.last_invoice_id)

    def test_with_sales(self):
        order_vals = {
            "partner_id": self.customer_partner.id,
            "date_order": fields.Datetime.now() - relativedelta(days=2),
            "state": "sale",
        }
        so = self.sale_model.create(order_vals)
        self.customer_partner._compute_sales_info()
        self.assertEqual(self.customer_partner.last_order_date, so.date_order.date())
        self.assertEqual(self.customer_partner.last_order_status, so.state)

    def test_with_invoices(self):
        self._create_invoice(self.customer_partner, 100, days_diff=10)
        inv = self._create_invoice(self.customer_partner, 200, days_diff=5)
        self.customer_partner._compute_sales_info()
        self.assertEqual(self.customer_partner.invoice_count, 2)
        self.assertAlmostEqual(self.customer_partner.total_invoiced, 300)
        self.assertAlmostEqual(self.customer_partner.average_invoiced, 150)
        self.assertEqual(self.customer_partner.last_invoice_id, inv)
        self.assertEqual(self.customer_partner.last_invoice_date, inv.invoice_date)

    def test_with_invoices_and_outliers(self):
        self._create_invoice(self.customer_partner, 100, days_diff=12)
        self._create_invoice(self.customer_partner, 110, days_diff=8)
        self._create_invoice(self.customer_partner, 120, days_diff=4)
        self._create_invoice(self.customer_partner, 10000, days_diff=1)

        self.customer_partner._compute_sales_info()
        self.assertEqual(self.customer_partner.invoice_count, 4)
        total_expected = 100 + 110 + 120 + 10000
        self.assertAlmostEqual(self.customer_partner.total_invoiced, total_expected)
        self.assertTrue(
            self.customer_partner.average_invoiced > 100
            and self.customer_partner.average_invoiced < total_expected
        )
        self.assertTrue(self.customer_partner.average_invoiced_no_discrepancies < 1000)

    def _create_invoice(self, partner, amount, days_diff=0):
        inv_date = fields.Date.today() - relativedelta(days=days_diff)
        invoice = self.invoice_model.create(
            {
                "partner_id": partner.id,
                "move_type": "out_invoice",
                "invoice_date": inv_date,
                "journal_id": self.sale_journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test Line",
                            "quantity": 1,
                            "price_unit": amount,
                            "account_id": self.account_income.id,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice
