# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ConsortiumQuotaComponent(models.Model):
    _name = "consortium.quota.component"
    _description = "Consortium Quota Component Configuration"

    quota_id = fields.Many2one(
        comodel_name="consortium.quota",
        required=True,
        ondelete="cascade",
    )
    component_type_id = fields.Many2one(
        comodel_name="consortium.component.type",
        required=True,
    )
    account_id = fields.Many2one(
        comodel_name="account.account",
        required=True,
    )

    _sql_constraints = [
        (
            "quota_component_type_uniq",
            "UNIQUE(quota_id, component_type_id)",
            "Component type must be unique per quota.",
        ),
    ]
