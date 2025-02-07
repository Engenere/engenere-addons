from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestPartnerSalesInfo(AccountTestInvoicingCommon):
    def setUp(self):
        super().setUp()
        self.partner_model = self.env["res.partner"]
        self.sale_model = self.env["sale.order"]
        self.invoice_model = self.env["account.move"]
        self.config_param = self.env["ir.config_parameter"].sudo()

        self.account_receivable = self.company_data["default_account_receivable"]
        self.account_income = self.company_data["default_account_revenue"]
        self.sale_journal = self.company_data["default_journal_sale"]
        self.customer_partner = self.partner_model.create(
            {
                "name": "Test Customer",
                "customer_rank": 1,
                "property_account_receivable_id": self.account_receivable.id,
            }
        )

        # Define meses de análise
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
        # Check last_order_id as well
        self.assertEqual(self.customer_partner.last_order_id, so)

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
            100 < self.customer_partner.average_invoiced < total_expected,
            "Average invoiced should be between normal invoice amounts and total.",
        )
        self.assertTrue(
            self.customer_partner.average_invoiced_no_discrepancies < 1000,
            "Filtered average should exclude the large outlier.",
        )

    def test_days_since_last_invoice(self):
        # First invoice, 10 days ago
        self._create_invoice(self.customer_partner, 150, days_diff=10)
        self.customer_partner._compute_sales_info()
        self.assertEqual(
            self.customer_partner.days_since_last_invoice,
            10,
            "days_since_last_invoice should match the 10 days old invoice",
        )

        # Newer invoice, 3 days ago
        inv2 = self._create_invoice(self.customer_partner, 300, days_diff=3)
        self.customer_partner._compute_sales_info()
        self.assertEqual(
            self.customer_partner.days_since_last_invoice,
            3,
            "days_since_last_invoice should be updated to match the newer invoice",
        )

        self.assertEqual(self.customer_partner.last_invoice_id, inv2)
        self.assertEqual(self.customer_partner.last_invoice_date, inv2.invoice_date)

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
