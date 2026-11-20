# Copyright 2026 Engenere.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.exceptions import UserError
from odoo.fields import Command, Datetime
from odoo.tests import TransactionCase, tagged


# After every module is loaded: the localization extends the order line, and a
# test run halfway through the load would meet a registry without those fields.
@tagged("post_install", "-at_install")
class TestSaleCommitmentDate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Customer"})
        cls.product = cls.env["product.product"].create({"name": "Product"})

    def _create_order(self, **values):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [Command.create({"product_id": self.product.id})],
                **values,
            }
        )

    def _get_arch(self, view_xmlid):
        view = self.env.ref(view_xmlid)
        arch = self.env["sale.order"].get_view(view.id, view.type)["arch"]
        return etree.fromstring(arch)

    def test_date_is_not_required_by_default(self):
        order = self._create_order()

        order.action_confirm()

        self.assertEqual(order.state, "sale")

    def test_order_without_date_is_not_confirmed(self):
        self.company.sale_commitment_date_required = True
        order = self._create_order()

        with self.assertRaises(UserError):
            order.action_confirm()

        self.assertEqual(order.state, "draft")

    def test_order_with_date_is_confirmed(self):
        self.company.sale_commitment_date_required = True
        order = self._create_order(commitment_date=Datetime.now())

        order.action_confirm()

        self.assertEqual(order.state, "sale")

    def test_error_names_every_order_without_date(self):
        self.company.sale_commitment_date_required = True
        dated = self._create_order(commitment_date=Datetime.now())
        undated = self._create_order() + self._create_order()

        with self.assertRaises(UserError) as error:
            (dated + undated).action_confirm()

        message = error.exception.args[0]
        for order in undated:
            self.assertIn(order.name, message)
        self.assertNotIn(dated.name, message)
        self.assertEqual(dated.state, "draft")

    def test_requirement_follows_the_company_of_the_order(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        other_company.sale_commitment_date_required = True
        order = self._create_order()

        order.action_confirm()

        self.assertEqual(order.state, "sale")

    def test_form_shows_the_date_in_the_header_only(self):
        arch = self._get_arch("sale.view_order_form")

        self.assertEqual(len(arch.xpath("//field[@name='commitment_date']")), 1)
        self.assertTrue(
            arch.xpath("//group[@name='order_details']//field[@name='commitment_date']")
        )
        self.assertTrue(
            arch.xpath("//group[@name='order_details']/label[@for='commitment_date']")
        )

    def test_lists_show_the_date_column(self):
        for view_xmlid in ("sale.view_quotation_tree", "sale.view_order_tree"):
            with self.subTest(view=view_xmlid):
                field = self._get_arch(view_xmlid).xpath(
                    "//field[@name='commitment_date']"
                )[0]
                self.assertEqual(field.get("optional"), "show")
