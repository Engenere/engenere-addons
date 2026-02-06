# Copyright 2022 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestRegisterConfirmation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create user.
        user = cls.env["res.users"].create(
            {
                "name": "Because I am accountman!",
                "login": "accountman",
                "password": "accountman",
                "groups_id": [
                    (6, 0, cls.env.user.groups_id.ids),
                    (4, cls.env.ref("account.group_account_user").id),
                    (
                        4,
                        cls.env.ref(
                            "eng_partner_confirmation.group_partner_confirmation"
                        ).id,
                    ),
                ],
            }
        )
        user.partner_id.email = "accountman@test.com"

        # Shadow the current environment/cursor
        # with one having the report user.
        # This is mandatory to test access rights.
        cls.env = cls.env(user=user)
        cls.cr = cls.env.cr

        cls.partner_confirm_obj = cls.env["account.invoice.partner.confirmation"]
        cls.part_confirm_registe_model = cls.env[
            "account.invoice.partner.confirmation.register"
        ]
        cls.account_move_model = cls.env["account.move"]

        cls.journal_sale = cls.env["account.journal"].create(
            {"name": "Sale Journal", "type": "sale", "code": "TEST_SALES_JOURNAL"}
        )

        cls.account_receivable = cls.env["account.account"].create(
            {
                "name": "Test receivable account",
                "reconcile": True,
                "account_type": "asset_receivable",
                "code": "ACCRV",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Partner",
                "property_account_receivable_id": cls.account_receivable.id,
            }
        )

        cls.vehicle = cls.env["partner.confirmation.vehicle"].create(
            {"name": "Test Vehicle"}
        )
        cls.employee = cls.env["partner.confirmation.responsible"].create(
            {"name": "Test Employee"}
        )

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

    def test_user_error_invoice_not_out_invoice(self):
        invoice = self.create_invoice(move_type="out_refund")
        with self.assertRaises(UserError):
            self.create_register_partner_confirm_wizard(invoice.ids)

    def test_action_register_partner_confirmation(self):
        """Test the button that opens the wizard from the invoice."""
        invoice = self.create_invoice()
        action = invoice.action_register_partner_confirmation()
        self.assertEqual(
            action["res_model"], "account.invoice.partner.confirmation.register"
        )
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["active_ids"], invoice.ids)

    def test_cancel_confirmation_message_all_fields(self):
        """Test cancel message includes all optional fields."""
        invoice = self.create_invoice()
        confirm_date = date(2024, 6, 15)
        wizard = self.create_register_partner_confirm_wizard(invoice.ids, confirm_date)
        wizard.vehicle_id = self.vehicle.id
        wizard.responsible_employee_ids = [(6, 0, self.employee.ids)]
        wizard.receipt_person = "John Doe"
        wizard.observations = "Test observations"
        wizard.register_confirmation()

        confirmation = invoice.part_confirm_id
        msg = invoice.get_delete_partner_conf_message(confirmation)
        self.assertIn("15/06/2024", msg)
        self.assertIn("Test Vehicle", msg)
        self.assertIn("John Doe", msg)
        self.assertIn("Test Employee", msg)
        self.assertIn("Test observations", msg)

    def test_computed_fields_on_invoice(self):
        """Test part_conf_one_id, part_confirm_date, part_confirm_vehicle_id."""
        invoice = self.create_invoice()
        self.assertFalse(invoice.part_conf_one_id)
        self.assertFalse(invoice.part_confirm_date)
        self.assertFalse(invoice.part_confirm_vehicle_id)

        confirm_date = date(2024, 1, 10)
        wizard = self.create_register_partner_confirm_wizard(invoice.ids, confirm_date)
        wizard.vehicle_id = self.vehicle.id
        wizard.register_confirmation()

        self.assertTrue(invoice.part_conf_one_id)
        self.assertEqual(invoice.part_conf_one_id, invoice.part_confirm_id[0])
        self.assertEqual(invoice.part_confirm_date, confirm_date)
        self.assertEqual(invoice.part_confirm_vehicle_id, self.vehicle)

    def test_company_id_from_invoice(self):
        """Test that confirmation company_id comes from the invoice."""
        invoice = self.create_invoice()
        wizard = self.create_register_partner_confirm_wizard(invoice.ids)
        wizard.register_confirmation()

        confirmation = invoice.part_confirm_id
        self.assertEqual(confirmation.company_id, invoice.company_id)

    def test_responsible_unlink_protection(self):
        """Test that a responsible linked to confirmations cannot be deleted."""
        invoice = self.create_invoice()
        wizard = self.create_register_partner_confirm_wizard(invoice.ids)
        wizard.responsible_employee_ids = [(6, 0, self.employee.ids)]
        wizard.register_confirmation()

        with self.assertRaises(UserError):
            self.employee.unlink()

    def test_responsible_unlink_allowed_when_not_linked(self):
        """Test that a responsible without confirmations can be deleted."""
        responsible = self.env["partner.confirmation.responsible"].create(
            {"name": "Temporary Responsible"}
        )
        responsible.unlink()
        self.assertFalse(responsible.exists())

    def test_vehicle_ondelete_restrict(self):
        """Test that a vehicle linked to confirmations cannot be deleted."""
        invoice = self.create_invoice()
        wizard = self.create_register_partner_confirm_wizard(invoice.ids)
        wizard.vehicle_id = self.vehicle.id
        wizard.register_confirmation()

        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.vehicle.unlink()

    def test_confirmation_order(self):
        """Test that confirmations are ordered by date desc."""
        invoice1 = self.create_invoice()
        invoice2 = self.create_invoice()
        invoice3 = self.create_invoice()

        wizard1 = self.create_register_partner_confirm_wizard(
            invoice1.ids, date(2024, 1, 1)
        )
        wizard1.register_confirmation()

        wizard2 = self.create_register_partner_confirm_wizard(
            invoice2.ids, date(2024, 6, 15)
        )
        wizard2.register_confirmation()

        wizard3 = self.create_register_partner_confirm_wizard(
            invoice3.ids, date(2024, 3, 10)
        )
        wizard3.register_confirmation()

        confirmations = self.partner_confirm_obj.search(
            [("invoice_id", "in", [invoice1.id, invoice2.id, invoice3.id])]
        )
        dates = confirmations.mapped("confirmation_date")
        self.assertEqual(dates[0], date(2024, 6, 15))
        self.assertEqual(dates[1], date(2024, 3, 10))
        self.assertEqual(dates[2], date(2024, 1, 1))

    @mute_logger("odoo.sql_db")
    def test_sql_constraint_unique_invoice(self):
        """Test that the same invoice cannot have two confirmations."""
        invoice = self.create_invoice()
        wizard = self.create_register_partner_confirm_wizard(invoice.ids)
        wizard.register_confirmation()

        with self.assertRaises(IntegrityError):
            self.partner_confirm_obj.create(
                {
                    "name": "Duplicate",
                    "confirmation_date": date.today(),
                    "invoice_id": invoice.id,
                    "state": "confirmed",
                }
            )
