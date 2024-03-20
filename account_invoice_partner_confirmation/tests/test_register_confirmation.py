# Copyright 2022 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestRegisterConfirmation(TransactionCase):
    def setUp(self):
        super().setUp()

        # Create user.
        user = self.env["res.users"].create(
            {
                "name": "Because I am accountman!",
                "login": "accountman",
                "password": "accountman",
                "groups_id": [
                    (6, 0, self.env.user.groups_id.ids),
                    (4, self.env.ref("account.group_account_user").id),
                ],
            }
        )
        user.partner_id.email = "accountman@test.com"

        # Shadow the current environment/cursor
        # with one having the report user.
        # This is mandatory to test access rights.
        self.env = self.env(user=user)
        self.cr = self.env.cr

        self.partner_confirm_obj = self.env["account.invoice.partner.confirmation"]
        self.part_confirm_registe_model = self.env[
            "account.invoice.partner.confirmation.register"
        ]
        self.account_move_model = self.env["account.move"]

        self.journal_sale = self.env["account.journal"].create(
            {"name": "Sale Journal", "type": "sale", "code": "TEST_SALES_JOURNAL"}
        )
        self.type_receivable = self.env["account.account.type"].create(
            {
                "name": "Receivable Account",
                "type": "receivable",
                "internal_group": "income",
            }
        )
        self.account_receivable = self.env["account.account"].create(
            {
                "name": "Test receivable account",
                "user_type_id": self.type_receivable.id,
                "reconcile": True,
                "code": "TEST_REC_AC",
            }
        )
        self.partner = self.env["res.partner"].create(
            {
                "name": "Partner",
                "property_account_receivable_id": self.account_receivable.id,
            }
        )

        self.brand = self.env["fleet.vehicle.model.brand"].create(
            {"name": "Brand Vehicle"}
        )
        self.model = self.env["fleet.vehicle.model"].create(
            {"brand_id": self.brand.id, "name": "Test1"}
        )
        self.vehicle = self.env["fleet.vehicle"].create({"model_id": self.model.id})
        self.employee = self.env["hr.employee"].create({"name": "Test Employee"})

    def create_invoice(self, posted=True, move_type="out_invoice"):
        invoice = self.account_move_model.create(
            {
                "partner_id": self.partner.id,
                "move_type": move_type,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {"name": "Test line", "quantity": 1.0, "price_unit": 100.00},
                    ),
                ],
            }
        )
        if posted:
            invoice.action_post()
        return invoice

    def create_register_partner_confirm_wizard(self, invoice_ids, confirm_date=None):
        if confirm_date is None:
            confirm_date = date.today()
        wizard = self.part_confirm_registe_model.with_context(
            active_ids=invoice_ids, active_model="account.move"
        ).create({"confirmation_date": confirm_date})
        return wizard

    def test_basic_partner_confir_and_error_confirmed_already(self):
        invoice1 = self.create_invoice()

        confirm_date = date(2022, 3, 12)
        wizard = self.create_register_partner_confirm_wizard(invoice1.ids, confirm_date)

        wizard.state = "with_pendencies"
        wizard.vehicle_id = self.vehicle.id
        wizard.responsible_employee_ids = [(6, 0, self.employee.ids)]
        action = wizard.register_confirmation()

        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(invoice1.part_confirm_vehicle_id, wizard.vehicle_id)
        self.assertEqual(
            invoice1.part_confirm_responsible_employee_ids,
            wizard.responsible_employee_ids,
        )
        self.assertEqual(invoice1.part_confirm_date, confirm_date)
        self.assertEqual(invoice1.part_confirm_state, wizard.state)

        invoice2 = self.create_invoice()

        with self.assertRaises(UserError):
            wizard = self.create_register_partner_confirm_wizard(
                [invoice1.id, invoice2.id]
            )

        invoice1.action_cancel_partner_confirmation()
        self.assertEqual(invoice1.part_confirm_id.id, False)

        wizard = self.create_register_partner_confirm_wizard([invoice1.id, invoice2.id])
        action = wizard.register_confirmation()
        self.assertEqual(action["view_mode"], "tree")
        partner_confirmation_ids = self.partner_confirm_obj.search(action["domain"])
        self.assertEqual(len(partner_confirmation_ids), 2)

        self.assertNotEqual(invoice1.part_confirm_id.id, False)
        self.assertNotEqual(invoice2.part_confirm_id.id, False)

    def test_user_error_invoice_draft(self):
        invoice = self.create_invoice(posted=False)
        with self.assertRaises(UserError):
            self.create_register_partner_confirm_wizard(invoice.ids)

    def test_user_error_invoices_max_number(self):
        invoices = []
        for _ in range(11):
            invoice = self.create_invoice()
            invoices.append(invoice.id)

        with self.assertRaises(UserError):
            self.create_register_partner_confirm_wizard(invoices)

    def test_user_error_invoice_not_out_invoice(self):
        invoice = self.create_invoice(move_type="out_refund")
        with self.assertRaises(UserError):
            self.create_register_partner_confirm_wizard(invoice.ids)
