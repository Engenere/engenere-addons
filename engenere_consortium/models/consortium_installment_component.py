# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ConsortiumInstallmentComponent(models.Model):
    _name = "consortium.installment.component"
    _description = "Consortium Installment Component"

    installment_id = fields.Many2one(
        comodel_name="consortium.installment",
        required=True,
        ondelete="cascade",
    )
    component_type_id = fields.Many2one(
        comodel_name="consortium.component.type",
        required=True,
    )
    amount = fields.Monetary(required=True)
    account_id = fields.Many2one(
        comodel_name="account.account",
        string="Account",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="installment_id.currency_id",
    )

    @api.onchange("component_type_id")
    def _onchange_component_type_id(self):
        if not self.component_type_id:
            return
        quota = self.installment_id.quota_id
        matching_config = quota.component_config_ids.filtered(
            lambda config: (config.component_type_id == self.component_type_id)
        )
        if matching_config:
            self.account_id = matching_config[0].account_id
        elif self.component_type_id.default_account_id:
            self.account_id = self.component_type_id.default_account_id
