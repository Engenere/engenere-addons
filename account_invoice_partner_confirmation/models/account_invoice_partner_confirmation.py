# Copyright 2022 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountInvoicePartnerConfirmation(models.Model):

    _name = "account.invoice.partner.confirmation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Receipt of goods from the partners in account invoices"
    _sql_constraints = [
        (
            "partner_confirmation_invoice_id_unique",
            "unique (invoice_id)",
            "There is already an invoice for this Partner Confirmation",
        )
    ]

    name = fields.Char(readonly=True)

    confirmation_date = fields.Date("Confirmation Date", required=True, tracking=True)

    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice",
        required=True,
        readonly=True,
        tracking=True,
        ondelete="cascade",
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        related="invoice_id.partner_id",
        readonly=True,
    )

    state = fields.Selection(
        [
            ("with_pendencies", "With Pendencies"),
            ("confirmed", "Confirmed"),
        ],
        string="State",
        required=True,
        tracking=True,
    )

    vehicle_id = fields.Many2one("fleet.vehicle", string="Vehicle", tracking=True)

    observations = fields.Text("Observations", tracking=True)

    related_file_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Related Files",
        ondelete="cascade",
        tracking=True,
    )

    receipt_person = fields.Char("Receipt Person", tracking=True)

    responsible_employee_ids = fields.Many2many(
        "hr.employee", string="Responsible Employees", tracking=True
    )
