# Copyright 2022 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountInvoicePartnerConfirmation(models.Model):
    _name = "account.invoice.partner.confirmation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Receipt of goods from the partners in account invoices"
    _check_company_auto = True
    _sql_constraints = [
        (
            "partner_confirmation_invoice_id_unique",
            "unique (invoice_id)",
            "There is already an invoice for this Partner Confirmation",
        )
    ]

    name = fields.Char(readonly=True)

    confirmation_date = fields.Date(required=True, tracking=True)

    company_id = fields.Many2one(
        "res.company",
        related="invoice_id.company_id",
        store=True,
    )

    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice",
        required=True,
        readonly=True,
        tracking=True,
        ondelete="cascade",
        check_company=True,
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
        required=True,
        tracking=True,
    )

    vehicle_id = fields.Many2one(
        "partner.confirmation.vehicle",
        string="Vehicle",
        tracking=True,
        ondelete="restrict",
    )

    observations = fields.Text(tracking=True)

    related_file_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Related Files",
        ondelete="cascade",
        tracking=True,
    )

    receipt_person = fields.Char(tracking=True)

    responsible_employee_ids = fields.Many2many(
        "partner.confirmation.responsible",
        relation="confirmation_responsible_rel",
        string="Responsible Employees",
        tracking=True,
    )
