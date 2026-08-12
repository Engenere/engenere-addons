# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

VENDOR_MOVE_TYPES = ("in_invoice", "in_receipt")


class AccountMove(models.Model):
    _inherit = "account.move"

    def _eng_can_renegotiate_vendor_bill(self):
        """Whether the current user may renegotiate this vendor document.

        Runs in the user's environment on purpose. The explicit access
        checks enforce ACLs and record rules even when the record is
        already in cache (a plain field read would be served from cache
        without any check).
        """
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        # The surgery writes through sudo(): without these, a user allowed
        # to read but blocked from writing by an ir.rule could renegotiate
        self.check_access_rights("write")
        self.check_access_rule("write")
        user = self.env.user
        return (
            self.move_type in VENDOR_MOVE_TYPES
            and user.has_group("account.group_account_invoice")
            and user.has_group(
                "eng_account_renegotiation" ".group_vendor_bill_renegotiation"
            )
        )

    def _eng_check_can_renegotiate_vendor_bill(self):
        self.ensure_one()
        if not self._eng_can_renegotiate_vendor_bill():
            raise UserError(
                _(
                    "Only users with 'Billing Administrator' rights or, for "
                    "vendor bills, Billing users in the 'Renegotiate Vendor "
                    "Bill Installments' group can renegotiate installments."
                )
            )

    @api.depends_context("uid")
    def _compute_can_renegotiate_installments(self):
        super()._compute_can_renegotiate_installments()
        if self.env.user.has_group("account.group_account_manager"):
            return
        for move in self:
            if not move.can_renegotiate_installments:
                continue
            try:
                allowed = move._eng_can_renegotiate_vendor_bill()
            except AccessError:
                allowed = False
            move.can_renegotiate_installments = allowed

    def action_renegotiate_installments(self):
        self.ensure_one()
        if self.env.user.has_group("account.group_account_manager"):
            return super().action_renegotiate_installments()
        self._eng_check_can_renegotiate_vendor_bill()
        return self._eng_open_renegotiation_wizard()

    def _eng_open_renegotiation_wizard(self):
        """Open the renegotiation wizard for an authorized non-manager user.

        Mirror of the non-permission part of the upstream
        action_renegotiate_installments() (l10n_br_account_renegotiation
        16.0.1.0.0), which hardcodes the Invoicing Manager check and thus
        cannot be called for these users.
        """
        self.ensure_one()
        if self.state != "posted":
            raise UserError(
                _("You can only renegotiate installments on posted invoices.")
            )
        unreconciled_payment_lines = self.line_ids.filtered(
            lambda line: line.display_type == "payment_term" and not line.reconciled
        )
        if not unreconciled_payment_lines:
            raise UserError(
                _(
                    "There are no unreconciled payment term lines to "
                    "renegotiate. All installments have been paid or "
                    "reconciled."
                )
            )
        wizard = self.env["account.installment.renegotiation.wizard"].create(
            {"move_id": self.id}
        )
        return {
            "name": _("Renegotiate Installments"),
            "type": "ir.actions.act_window",
            "res_model": "account.installment.renegotiation.wizard",
            "view_mode": "form",
            "res_id": wizard.id,
            "target": "new",
            "context": self.env.context,
        }

    def _get_installment_renegotiation_message(self, old_lines_data, new_lines_data):
        """Localizable replacement of the upstream chatter message.

        Same terms as upstream, but owned by this module so _() resolves
        them against this module's translations (Odoo 16 loads Python code
        translations only from the po files of the module that calls _()).
        """
        currency = self.currency_id

        def format_line(line_data):
            base = _("%(date)s: %(amount)s") % {
                "date": line_data["date_maturity"],
                "amount": currency.format(abs(line_data["amount_currency"])),
            }
            if line_data.get("payment_mode"):
                base += f" ({line_data['payment_mode']})"
            return base

        old_summary = "<br/>".join(format_line(line) for line in old_lines_data)
        new_summary = "<br/>".join(format_line(line) for line in new_lines_data)

        return _(
            "<p><strong>Payment Installments Renegotiated</strong></p>"
            "<p><strong>Previous installments:</strong><br/>%(old)s</p>"
            "<p><strong>New installments:</strong><br/>%(new)s</p>"
        ) % {
            "old": old_summary,
            "new": new_summary,
        }
