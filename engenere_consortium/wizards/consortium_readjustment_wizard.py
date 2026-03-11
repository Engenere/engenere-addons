# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ConsortiumReadjustmentWizard(models.TransientModel):
    _name = "consortium.readjustment.wizard"
    _description = "Consortium Readjustment Wizard"

    quota_id = fields.Many2one(
        comodel_name="consortium.quota",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="quota_id.currency_id",
    )
    current_credit_value = fields.Monetary(
        related="quota_id.current_credit_value",
        readonly=True,
    )
    new_credit_value = fields.Monetary(
        required=True,
    )
    adjustment_percentage = fields.Float(
        compute="_compute_adjustment_percentage",
        inverse="_inverse_adjustment_percentage",
    )
    effective_date = fields.Date(
        required=True,
        default=fields.Date.today,
    )
    recalculate_future = fields.Boolean(
        default=True,
        help="Proportionally recalculate common fund component of "
        "unpaid installments",
    )
    notes = fields.Text()

    @api.depends("current_credit_value", "new_credit_value")
    def _compute_adjustment_percentage(self):
        for wizard in self:
            if wizard.current_credit_value:
                wizard.adjustment_percentage = (
                    (wizard.new_credit_value - wizard.current_credit_value)
                    / wizard.current_credit_value
                    * 100
                )
            else:
                wizard.adjustment_percentage = 0.0

    def _inverse_adjustment_percentage(self):
        for wizard in self:
            wizard.new_credit_value = wizard.current_credit_value + (
                wizard.current_credit_value * wizard.adjustment_percentage / 100
            )

    def action_apply(self):
        self.ensure_one()
        self.env["consortium.readjustment"].create(
            {
                "quota_id": self.quota_id.id,
                "date": self.effective_date,
                "previous_credit_value": self.current_credit_value,
                "new_credit_value": self.new_credit_value,
                "notes": self.notes,
            }
        )
        self.quota_id.current_credit_value = self.new_credit_value
        if self.recalculate_future:
            factor = 1 + self.adjustment_percentage / 100
            unpaid_installments = self.quota_id.installment_ids.filtered(
                lambda inst: inst.state in ("draft", "open")
            )
            for installment in unpaid_installments:
                common_fund_components = installment.component_ids.filtered(
                    lambda comp: comp.component_type_id.code == "common_fund"
                )
                for component in common_fund_components:
                    component.amount = component.amount * factor
        return {"type": "ir.actions.act_window_close"}
