# Copyright 2022 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountInvoicePartnerConfirmationRegister(models.TransientModel):

    _name = "account.invoice.partner.confirmation.register"
    _description = "Register Partner Confirmation"

    confirmation_date = fields.Date("Confirmation Date", required=True)

    state = fields.Selection(
        [
            ("with_pendencies", "With Pendencies"),
            ("confirmed", "Confirmed"),
        ],
        string="State",
        required=True,
        default="confirmed",
    )

    vehicle_id = fields.Many2one("fleet.vehicle", string="Vehicle")

    observations = fields.Text("Observations")

    related_file_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Related Files",
        ondelete="cascade",
    )

    receipt_person = fields.Char("Receipt Person")

    responsible_employee_ids = fields.Many2many(
        "hr.employee", string="Responsible Employees"
    )

    batch_register = fields.Boolean("Batch Register", compute="_compute_batch_register")

    active_invoices_ids = fields.Many2many("account.move", string="Active Invoices")

    @api.model
    def default_get(self, fields_list):
        # OVERRIDE
        res = super().default_get(fields_list)

        if "active_invoices_ids" in fields_list and "active_invoices_ids" not in res:

            if self._context.get("active_model") != "account.move":
                raise UserError(
                    _(
                        "The register partner confirmation wizard should only be called "
                        "on account.move records."
                    )
                )

            invoice_ids = self.env["account.move"].browse(
                self._context.get("active_ids", [])
            )

            for invoice in invoice_ids:

                if invoice.move_type != "out_invoice":
                    raise UserError(
                        _(
                            "You cannot select invoices with move type different"
                            "of 'out_invoice'.\n\nInvoice: " + invoice.name
                        )
                    )

                if invoice.state != "posted":
                    raise UserError(
                        _(
                            "You can only select posted invoices.\n\nInvoice: "
                            + invoice.name
                        )
                    )

                if invoice.part_confirm_id:
                    raise UserError(
                        _(
                            "You cannot select invoices for which the partner "
                            "has already confirmed receipt of goods.\n\nInvoice: "
                            + invoice.name
                        )
                    )

            res["active_invoices_ids"] = [(6, 0, invoice_ids.ids)]

        return res

    @api.depends("active_invoices_ids")
    def _compute_batch_register(self):
        for wizard in self:
            wizard.batch_register = len(wizard.active_invoices_ids) - 1

    def get_confirmantion_vals(self, invoice_id):

        return {
            "name": "Confirmation - " + invoice_id.name,
            "confirmation_date": self.confirmation_date,
            "invoice_id": invoice_id.id,
            "state": self.state,
            "vehicle_id": self.vehicle_id.id,
            "observations": self.observations,
            "related_file_ids": [(6, 0, self.related_file_ids.ids)],
            "receipt_person": self.receipt_person,
            "responsible_employee_ids": [(6, 0, self.responsible_employee_ids.ids)],
        }

    def create_partner_confirmations(self):
        partner_confirmation_ids = []
        partner_conf_model = self.env["account.invoice.partner.confirmation"]

        for invoice_id in self.active_invoices_ids:
            partner_conf_vals = self.get_confirmantion_vals(invoice_id)
            partner_confirmation_id = partner_conf_model.create(partner_conf_vals)
            partner_confirmation_ids.append(partner_confirmation_id.id)

        return partner_confirmation_ids

    def register_confirmation(self):
        self.ensure_one()

        partner_confirmation_ids = self.create_partner_confirmations()

        action = {
            "name": _("Partner Confirmation"),
            "type": "ir.actions.act_window",
            "res_model": "account.invoice.partner.confirmation",
            "context": {"create": False},
        }

        if not self.batch_register:
            action.update(
                {
                    "view_mode": "form",
                    "res_id": partner_confirmation_ids[0],
                }
            )
        else:
            action.update(
                {
                    "view_mode": "tree",
                    "domain": [("id", "in", partner_confirmation_ids)],
                }
            )

        return action
