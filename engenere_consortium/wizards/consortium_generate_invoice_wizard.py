# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError


class ConsortiumGenerateInvoiceWizard(models.TransientModel):
    _name = "consortium.generate.invoice.wizard"
    _description = "Generate Invoice from Consortium Installments"

    installment_ids = fields.Many2many(
        comodel_name="consortium.installment",
        default=lambda self: self.env.context.get("active_ids"),
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        required=True,
        domain=[("type", "=", "purchase")],
        default=lambda self: self.env["account.journal"].search(
            [
                ("type", "=", "purchase"),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        ),
    )
    invoice_date = fields.Date(
        default=fields.Date.today,
    )

    def action_generate(self):
        self.ensure_one()
        created_moves = self.env["account.move"]
        for installment in self.installment_ids:
            if installment.move_id:
                raise UserError(
                    _(
                        "Installment %s already has an invoice.",
                        installment.name,
                    )
                )
            if not installment.component_ids:
                raise UserError(
                    _(
                        "Installment %s has no components.",
                        installment.name,
                    )
                )
            invoice_lines = []
            for component in installment.component_ids:
                account = (
                    component.account_id
                    or component.component_type_id.default_account_id
                )
                invoice_lines.append(
                    (
                        0,
                        0,
                        {
                            "name": component.component_type_id.name,
                            "account_id": account.id if account else False,
                            "price_unit": component.amount,
                            "quantity": 1,
                            "tax_ids": [(5, 0, 0)],
                        },
                    )
                )
            move = self.env["account.move"].create(
                {
                    "move_type": "in_invoice",
                    "partner_id": installment.administrator_id.id,
                    "journal_id": self.journal_id.id,
                    "invoice_date": self.invoice_date or installment.due_date,
                    "ref": (
                        f"Consortium {installment.quota_id.name} "
                        f"- Installment {installment.number}"
                    ),
                    "invoice_line_ids": invoice_lines,
                }
            )
            installment.move_id = move
            installment.state = "open"
            created_moves |= move
        if len(created_moves) == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": created_moves.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "tree,form",
            "domain": [("id", "in", created_moves.ids)],
            "target": "current",
        }
