# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date, timedelta

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import ChartlessAccountCommon

BLOCK_MSG = "Renegotiate Vendor Bill"


@tagged("post_install", "-at_install")
class TestVendorBillRenegotiationGroup(ChartlessAccountCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # weight: the repo-wide CI installs every module of this repo and
        # some of them constrain product weight to be positive
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "service",
                "list_price": 1000.0,
                "weight": 1.0,
            }
        )
        cls.payment_term = cls.env["account.payment.term"].create(
            {
                "name": "2 Installments Test",
                "line_ids": [
                    Command.create(
                        {"value": "percent", "value_amount": 50.0, "days": 30}
                    ),
                    Command.create({"value": "balance", "days": 60}),
                ],
            }
        )

        cls.renegotiation_group = cls.env.ref(
            "eng_account_renegotiation.group_vendor_bill_renegotiation"
        )
        internal_group = cls.env.ref("base.group_user")
        billing_group = cls.env.ref("account.group_account_invoice")
        manager_group = cls.env.ref("account.group_account_manager")
        cls.billing_user = cls.env["res.users"].create(
            {
                "name": "Billing Without Renegotiation Group",
                "login": "billing_no_renegotiation",
                "email": "billing.no.renegotiation@test.example.com",
                "groups_id": [Command.set([internal_group.id, billing_group.id])],
            }
        )
        cls.renegotiator_user = cls.env["res.users"].create(
            {
                "name": "Billing With Renegotiation Group",
                "login": "billing_renegotiator",
                "email": "billing.renegotiator@test.example.com",
                "groups_id": [
                    Command.set(
                        [
                            internal_group.id,
                            billing_group.id,
                            cls.renegotiation_group.id,
                        ]
                    )
                ],
            }
        )
        cls.group_only_user = cls.env["res.users"].create(
            {
                "name": "Group Without Billing",
                "login": "renegotiation_group_only",
                "email": "renegotiation.group.only@test.example.com",
                "groups_id": [
                    Command.set([internal_group.id, cls.renegotiation_group.id])
                ],
            }
        )
        cls.manager_user = cls.env["res.users"].create(
            {
                "name": "Plain Invoicing Manager",
                "login": "plain_invoicing_manager",
                "email": "plain.invoicing.manager@test.example.com",
                "groups_id": [Command.set([internal_group.id, manager_group.id])],
            }
        )

        # Second company (no chart of accounts needed: explicit accounts)
        cls.company2 = cls.env["res.company"].create({"name": "Other Company"})
        cls.account_expense2 = cls.env["account.account"].create(
            {
                "name": "Expenses C2",
                "code": "EXP2TEST",
                "account_type": "expense",
                "company_id": cls.company2.id,
            }
        )
        cls.account_payable2 = cls.env["account.account"].create(
            {
                "name": "Payable C2",
                "code": "PAY2TEST",
                "account_type": "liability_payable",
                "reconcile": True,
                "company_id": cls.company2.id,
            }
        )
        cls.journal_purchase2 = cls.env["account.journal"].create(
            {
                "name": "Purchases C2",
                "code": "BIL2",
                "type": "purchase",
                "company_id": cls.company2.id,
                "default_account_id": cls.account_expense2.id,
            }
        )
        cls.partner2 = cls.env["res.partner"].create({"name": "Vendor C2"})
        cls.partner2.with_company(
            cls.company2
        ).property_account_payable_id = cls.account_payable2

    def _create_posted_move(self, move_type, company=None, journal=None):
        company = company or self.company
        if company == self.company2:
            account = self.account_expense2
        elif move_type in ("in_invoice", "in_receipt"):
            account = self.account_expense
        else:
            account = self.account_income
        if not journal and company == self.company:
            journal = self._journal_for(move_type)
        vals = {
            "move_type": move_type,
            "partner_id": (
                self.partner.id if company == self.company else self.partner2.id
            ),
            "invoice_date": date.today(),
            "invoice_payment_term_id": self.payment_term.id,
            "invoice_line_ids": [
                Command.create(
                    {
                        "name": "Test Line",
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 1000.0,
                        "account_id": account.id,
                    }
                )
            ],
        }
        if journal:
            vals["journal_id"] = journal.id
        move = self.env["account.move"].with_company(company).create(vals)
        move.action_post()
        return move

    def _payment_term_lines(self, move):
        return move.sudo().line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )

    def _assert_move_untouched(self, move, dates_before):
        lines = self._payment_term_lines(move)
        self.assertEqual(
            sorted(lines.mapped("date_maturity")),
            dates_before,
            "Payment term lines must not have been modified.",
        )
        self.assertFalse(
            any(
                "Renegotiated" in (message.body or "")
                for message in move.sudo().message_ids
            ),
            "No renegotiation message may be logged in the chatter.",
        )

    def test_billing_user_without_group_is_blocked(self):
        """Billing rights alone must not allow renegotiating a vendor bill."""
        bill = self._create_posted_move("in_invoice")
        bill_as_user = bill.with_user(self.billing_user)

        self.assertFalse(bill_as_user.can_renegotiate_installments)
        with self.assertRaisesRegex(UserError, BLOCK_MSG):
            bill_as_user.action_renegotiate_installments()
        with self.assertRaises(AccessError):
            self.env["account.installment.renegotiation.wizard"].with_user(
                self.billing_user
            ).create({"move_id": bill.id})

    def test_group_without_billing_is_blocked(self):
        """The group only works combined with Billing rights."""
        bill = self._create_posted_move("in_invoice")

        # Unit proof of the AND (sudo keeps the user and their groups but
        # bypasses the access checks, isolating the helper's semantics)
        self.assertFalse(
            bill.with_user(self.group_only_user)
            .sudo()
            ._eng_can_renegotiate_vendor_bill()
        )

        # End to end the user dies earlier: no ACL on account.move at all
        with self.assertRaises(AccessError):
            bill.with_user(self.group_only_user).action_renegotiate_installments()
        with self.assertRaises(AccessError):
            self.env["account.installment.renegotiation.wizard"].with_user(
                self.group_only_user
            ).create({"move_id": bill.id})

    def test_group_user_renegotiates_vendor_bill(self):
        """A billing user in the group runs the whole flow on a vendor bill."""
        bill = self._create_posted_move("in_invoice")
        bill_as_user = bill.with_user(self.renegotiator_user)

        self.assertTrue(bill_as_user.can_renegotiate_installments)

        action = bill_as_user.action_renegotiate_installments()
        self.assertEqual(
            action["res_model"], "account.installment.renegotiation.wizard"
        )
        wizard = (
            self.env["account.installment.renegotiation.wizard"]
            .with_user(self.renegotiator_user)
            .browse(action["res_id"])
        )
        self.assertEqual(wizard.move_id, bill)

        new_date = date.today() + timedelta(days=180)
        for line in wizard.line_ids:
            line.date_maturity = new_date
        wizard.action_apply()

        term_lines = self._payment_term_lines(bill)
        self.assertEqual(len(term_lines), 2)
        for line in term_lines:
            self.assertEqual(line.date_maturity, new_date)
        self.assertAlmostEqual(
            sum(abs(line.amount_currency) for line in term_lines),
            bill.amount_total,
            places=2,
        )
        self.assertTrue(
            any("Renegotiated" in (message.body or "") for message in bill.message_ids),
            "The renegotiation must be logged in the chatter.",
        )

    def test_can_renegotiate_cache_is_user_dependent(self):
        """The compute must not leak one user's value to another via cache.

        No cache invalidation between the reads: without the
        @api.depends_context("uid") on this module's compute override, the
        first user's value would be served to the others from the cache.
        """
        bill = self._create_posted_move("in_invoice")
        self.assertTrue(bill.with_user(self.manager_user).can_renegotiate_installments)
        self.assertFalse(bill.with_user(self.billing_user).can_renegotiate_installments)
        self.assertTrue(
            bill.with_user(self.renegotiator_user).can_renegotiate_installments
        )

    def test_group_user_receipt_matrix(self):
        """in_receipt is a vendor document (allowed); out_receipt is not."""
        in_receipt = self._create_posted_move("in_receipt")
        in_receipt_as_user = in_receipt.with_user(self.renegotiator_user)
        self.assertTrue(in_receipt_as_user.can_renegotiate_installments)
        action = in_receipt_as_user.action_renegotiate_installments()
        self.assertEqual(
            action["res_model"], "account.installment.renegotiation.wizard"
        )

        out_receipt = self._create_posted_move("out_receipt")
        out_receipt_as_user = out_receipt.with_user(self.renegotiator_user)
        self.assertFalse(out_receipt_as_user.can_renegotiate_installments)
        with self.assertRaisesRegex(UserError, BLOCK_MSG):
            out_receipt_as_user.action_renegotiate_installments()

    def test_group_user_blocked_on_customer_invoice(self):
        """The group must not unlock customer invoices, on any code path."""
        invoice = self._create_posted_move("out_invoice")
        dates_before = sorted(self._payment_term_lines(invoice).mapped("date_maturity"))
        invoice_as_user = invoice.with_user(self.renegotiator_user)

        self.assertFalse(invoice_as_user.can_renegotiate_installments)
        with self.assertRaisesRegex(UserError, BLOCK_MSG):
            invoice_as_user.action_renegotiate_installments()

        # Attack path: the renegotiator builds the wizard directly (the ACL
        # allows it) pointing at a customer invoice — apply must refuse
        wizard = (
            self.env["account.installment.renegotiation.wizard"]
            .with_user(self.renegotiator_user)
            .create({"move_id": invoice.id})
        )
        new_date = date.today() + timedelta(days=180)
        for line in wizard.line_ids:
            line.date_maturity = new_date
        with self.assertRaisesRegex(UserError, BLOCK_MSG):
            wizard.action_apply()

        self._assert_move_untouched(invoice, dates_before)

    def test_record_rule_blocks_other_company_bill(self):
        """A user must not reach another company's bill through the wizard."""
        bill2 = self._create_posted_move(
            "in_invoice", company=self.company2, journal=self.journal_purchase2
        )
        dates_before = sorted(self._payment_term_lines(bill2).mapped("date_maturity"))

        # Re-browse through a clean env: a real RPC attacker guesses the id
        # and does not inherit the fixture's allowed_company_ids context
        bill2_as_user = (
            self.env["account.move"].with_user(self.renegotiator_user).browse(bill2.id)
        )
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            bill2_as_user.action_renegotiate_installments()
        with self.assertRaises(AccessError):
            self.env["account.installment.renegotiation.wizard"].with_user(
                self.renegotiator_user
            ).create({"move_id": bill2.id})

        # Swap vector: build a wizard on an accessible bill, then point it
        # at the other company's bill through a raw write (as RPC would)
        bill = self._create_posted_move("in_invoice")
        action = bill.with_user(
            self.renegotiator_user
        ).action_renegotiate_installments()
        wizard = (
            self.env["account.installment.renegotiation.wizard"]
            .with_user(self.renegotiator_user)
            .browse(action["res_id"])
        )
        wizard.write({"move_id": bill2.id})
        with self.assertRaises(AccessError):
            wizard.action_apply()

        self._assert_move_untouched(bill2, dates_before)

    def test_warm_cache_does_not_bypass_access_checks(self):
        """A cache warmed by privileged code must not leak another company's
        bill to the user: the helper's explicit access checks fire anyway.

        The helper is targeted directly because it is what the explicit
        checks guard: a plain field read (move_type) IS served from the
        warm cache without any access check, so without the explicit
        checks the helper would silently authorize. The deeper flow is
        exercised by test_record_rule_blocks_other_company_bill on a cold
        cache, where the ORM fetches enforce the rules by themselves.
        """
        bill2 = self._create_posted_move(
            "in_invoice", company=self.company2, journal=self.journal_purchase2
        )
        # Warm the cache as superuser on purpose, then attack WITHOUT
        # invalidating: plain field reads are now served from cache.
        # Explicit field list: with the whole repo installed (CI), a bare
        # read() walks exotic NFe spec fields on account.move and blows up
        # in convert_to_read before the scenario even starts
        bill2.sudo().read(["move_type", "state", "company_id"])
        bill2_as_user = (
            self.env["account.move"].with_user(self.renegotiator_user).browse(bill2.id)
        )
        self.assertFalse(
            bill2_as_user.can_renegotiate_installments,
            "The compute must swallow the AccessError and hide the button.",
        )
        with self.assertRaises(AccessError):
            bill2_as_user._eng_can_renegotiate_vendor_bill()

    def test_manager_keeps_full_access(self):
        """A plain Invoicing Manager still renegotiates customer invoices."""
        self.assertFalse(
            self.renegotiator_user.has_group("account.group_account_manager"),
            "The renegotiator fixture must not be a manager.",
        )

        invoice = self._create_posted_move("out_invoice")
        invoice_as_manager = invoice.with_user(self.manager_user)
        self.assertTrue(invoice_as_manager.can_renegotiate_installments)

        action = invoice_as_manager.action_renegotiate_installments()
        wizard = (
            self.env["account.installment.renegotiation.wizard"]
            .with_user(self.manager_user)
            .browse(action["res_id"])
        )
        new_date = date.today() + timedelta(days=90)
        for line in wizard.line_ids:
            line.date_maturity = new_date
        wizard.action_apply()
        for line in self._payment_term_lines(invoice):
            self.assertEqual(line.date_maturity, new_date)

        bill = self._create_posted_move("in_invoice")
        self.assertTrue(bill.with_user(self.manager_user).can_renegotiate_installments)

    def _fully_pay(self, move):
        """Pay and reconcile all installments of a posted move (as admin)."""
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=move.ids
        ).create({}).action_create_payments()

    def test_group_user_action_guards(self):
        """Draft and fully paid bills hit the mirrored action guards."""
        draft = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": date.today(),
                "invoice_payment_term_id": self.payment_term.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Test Line",
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 1000.0,
                            "account_id": self.account_expense.id,
                        }
                    )
                ],
            }
        )
        draft_as_user = draft.with_user(self.renegotiator_user)
        self.assertFalse(draft_as_user.can_renegotiate_installments)
        with self.assertRaisesRegex(UserError, "posted invoices"):
            draft_as_user.action_renegotiate_installments()

        paid = self._create_posted_move("in_invoice")
        self._fully_pay(paid)
        paid_as_user = paid.with_user(self.renegotiator_user)
        with self.assertRaisesRegex(UserError, "no unreconciled payment term"):
            paid_as_user.action_renegotiate_installments()

    def test_group_user_empty_wizard_blocked(self):
        """A wizard without installment lines is refused (mirrored guard)."""
        paid = self._create_posted_move("in_invoice")
        self._fully_pay(paid)
        wizard = (
            self.env["account.installment.renegotiation.wizard"]
            .with_user(self.renegotiator_user)
            .create({"move_id": paid.id})
        )
        with self.assertRaisesRegex(UserError, "at least one installment"):
            wizard.action_apply()

    def test_group_user_replicated_validations(self):
        """Every mirrored wizard validation fires for the group user."""
        bill = self._create_posted_move("in_invoice")
        action = bill.with_user(
            self.renegotiator_user
        ).action_renegotiate_installments()
        wizard = (
            self.env["account.installment.renegotiation.wizard"]
            .with_user(self.renegotiator_user)
            .browse(action["res_id"])
        )
        line_a, line_b = wizard.line_ids
        amount_a, amount_b = line_a.amount, line_b.amount

        line_a.amount = amount_a + 100
        with self.assertRaisesRegex(UserError, "must remain unchanged"):
            wizard.action_apply()
        line_a.amount = amount_a

        line_a.amount = -100
        line_b.amount = amount_b + amount_a + 100
        with self.assertRaisesRegex(UserError, "greater than zero"):
            wizard.action_apply()
        line_a.amount = amount_a
        line_b.amount = amount_b

        line_a.date_maturity = False
        with self.assertRaisesRegex(UserError, "must have a due date"):
            wizard.action_apply()
        line_a.date_maturity = date.today() + timedelta(days=30)

        bill.sudo().button_draft()
        with self.assertRaisesRegex(UserError, "must be posted"):
            wizard.action_apply()

    def test_python_message_translated(self):
        """A Python error message from this module renders in pt_BR.

        Guards the Odoo 16 limitation worked around here: code
        translations only load from the po files of the module that owns
        the _() call, so the module carries its own translated strings.
        """
        self.env["res.lang"]._activate_lang("pt_BR")
        invoice = self._create_posted_move("out_invoice")
        with self.assertRaisesRegex(UserError, "Administrador de Faturamento"):
            invoice.with_user(self.renegotiator_user).with_context(
                lang="pt_BR"
            ).action_renegotiate_installments()
