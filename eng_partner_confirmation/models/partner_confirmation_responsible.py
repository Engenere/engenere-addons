# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError


class PartnerConfirmationResponsible(models.Model):
    _name = "partner.confirmation.responsible"
    _description = "Partner Confirmation Responsible"

    name = fields.Char(required=True)

    def unlink(self):
        confirmations = self.env["account.invoice.partner.confirmation"].search(
            [("responsible_employee_ids", "in", self.ids)]
        )
        if confirmations:
            raise UserError(
                _(
                    "You cannot delete a responsible that is linked to"
                    " partner confirmations."
                )
            )
        return super().unlink()
