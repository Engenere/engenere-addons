# Copyright 2026 Engenere.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.fields import Command
from odoo.tests import Form, TransactionCase


class TestSaleCustomerOrderRef(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Customer"})
        cls.product = cls.env["product.product"].create({"name": "Product"})
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "client_order_ref": "PO0042",
                "order_line": [
                    Command.create({"product_id": cls.product.id}),
                    Command.create({"product_id": cls.product.id}),
                ],
            }
        )

    def test_lines_take_the_customer_reference(self):
        self.assertEqual(
            self.order.order_line.mapped("partner_order"), ["PO0042", "PO0042"]
        )

    def test_lines_follow_the_customer_reference(self):
        self.order.client_order_ref = "PO0043"

        self.assertEqual(
            self.order.order_line.mapped("partner_order"), ["PO0043", "PO0043"]
        )

    def test_line_keeps_its_own_partner_order(self):
        line = self.order.order_line[0]

        line.partner_order = "PO0099"

        self.assertEqual(
            self.order.order_line.mapped("partner_order"), ["PO0099", "PO0042"]
        )

    def test_new_line_without_partner_order_takes_the_customer_reference(self):
        """The line form opened on a new line sends an empty partner order."""
        line = self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "product_id": self.product.id,
                "partner_order": False,
            }
        )

        self.assertEqual(line.partner_order, "PO0042")

    def test_new_line_keeps_the_partner_order_it_brings(self):
        line = self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "product_id": self.product.id,
                "partner_order": "PO0099",
            }
        )

        self.assertEqual(line.partner_order, "PO0099")

    def test_duplicated_order_starts_without_partner_order(self):
        new_order = self.order.copy()

        self.assertFalse(new_order.client_order_ref)
        self.assertEqual(new_order.order_line.mapped("partner_order"), [False, False])

    def _get_order_form_arch(self):
        view = self.env.ref("sale.view_order_form")
        return etree.fromstring(self.env["sale.order"].get_view(view.id)["arch"])

    def test_customer_reference_is_in_the_partner_group(self):
        """The customer reference is typed next to the customer, not in the
        Other Info tab."""
        arch = self._get_order_form_arch()

        self.assertEqual(
            arch.xpath("//field[@name='client_order_ref']/..")[0].get("name"),
            "partner_details",
        )
        self.assertEqual(len(arch.xpath("//field[@name='client_order_ref']")), 1)

    def test_new_line_shows_the_customer_reference_before_saving(self):
        """The partner order is in the list of lines, hidden by default: the
        form of a line not saved yet only shows what the list has loaded."""
        with Form(self.order) as order_form:
            with order_form.order_line.new() as line:
                line.product_id = self.product

                self.assertEqual(line.partner_order, "PO0042")

    def test_new_line_follows_the_customer_reference_before_saving(self):
        with Form(self.order) as order_form:
            with order_form.order_line.new() as line:
                line.product_id = self.product
            order_form.client_order_ref = "PO0043"

        self.assertEqual(
            self.order.order_line.mapped("partner_order"),
            ["PO0043", "PO0043", "PO0043"],
        )
