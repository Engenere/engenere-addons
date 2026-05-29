from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestFaturistaInvoicePost(AccountTestInvoicingCommon):
    """The picking lockdown turns stock.picking/move/move.line read-only for
    the invoicing role. This must NOT bleed into the invoicing flow: a
    faturista (and Bruna's full multi-hat stack) has to keep posting customer
    invoices for stockable products without hitting an AccessError on stock.

    The Trento companies run manual/periodic valuation (anglo_saxon=False), so
    posting a customer invoice never touches stock.valuation.layer — this test
    locks that invariant against a regression in the lockdown ACLs. (Real-time
    valuation would route the post through stock.valuation.layer, which needs a
    stock role; that configuration is out of scope by decision.)
    """

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.company = cls.company_data["company"]
        cls.stockable = cls.env["product.product"].create(
            {
                "name": "Stockable Invoiceable",
                "type": "product",
                "invoice_policy": "order",
                "categ_id": cls.env.ref("product.product_category_all").id,
            }
        )
        cls.faturista = new_test_user(
            cls.env,
            login="inv_faturista",
            groups="base.group_user,account.group_account_invoice",
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )
        # Bruna's real hat stack: salesman + buyer + invoicing, no stock role.
        cls.multi_hat = new_test_user(
            cls.env,
            login="inv_multi_hat",
            groups=(
                "base.group_user,"
                "sales_team.group_sale_salesman,"
                "purchase.group_purchase_user,"
                "account.group_account_invoice"
            ),
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )

    def _sale_with_draft_invoice(self):
        """Build a confirmed sale of a stockable product (which creates a
        delivery picking) and its draft customer invoice, as the back office
        would hand it to the invoicing clerk."""
        order = (
            self.env["sale.order"]
            .with_company(self.company)
            .create(
                {
                    "partner_id": self.partner_a.id,
                    "order_line": [
                        (0, 0, {"product_id": self.stockable.id, "product_uom_qty": 3})
                    ],
                }
            )
        )
        order.action_confirm()
        self.assertTrue(
            order.picking_ids,
            "confirming a stockable sale must create a delivery picking",
        )
        invoice = order._create_invoices()
        self.assertEqual(invoice.state, "draft")
        return order, invoice

    def test_faturista_posts_invoice_without_stock_error(self):
        order, invoice = self._sale_with_draft_invoice()
        invoice.with_user(self.faturista).action_post()
        self.assertEqual(invoice.state, "posted")
        # The lockdown still holds in the very same scenario: the clerk who
        # just posted the invoice cannot touch the delivery picking.
        with self.assertRaises(AccessError):
            order.picking_ids[:1].with_user(self.faturista).write({"note": "leak"})

    def test_multi_hat_posts_invoice_without_stock_error(self):
        order, invoice = self._sale_with_draft_invoice()
        invoice.with_user(self.multi_hat).action_post()
        self.assertEqual(invoice.state, "posted")
        with self.assertRaises(AccessError):
            order.picking_ids[:1].with_user(self.multi_hat).write({"note": "leak"})
