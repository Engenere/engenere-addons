# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ConsortiumInstallment(models.Model):
    _name = "consortium.installment"
    _description = "Consortium Installment"
    _order = "quota_id, number"

    name = fields.Char(
        compute="_compute_name",
        store=True,
    )
    quota_id = fields.Many2one(
        comodel_name="consortium.quota",
        required=True,
        ondelete="cascade",
    )
    number = fields.Integer(required=True)
    due_date = fields.Date(required=True)
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("open", "Open"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
    )
    is_lance = fields.Boolean(default=False)
    total_amount = fields.Monetary(
        compute="_compute_total_amount",
        store=True,
    )
    component_ids = fields.One2many(
        comodel_name="consortium.installment.component",
        inverse_name="installment_id",
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="quota_id.company_id",
        store=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="quota_id.currency_id",
    )
    administrator_id = fields.Many2one(
        comodel_name="res.partner",
        related="quota_id.administrator_id",
        store=True,
    )
    notes = fields.Text()

    _sql_constraints = [
        (
            "quota_number_uniq",
            "UNIQUE(quota_id, number)",
            "Installment number must be unique per quota.",
        ),
    ]

    @api.depends("number", "quota_id.total_installments")
    def _compute_name(self):
        for installment in self:
            total = installment.quota_id.total_installments or 0
            installment.name = f"Installment {installment.number}/{total}"

    @api.depends("component_ids.amount")
    def _compute_total_amount(self):
        for installment in self:
            installment.total_amount = sum(installment.component_ids.mapped("amount"))

    def action_view_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_mark_paid(self):
        self.write({"state": "paid"})
