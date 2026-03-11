# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ConsortiumReadjustment(models.Model):
    _name = "consortium.readjustment"
    _description = "Consortium Readjustment"
    _order = "date desc"

    quota_id = fields.Many2one(
        comodel_name="consortium.quota",
        required=True,
        ondelete="cascade",
    )
    date = fields.Date(
        required=True,
        default=fields.Date.today,
    )
    previous_credit_value = fields.Monetary(
        currency_field="currency_id",
    )
    new_credit_value = fields.Monetary(
        currency_field="currency_id",
    )
    adjustment_percentage = fields.Float(
        compute="_compute_adjustment_percentage",
        store=True,
    )
    previous_installment_amount = fields.Monetary(
        currency_field="currency_id",
    )
    new_installment_amount = fields.Monetary(
        currency_field="currency_id",
    )
    notes = fields.Text()
    applied_by = fields.Many2one(
        comodel_name="res.users",
        default=lambda self: self.env.user,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="quota_id.currency_id",
    )

    @api.depends("previous_credit_value", "new_credit_value")
    def _compute_adjustment_percentage(self):
        for readjustment in self:
            if readjustment.previous_credit_value:
                readjustment.adjustment_percentage = (
                    (readjustment.new_credit_value - readjustment.previous_credit_value)
                    / readjustment.previous_credit_value
                    * 100
                )
            else:
                readjustment.adjustment_percentage = 0.0
