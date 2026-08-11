# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date, timedelta
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from ..hooks import post_init_hook
from .common import ChartlessAccountCommon


@tagged("post_install", "-at_install")
class TestRenegotiationUnified(ChartlessAccountCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create(
            {
                "name": "Unified Product",
                "type": "service",
                "list_price": 1000.0,
                "weight": 1.0,
            }
        )
        cls.payment_term = cls.env["account.payment.term"].create(
            {
                "name": "2x Unified",
                "line_ids": [
                    Command.create(
                        {"value": "percent", "value_amount": 50.0, "days": 30}
                    ),
                    Command.create({"value": "balance", "days": 60}),
                ],
            }
        )
        cls.payment_term_4x = cls.env["account.payment.term"].create(
            {
                "name": "4x Unified",
                "line_ids": [
                    Command.create(
                        {"value": "percent", "value_amount": 25.0, "days": 15}
                    ),
                    Command.create(
                        {"value": "percent", "value_amount": 25.0, "days": 30}
                    ),
                    Command.create(
                        {"value": "percent", "value_amount": 25.0, "days": 45}
                    ),
                    Command.create({"value": "balance", "days": 60}),
                ],
            }
        )

        Method = cls.env["account.payment.method"]

        def _method(code, payment_type, name):
            # l10n_br_account_payment_order ships the inbound CNAB methods
            existing = Method.search(
                [("code", "=", code), ("payment_type", "=", payment_type)],
                limit=1,
            )
            return existing or Method.create(
                {"name": name, "code": code, "payment_type": payment_type}
            )

        method_cnab_in = _method("240", "inbound", "CNAB 240 Test")
        method_manual_in = _method("manual_in_t", "inbound", "Manual In Test")
        method_cnab_out = _method("240", "outbound", "CNAB Out Test")
        cls.mode_cnab_in = cls.env["account.payment.mode"].create(
            {
                "name": "Boleto CNAB Test",
                "payment_method_id": method_cnab_in.id,
                "company_id": cls.company.id,
                "bank_account_link": "variable",
                # CNAB constraints from l10n_br_account_payment_order
                "group_lines": False,
            }
        )
        cls.mode_manual_in = cls.env["account.payment.mode"].create(
            {
                "name": "Manual In Mode",
                "payment_method_id": method_manual_in.id,
                "company_id": cls.company.id,
                "bank_account_link": "variable",
            }
        )
        cls.mode_cnab_out = cls.env["account.payment.mode"].create(
            {
                "name": "CNAB Out Mode",
                "payment_method_id": method_cnab_out.id,
                "company_id": cls.company.id,
                "bank_account_link": "variable",
                "group_lines": False,
            }
        )

        cls.renegotiation_group = cls.env.ref(
            "eng_account_renegotiation.group_vendor_bill_renegotiation"
        )
        internal_group = cls.env.ref("base.group_user")
        billing_group = cls.env.ref("account.group_account_invoice")
        manager_group = cls.env.ref("account.group_account_manager")
        # CNAB flows read account.payment.line in the acting user's env
        # (upstream duck-typing), which requires the payment order group
        payment_group = cls.env.ref("account_payment_order.group_account_payment")
        cls.currency_eur = cls.env.ref("base.EUR")
        cls.currency_eur.active = True
        cls.env["res.currency.rate"].create(
            {
                "currency_id": cls.currency_eur.id,
                "rate": 2.0,
                "company_id": cls.company.id,
            }
        )
        cls.manager_user = cls.env["res.users"].create(
            {
                "name": "Unified Manager",
                "login": "unified_manager",
                "email": "unified.manager@test.example.com",
                "groups_id": [
                    Command.set([internal_group.id, manager_group.id, payment_group.id])
                ],
            }
        )
        cls.renegotiator_user = cls.env["res.users"].create(
            {
                "name": "Unified Renegotiator",
                "login": "unified_renegotiator",
                "email": "unified.renegotiator@test.example.com",
                "groups_id": [
                    Command.set(
                        [
                            internal_group.id,
                            billing_group.id,
                            payment_group.id,
                            cls.renegotiation_group.id,
                        ]
                    )
                ],
            }
        )

    def _create_posted_move(
        self, move_type, payment_mode=None, term=None, currency=None
    ):
        account = (
            self.account_expense
            if move_type in ("in_invoice", "in_receipt")
            else self.account_income
        )
        journal = self._journal_for(move_type)
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "invoice_date": date.today(),
            "invoice_payment_term_id": (term or self.payment_term).id,
            "invoice_line_ids": [
                Command.create(
                    {
                        "name": "Unified Line",
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 1000.0,
                        "account_id": account.id,
                    }
                )
            ],
        }
        vals["journal_id"] = journal.id
        if currency:
            vals["currency_id"] = currency.id
        if payment_mode:
            vals["payment_mode_id"] = payment_mode.id
        move = self.env["account.move"].create(vals)
        move.action_post()
        return move

    def _make_wizard(self, move, user=None):
        wizard_model = self.env["account.installment.renegotiation.wizard"]
        if user:
            wizard_model = wizard_model.with_user(user)
        return wizard_model.create({"move_id": move.id})

    def _term_lines(self, move):
        return move.sudo().line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )

    def _register_partial_payment(self, move, amount):
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=move.ids
        ).create({"amount": amount}).action_create_payments()

    def test_partial_reconciliation_blocked(self):
        """A partially paid installment blocks renegotiation for everyone."""
        invoice = self._create_posted_move("out_invoice")
        self._register_partial_payment(invoice, 100.0)
        partial_lines = self._term_lines(invoice).filtered(
            lambda line: line.matched_credit_ids or line.matched_debit_ids
        )
        self.assertTrue(partial_lines, "Fixture must have a partial installment.")
        dates_before = sorted(self._term_lines(invoice).mapped("date_maturity"))
        messages_before = len(invoice.message_ids)

        wizard = self._make_wizard(invoice, user=self.manager_user)
        with self.assertRaisesRegex(UserError, "partial payment"):
            wizard.action_apply()

        self.assertEqual(
            sorted(self._term_lines(invoice).mapped("date_maturity")), dates_before
        )
        self.assertTrue(
            partial_lines.exists()
            and (partial_lines.matched_credit_ids or partial_lines.matched_debit_ids),
            "The partial reconciliation must be intact.",
        )
        self.assertEqual(len(invoice.message_ids), messages_before)

        bill = self._create_posted_move("in_invoice")
        self._register_partial_payment(bill, 100.0)
        bill_wizard = self._make_wizard(bill, user=self.renegotiator_user)
        with self.assertRaisesRegex(UserError, "partial payment"):
            bill_wizard.action_apply()

    def test_header_mode_change_full_flow(self):
        """Header mode + term swap runs the mirrored sequence in order."""
        invoice = self._create_posted_move(
            "out_invoice", payment_mode=self.mode_manual_in
        )
        wizard = self._make_wizard(invoice, user=self.manager_user)
        self.assertEqual(wizard.expected_payment_type, "inbound")
        wizard.payment_term_id = self.payment_term_4x
        wizard._onchange_payment_term_id()
        wizard.header_payment_mode_id = self.mode_cnab_in
        wizard._onchange_header_payment_mode_id()

        calls = []
        move_cls = type(self.env["account.move"])
        line_cls = type(self.env["account.move.line"])
        with patch.object(
            line_cls, "_cnab_already_start", lambda line: True
        ), patch.object(
            line_cls,
            "update_cnab_for_cancel_invoice",
            lambda line: calls.append("baixa"),
        ), patch.object(
            move_cls, "load_cnab_info", lambda move: calls.append("inclusao")
        ), patch.object(
            move_cls, "generate_boleto_pdf", lambda move: calls.append("pdf")
        ):
            wizard.action_apply()

        self.assertEqual(invoice.payment_mode_id, self.mode_cnab_in)
        self.assertEqual(invoice.invoice_payment_term_id, self.payment_term_4x)
        new_lines = self._term_lines(invoice)
        self.assertEqual(len(new_lines), 4)
        for line in new_lines:
            self.assertEqual(line.payment_mode_id, self.mode_cnab_in)
        self.assertEqual(calls[:2], ["baixa", "baixa"])
        self.assertEqual(calls[2:], ["inclusao", "pdf"])
        self.assertTrue(
            any(
                "payment mode replaced" in (message.body or "")
                for message in invoice.message_ids
            )
        )
        self.assertTrue(
            any(
                "Renegotiated" in (message.body or "")
                for message in invoice.message_ids
            )
        )

    def test_header_mode_mixture_refused(self):
        """Header swap plus a divergent per-line mode is refused, no effects."""
        invoice = self._create_posted_move(
            "out_invoice", payment_mode=self.mode_manual_in
        )
        dates_before = sorted(self._term_lines(invoice).mapped("date_maturity"))
        wizard = self._make_wizard(invoice, user=self.manager_user)
        wizard.header_payment_mode_id = self.mode_cnab_in
        wizard._onchange_header_payment_mode_id()
        wizard.line_ids[0].payment_mode_id = self.mode_manual_in

        with self.assertRaisesRegex(UserError, "installments must use the new mode"):
            wizard.action_apply()

        self.assertEqual(invoice.payment_mode_id, self.mode_manual_in)
        self.assertEqual(
            sorted(self._term_lines(invoice).mapped("date_maturity")), dates_before
        )

    def test_plain_renegotiation_regenerates_boleto(self):
        """Without a header swap the boleto is still reissued for CNAB."""
        calls = []
        move_cls = type(self.env["account.move"])
        with patch.object(
            move_cls, "load_cnab_info", lambda move: calls.append("inclusao")
        ), patch.object(
            move_cls, "generate_boleto_pdf", lambda move: calls.append("pdf")
        ):
            invoice = self._create_posted_move(
                "out_invoice", payment_mode=self.mode_cnab_in
            )
            calls.clear()  # posting side effects are not under test
            wizard = self._make_wizard(invoice, user=self.manager_user)
            new_date = date.today() + timedelta(days=120)
            for line in wizard.line_ids:
                line.date_maturity = new_date
            wizard.action_apply()

        self.assertEqual(calls, ["inclusao", "pdf"])
        self.assertEqual(invoice.payment_mode_id, self.mode_cnab_in)
        for line in self._term_lines(invoice):
            self.assertEqual(line.date_maturity, new_date)

    def test_non_cnab_no_pdf(self):
        """Non-CNAB mode: upstream may call load_cnab_info, never the PDF."""
        invoice = self._create_posted_move(
            "out_invoice", payment_mode=self.mode_manual_in
        )
        wizard = self._make_wizard(invoice, user=self.manager_user)
        new_date = date.today() + timedelta(days=120)
        for line in wizard.line_ids:
            line.date_maturity = new_date

        calls = []
        move_cls = type(self.env["account.move"])
        with patch.object(
            move_cls, "load_cnab_info", lambda move: calls.append("inclusao")
        ), patch.object(
            move_cls, "generate_boleto_pdf", lambda move: calls.append("pdf")
        ):
            wizard.action_apply()

        self.assertNotIn("pdf", calls)

    def test_vendor_bill_no_boleto(self):
        """Outbound documents never generate a boleto, even CNAB-coded."""
        bill = self._create_posted_move("in_invoice", currency=self.currency_eur)
        wizard = self._make_wizard(bill, user=self.renegotiator_user)
        self.assertEqual(wizard.expected_payment_type, "outbound")
        wizard.header_payment_mode_id = self.mode_cnab_out
        wizard._onchange_header_payment_mode_id()

        calls = []
        move_cls = type(self.env["account.move"])
        with patch.object(
            move_cls, "load_cnab_info", lambda move: calls.append("inclusao")
        ), patch.object(
            move_cls, "generate_boleto_pdf", lambda move: calls.append("pdf")
        ):
            wizard.action_apply()

        self.assertNotIn("pdf", calls)
        self.assertEqual(bill.payment_mode_id, self.mode_cnab_out)

    def test_header_mode_wrong_type_refused(self):
        """An RPC write bypasses the view domain; the server refuses."""
        bill = self._create_posted_move("in_invoice")
        dates_before = sorted(self._term_lines(bill).mapped("date_maturity"))
        mode_before = bill.payment_mode_id
        wizard = self._make_wizard(bill, user=self.renegotiator_user)
        # inbound mode pushed into a vendor bill, written directly
        # (no onchange, no client domain); line modes match so the
        # direction guard is the one exercised
        wizard.write({"header_payment_mode_id": self.mode_cnab_in.id})
        for line in wizard.line_ids:
            line.payment_mode_id = self.mode_cnab_in

        with self.assertRaisesRegex(UserError, "must be of type outbound"):
            wizard.action_apply()

        self.assertEqual(bill.payment_mode_id, mode_before)
        self.assertEqual(
            sorted(self._term_lines(bill).mapped("date_maturity")), dates_before
        )

    def test_header_mode_then_term_change_sequence(self):
        """Choosing the header mode before the term keeps lines consistent."""
        invoice = self._create_posted_move(
            "out_invoice", payment_mode=self.mode_manual_in
        )
        wizard = self._make_wizard(invoice, user=self.manager_user)
        wizard.header_payment_mode_id = self.mode_cnab_in
        wizard._onchange_header_payment_mode_id()
        wizard.payment_term_id = self.payment_term_4x
        wizard._onchange_payment_term_id()

        for line in wizard.line_ids:
            self.assertEqual(line.payment_mode_id, self.mode_cnab_in)

        move_cls = type(self.env["account.move"])
        with patch.object(move_cls, "load_cnab_info", lambda move: None), patch.object(
            move_cls, "generate_boleto_pdf", lambda move: None
        ):
            wizard.action_apply()

        self.assertEqual(invoice.payment_mode_id, self.mode_cnab_in)
        for line in self._term_lines(invoice):
            self.assertEqual(line.payment_mode_id, self.mode_cnab_in)

    def test_read_only_user_cannot_renegotiate(self):
        """Read access is not enough: the sudo() surgery demands write."""
        bill = self._create_posted_move("in_invoice")
        dates_before = sorted(self._term_lines(bill).mapped("date_maturity"))
        # GLOBAL write-only rule (group rules are unioned, so a permissive
        # billing rule would win): reads stay allowed, writes on this bill
        # are denied for every non-superuser
        self.env["ir.rule"].create(
            {
                "name": "Test: block writes on this bill",
                "model_id": self.env.ref("account.model_account_move").id,
                "domain_force": f"[('id', '!=', {bill.id})]",
                "perm_read": False,
                "perm_write": True,
                "perm_create": False,
                "perm_unlink": False,
            }
        )
        bill_as_user = bill.with_user(self.renegotiator_user)
        self.assertEqual(bill_as_user.move_type, "in_invoice")  # read OK

        from odoo.exceptions import AccessError

        with self.assertRaises(AccessError):
            bill_as_user.action_renegotiate_installments()
        self.assertFalse(bill_as_user.can_renegotiate_installments)
        self.assertEqual(
            sorted(self._term_lines(bill).mapped("date_maturity")), dates_before
        )

    def test_migration_hook(self):
        """The post_init_hook copies old group members exactly once."""
        member = self.env["res.users"].create(
            {
                "name": "Old Group Member",
                "login": "old_group_member",
                "email": "old.group.member@test.example.com",
            }
        )
        bystander = self.env["res.users"].create(
            {
                "name": "Bystander",
                "login": "bystander_user",
                "email": "bystander@test.example.com",
            }
        )

        # Absent old module: no-op
        post_init_hook(self.env.cr, None)
        self.assertNotIn(member, self.renegotiation_group.users)

        # Simulate the old module's group, still empty: no-op branch
        old_group = self.env["res.groups"].create({"name": "Change Payment Data"})
        self.env["ir.model.data"].create(
            {
                "name": "group_payment_data",
                "module": "trento_invoice_change_payment_data",
                "model": "res.groups",
                "res_id": old_group.id,
            }
        )
        post_init_hook(self.env.cr, None)
        self.assertNotIn(member, self.renegotiation_group.users)

        old_group.users = [Command.link(member.id)]
        post_init_hook(self.env.cr, None)
        self.assertIn(member, self.renegotiation_group.users)
        self.assertNotIn(bystander, self.renegotiation_group.users)

        members_before = self.renegotiation_group.users
        post_init_hook(self.env.cr, None)
        self.assertEqual(self.renegotiation_group.users, members_before)
