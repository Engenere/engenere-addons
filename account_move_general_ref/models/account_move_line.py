# Copyright (C) 2023-Today - Engenere (<https://engenere.one>).
# @author Felipe Motter Pereira <felipe@engenere.one>

from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    partner_order = fields.Text(
        compute="_compute_partner_order",
        store=True,
        readonly=False,
    )

    @api.model
    def create(self, vals):
        if "partner_order" not in vals and "move_id" in vals:
            account_move = self.env["account.move"].browse(vals["move_id"])
            if account_move.ref:
                vals["partner_order"] = account_move.ref
        return super().create(vals)

    @api.depends("move_id", "move_id.ref")
    def _compute_partner_order(self):
        if hasattr(super(), "_compute_partner_order"):
            super()._compute_partner_order()
        for line in self:
            line.partner_order = line.move_id.ref
