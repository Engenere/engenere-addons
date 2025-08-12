from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestPartnerSalesInfo(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.sale_model = cls.env["sale.order"]
        cls.invoice_model = cls.env["account.move"]
        cls.config_param = cls.env["ir.config_parameter"].sudo()

        cls.account_receivable = cls.company_data["default_account_receivable"]
        cls.account_income = cls.company_data["default_account_revenue"]
        cls.sale_journal = cls.company_data["default_journal_sale"]

        cls.customer_partner = cls.partner_model.create(
            {
                "name": "Test Customer",
                "customer_rank": 1,
                "property_account_receivable_id": cls.account_receivable.id,
            }
        )

        cls.config_param.set_param("eng_partner_sales_info.default_analysis_months", 12)

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
        self.assertEqual(self.customer_partner.last_order_id, so)

    def test_with_invoices(self):
        self._create_invoice(self.customer_partner, 100, days_diff=10)
        inv = self._create_invoice(self.customer_partner, 200, days_diff=5)
        self.customer_partner._compute_sales_info()
        self.assertEqual(self.customer_partner.invoice_count, 2)
        self.assertAlmostEqual(self.customer_partner.total_invoiced, 345)
        self.assertAlmostEqual(self.customer_partner.average_invoiced, 172.5)
        self.assertEqual(self.customer_partner.last_invoice_id, inv)
        self.assertEqual(self.customer_partner.last_invoice_date, inv.invoice_date)

    def test_with_invoices_and_outliers(self):
        self._create_invoice(self.customer_partner, 100, days_diff=12)
        self._create_invoice(self.customer_partner, 110, days_diff=8)
        self._create_invoice(self.customer_partner, 120, days_diff=4)
        self._create_invoice(self.customer_partner, 10000, days_diff=1)
        self.customer_partner._compute_sales_info()
        self.assertEqual(self.customer_partner.invoice_count, 4)
        self.assertEqual(self.customer_partner.total_invoiced, 11879.5)
        self.assertEqual(self.customer_partner.average_invoiced, 2969.88)
        self.assertEqual(self.customer_partner.average_invoiced_no_discrepancies, 126.5)

    def test_days_since_last_invoice(self):
        self._create_invoice(self.customer_partner, 150, days_diff=10)
        self.customer_partner._compute_sales_info()
        self.assertEqual(self.customer_partner.days_since_last_invoice, 10)
        inv2 = self._create_invoice(self.customer_partner, 300, days_diff=3)
        self.customer_partner._compute_sales_info()
        self.assertEqual(self.customer_partner.days_since_last_invoice, 3)
        self.assertEqual(self.customer_partner.last_invoice_id, inv2)
        self.assertEqual(self.customer_partner.last_invoice_date, inv2.invoice_date)

    def test_open_quotation_fields_no_quotations(self):
        self.customer_partner._compute_open_quotation_info()
        self.assertFalse(self.customer_partner.has_open_quotation)
        self.assertFalse(self.customer_partner.last_open_quotation_id)
        self.assertFalse(self.customer_partner.last_open_quotation_date)

    def test_open_quotation_with_draft(self):
        quotation = self._create_quotation(state="draft", days_diff=2)
        self.customer_partner._compute_open_quotation_info()
        self.assertTrue(self.customer_partner.has_open_quotation)
        self.assertEqual(self.customer_partner.last_open_quotation_id, quotation)
        self.assertEqual(
            self.customer_partner.last_open_quotation_date, quotation.date_order.date()
        )

    def test_open_quotation_with_sent_state(self):
        quotation = self._create_quotation(state="sent", days_diff=1)
        self.customer_partner._compute_open_quotation_info()
        self.assertTrue(self.customer_partner.has_open_quotation)
        self.assertEqual(self.customer_partner.last_open_quotation_id, quotation)

    def test_multiple_open_quotations(self):
        old_quotation = self._create_quotation(state="draft", days_diff=5)
        new_quotation = self._create_quotation(state="sent", days_diff=2)
        self.customer_partner._compute_open_quotation_info()
        self.assertEqual(self.customer_partner.last_open_quotation_id, new_quotation)
        self.assertEqual(
            self.customer_partner.last_open_quotation_date,
            new_quotation.date_order.date(),
        )
        self.assertNotEqual(old_quotation, self.customer_partner.last_open_quotation_id)

    def test_quotation_confirmed_state(self):
        quotation = self._create_quotation(state="draft", days_diff=1)
        quotation.action_confirm()
        self.customer_partner._compute_open_quotation_info()
        self.assertFalse(self.customer_partner.has_open_quotation)
        self.assertFalse(self.customer_partner.last_open_quotation_id)

    def test_quotation_cancelled_state(self):
        quotation = self._create_quotation(state="draft", days_diff=1)
        quotation.action_cancel()
        self.customer_partner._compute_open_quotation_info()
        self.assertFalse(self.customer_partner.has_open_quotation)
        self.assertFalse(self.customer_partner.last_open_quotation_id)

    def test_mixed_quotation_states(self):
        self._create_quotation(state="draft", days_diff=5)
        confirmed = self._create_quotation(state="draft", days_diff=4)
        confirmed.action_confirm()
        cancelled = self._create_quotation(state="sent", days_diff=3)
        cancelled.action_cancel()
        valid_quotation = self._create_quotation(state="sent", days_diff=1)
        self.customer_partner._compute_open_quotation_info()
        self.assertTrue(self.customer_partner.has_open_quotation)
        self.assertEqual(self.customer_partner.last_open_quotation_id, valid_quotation)

    def test_quotation_date_consistency(self):
        quotation = self._create_quotation(state="draft", days_diff=3)
        self.customer_partner._compute_open_quotation_info()
        self.assertEqual(
            self.customer_partner.last_open_quotation_date, quotation.date_order.date()
        )
        new_date = fields.Date.today() - relativedelta(days=3)
        quotation.write({"date_order": new_date})
        self.customer_partner._compute_open_quotation_info()
        self.assertEqual(self.customer_partner.last_open_quotation_date, new_date)

    def test_partner_not_customer(self):
        """Partner with customer_rank = 0 should reset all related fields."""
        partner_no_customer = self.partner_model.create(
            {
                "name": "No Customer",
                "customer_rank": 0,
                "property_account_receivable_id": self.account_receivable.id,
            }
        )
        self._create_invoice(partner_no_customer, 500, days_diff=5, post=False)
        partner_no_customer._compute_sales_info()
        self.assertFalse(partner_no_customer.last_order_id)
        self.assertFalse(partner_no_customer.last_invoice_id)
        self.assertEqual(partner_no_customer.invoice_count, 0)
        self.assertEqual(partner_no_customer.total_invoiced, 0)

    def test_invoice_out_of_analysis_range(self):
        """Invoices older than analysis_months should not affect stats."""
        # 12 months configured, invoice 400 days old
        self._create_invoice(self.customer_partner, 100, days_diff=400)
        self.customer_partner._compute_sales_info()
        self.assertFalse(self.customer_partner.last_invoice_date)
        self.assertEqual(self.customer_partner.invoice_count, 0)
        self.assertEqual(self.customer_partner.total_invoiced, 0)

    def test_sale_out_of_analysis_range(self):
        """Sales older than analysis_months should not affect stats."""
        self.sale_model.create(
            {
                "partner_id": self.customer_partner.id,
                "date_order": fields.Datetime.now() - relativedelta(days=400),
                "state": "sale",
            }
        )
        self.customer_partner._compute_sales_info()
        self.assertFalse(self.customer_partner.last_order_date)
        self.assertEqual(self.customer_partner.order_count, 0)
        self.assertEqual(self.customer_partner.total_ordered, 0)

    def test_analysis_months_zero_or_negative(self):
        """If analysis months is 0 or negative, no records should be included."""
        self.config_param.set_param(
            "eng_partner_sales_info.default_analysis_months", -1
        )
        self._create_invoice(self.customer_partner, 100, days_diff=1)
        self.customer_partner._compute_sales_info()
        self.assertFalse(self.customer_partner.last_invoice_date)
        self.assertEqual(self.customer_partner.invoice_count, 0)
        self.assertEqual(self.customer_partner.total_invoiced, 0)

        self.config_param.set_param("eng_partner_sales_info.default_analysis_months", 0)
        self.customer_partner._compute_sales_info()
        self.assertFalse(self.customer_partner.last_invoice_date)
        self.assertEqual(self.customer_partner.invoice_count, 0)
        self.assertEqual(self.customer_partner.total_invoiced, 0)

    def test_analysis_message(self):
        """Check if analysis_message is set correctly."""
        # default_analysis_months = 12
        self.customer_partner._compute_analysis_message()
        self.assertIn(
            "Analysis period: 12 months", self.customer_partner.analysis_message
        )

        self.config_param.set_param(
            "eng_partner_sales_info.default_analysis_months", 24
        )
        self.customer_partner._compute_analysis_message()
        self.assertIn(
            "Analysis period: 24 months", self.customer_partner.analysis_message
        )

    def _create_quotation(self, state="draft", days_diff=0):
        date_order = fields.Datetime.now() - relativedelta(days=days_diff)
        return self.sale_model.create(
            {
                "partner_id": self.customer_partner.id,
                "state": state,
                "date_order": date_order,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.env.ref("product.product_product_4").id,
                            "product_uom_qty": 1,
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )

    def _create_invoice(self, partner, amount, days_diff=0, post=True):
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
        if post:
            invoice.action_post()
        return invoice
