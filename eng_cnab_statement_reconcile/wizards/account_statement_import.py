# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, formatLang


class AccountStatementImport(models.TransientModel):
    _inherit = "account.statement.import"

    def _create_bank_statements(self, stmts_vals, result):
        # A transaction imported again with the same content is skipped by
        # the standard import; with another date or amount it is a conflict
        self._eng_check_unique_import_id_conflicts(stmts_vals)
        return super()._create_bank_statements(stmts_vals, result)

    def _eng_check_unique_import_id_conflicts(self, stmts_vals):
        """Refuse the file when a known transaction id (the FITID of an OFX
        file) comes back with another date or amount."""
        st_line_model = self.env["account.bank.statement.line"].sudo()
        conflicts = []
        for st_vals in stmts_vals:
            for line_vals in st_vals["transactions"]:
                unique_import_id = line_vals.get("unique_import_id")
                if not unique_import_id:
                    continue
                existing_line = st_line_model.search(
                    [("unique_import_id", "=", unique_import_id)], limit=1
                )
                if not existing_line:
                    continue
                currency = existing_line.currency_id
                line_date = fields.Date.to_date(line_vals["date"])
                amount = float(line_vals["amount"])
                if existing_line.date == line_date and not currency.compare_amounts(
                    existing_line.amount, amount
                ):
                    continue
                conflicts.append(
                    _(
                        "Transaction %(transaction)s: imported on %(old_date)s for "
                        "%(old_amount)s, now on %(new_date)s for %(new_amount)s.",
                        transaction=unique_import_id,
                        old_date=format_date(self.env, existing_line.date),
                        old_amount=formatLang(
                            self.env, existing_line.amount, currency_obj=currency
                        ),
                        new_date=format_date(self.env, line_date),
                        new_amount=formatLang(self.env, amount, currency_obj=currency),
                    )
                )
        if conflicts:
            raise UserError(
                _(
                    "The bank statement file was not imported: some of its "
                    "transactions were already imported with the same identifier "
                    "but another date or amount. Check the file with the bank.\n"
                    "%(conflicts)s",
                    conflicts="\n".join(conflicts),
                )
            )
