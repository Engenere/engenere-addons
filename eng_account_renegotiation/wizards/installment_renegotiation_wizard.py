# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

CNAB_METHOD_CODES = ("240", "400", "500")


class InstallmentRenegotiationWizard(models.TransientModel):
    _inherit = "account.installment.renegotiation.wizard"

    header_payment_mode_id = fields.Many2one(
        comodel_name="account.payment.mode",
        string="New Invoice Payment Mode",
        help="Also replace the payment mode on the invoice header. All new "
        "installments will use this mode.",
    )

    expected_payment_type = fields.Selection(
        selection=[("inbound", "Inbound"), ("outbound", "Outbound")],
        compute="_compute_expected_payment_type",
    )

    @api.depends("move_id.move_type")
    def _compute_expected_payment_type(self):
        for wizard in self:
            wizard.expected_payment_type = (
                "inbound" if wizard.move_id.is_inbound() else "outbound"
            )

    @api.onchange("payment_term_id", "starting_date")
    def _onchange_payment_term_id(self):
        """Upstream regenerates the lines with the move's current mode;
        reapply the chosen header mode so the wizard does not create the
        mixture its own consistency guard refuses."""
        res = super()._onchange_payment_term_id()
        if self.header_payment_mode_id:
            for line in self.line_ids:
                line.payment_mode_id = self.header_payment_mode_id
        return res

    @api.onchange("header_payment_mode_id")
    def _onchange_header_payment_mode_id(self):
        """A header mode swap forces every new installment to that mode."""
        if self.header_payment_mode_id:
            for line in self.line_ids:
                line.payment_mode_id = self.header_payment_mode_id

    def _eng_header_mode_changed(self):
        self.ensure_one()
        return bool(
            self.header_payment_mode_id
            and self.header_payment_mode_id != self.move_id.payment_mode_id
        )

    def _eng_check_partial_reconciliation(self):
        """Refuse renegotiating over a partially reconciled installment.

        The upstream wizard only skips fully reconciled lines; a partially
        reconciled one would blow up later in the core unlink(), midway
        through the surgery. Fail clean and early instead, for every
        profile (managers hit the same core error upstream today).
        """
        self.ensure_one()
        partial_lines = self.move_id.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
            and not line.reconciled
            and (line.matched_debit_ids or line.matched_credit_ids)
        )
        if partial_lines:
            raise UserError(
                _(
                    "Installments with a partial payment cannot be "
                    "renegotiated: %(dates)s. Unreconcile the partial "
                    "payment first.",
                    dates=", ".join(str(line.date_maturity) for line in partial_lines),
                )
            )

    def _eng_check_header_mode_consistency(self):
        """A header mode swap must match the document direction and cannot
        be mixed with divergent per-line modes."""
        self.ensure_one()
        if not self._eng_header_mode_changed():
            return
        # The view domain is client-side only: an RPC write could push an
        # inbound mode into a vendor bill (or the opposite) and the sudo()
        # surgery would take it to the journal entry
        expected = "inbound" if self.move_id.is_inbound() else "outbound"
        if self.header_payment_mode_id.payment_method_id.payment_type != expected:
            raise UserError(
                _(
                    "The new invoice payment mode must be of type %(expected)s "
                    "for this document.",
                    expected=expected,
                )
            )
        mixed = self.line_ids.filtered(
            lambda line: line.payment_mode_id != self.header_payment_mode_id
        )
        if mixed:
            raise UserError(
                _(
                    "When replacing the invoice payment mode, all "
                    "installments must use the new mode. Clear the manual "
                    "modes or the new invoice payment mode."
                )
            )

    def _validate_renegotiation(self):
        self.ensure_one()
        # Guards for every profile, managers included
        self._eng_check_partial_reconciliation()
        self._eng_check_header_mode_consistency()
        if self.env.user.has_group("account.group_account_manager"):
            return super()._validate_renegotiation()
        # Reads move_id in the user's environment: ACLs and record rules
        # apply here, including a move_id swapped in through an RPC write
        self.move_id._eng_check_can_renegotiate_vendor_bill()
        return self._eng_validate_renegotiation_terms()

    def _eng_validate_renegotiation_terms(self):
        """Mirror of the upstream non-permission validations
        (l10n_br_account_renegotiation 16.0.1.0.0 _validate_renegotiation),
        which are unreachable for non-managers because the upstream method
        starts with a hardcoded Invoicing Manager check.
        """
        self.ensure_one()

        if self.move_id.state != "posted":
            raise UserError(
                _("The invoice must be posted to renegotiate installments.")
            )

        precision = self.currency_id.rounding
        if float_compare(self.difference, 0, precision_rounding=precision) != 0:
            raise UserError(
                _(
                    "The total amount of installments must remain unchanged. "
                    "Current difference: %(diff)s",
                    diff=self.currency_id.format(self.difference),
                )
            )

        if not self.line_ids:
            raise UserError(_("You must have at least one installment."))

        if any(line.amount <= 0 for line in self.line_ids):
            raise UserError(_("All installment amounts must be greater than zero."))

        if any(not line.date_maturity for line in self.line_ids):
            raise UserError(_("All installments must have a due date."))

    def _eng_mode_is_cnab(self, mode):
        return bool(mode and mode.payment_method_code in CNAB_METHOD_CODES)

    def _eng_generate_boleto_if_applicable(self, mode):
        """Reissue the boleto PDF after a CNAB reschedule (inbound only)."""
        self.ensure_one()
        move = self.move_id
        if (
            move.is_inbound()
            and self._eng_mode_is_cnab(mode)
            and hasattr(move, "generate_boleto_pdf")
        ):
            move.generate_boleto_pdf()

    def action_apply(self):
        self.ensure_one()
        if self._eng_header_mode_changed():
            return self._eng_apply_with_header_mode()
        res = super().action_apply()
        # Upstream already ran baixa + load_cnab_info; the old
        # trento_invoice_change_payment_data behavior also reissued the
        # boleto PDF on any CNAB reschedule
        self._eng_generate_boleto_if_applicable(self.move_id.payment_mode_id)
        return res

    def _eng_apply_with_header_mode(self):
        """Apply the renegotiation replacing the invoice payment mode.

        Controlled mirror of the upstream action_apply()
        (l10n_br_account_renegotiation 16.0.1.0.0): the header cannot be
        written before the snapshot/CNAB write-off (it would corrupt both)
        nor after the new lines and load_cnab_info() (they must already run
        with the new configuration), and upstream offers no hook at that
        point.
        """
        self.ensure_one()
        self._validate_renegotiation()

        move = self.move_id
        new_mode = self.header_payment_mode_id
        old_mode = move.payment_mode_id

        original_lines = move.line_ids.filtered(
            lambda line: line.display_type == "payment_term" and not line.reconciled
        )

        old_lines_data = []
        for line in original_lines.sorted("date_maturity"):
            data = {
                "date_maturity": line.date_maturity,
                "amount_currency": line.amount_currency,
            }
            if "payment_mode_id" in line._fields and line.payment_mode_id:
                data["payment_mode"] = line.payment_mode_id.name
            old_lines_data.append(data)

        # DUCK TYPING: CNAB write-off runs with the OLD configuration
        for line in original_lines:
            if hasattr(line, "payment_line_ids"):
                if hasattr(line, "_cnab_already_start") and line._cnab_already_start():
                    line.update_cnab_for_cancel_invoice()
                else:
                    line.payment_line_ids.unlink()

        sign = 1 if move.is_inbound() else -1

        ctx = dict(
            self.env.context,
            skip_invoice_sync=True,
            allow_installment_renegotiation=True,
            check_move_validity=False,
        )

        account_id = original_lines[0].account_id.id

        wizard_lines = self.line_ids.sorted("date_maturity")
        new_line_vals = []
        for wiz_line in wizard_lines:
            amount_currency = sign * wiz_line.amount
            if move.currency_id != move.company_currency_id:
                balance = move.currency_id._convert(
                    amount_currency,
                    move.company_currency_id,
                    move.company_id,
                    move.date,
                )
            else:
                balance = amount_currency
            new_line_vals.append(
                {
                    "date_maturity": wiz_line.date_maturity,
                    "amount_currency": amount_currency,
                    "debit": balance if balance > 0 else 0,
                    "credit": -balance if balance < 0 else 0,
                    "account_id": account_id,
                    "payment_mode_id": new_mode.id,
                }
            )

        header_vals = {"payment_mode_id": new_mode.id}
        if (
            self.payment_term_id
            and move.invoice_payment_term_id != self.payment_term_id
        ):
            header_vals["invoice_payment_term_id"] = self.payment_term_id.id

        original_lines.with_context(
            **ctx, dynamic_unlink=True, force_delete=True
        ).sudo().unlink()

        # The header must change after the old-config write-off and before
        # the new lines / load_cnab_info()
        move.with_context(**ctx).sudo().write(header_vals)

        for vals in new_line_vals:
            self.env["account.move.line"].with_context(**ctx).sudo().create(
                {
                    "move_id": move.id,
                    "display_type": "payment_term",
                    "name": "",
                    "account_id": vals["account_id"],
                    "date_maturity": vals["date_maturity"],
                    "amount_currency": vals["amount_currency"],
                    "debit": vals["debit"],
                    "credit": vals["credit"],
                    "currency_id": move.currency_id.id,
                    "partner_id": move.partner_id.id,
                    "payment_mode_id": vals["payment_mode_id"],
                }
            )

        move.with_context(**ctx).update_payment_term_number()

        # CNAB registration + boleto only when the NEW mode is CNAB
        if self._eng_mode_is_cnab(new_mode) and hasattr(move, "load_cnab_info"):
            move.load_cnab_info()
        self._eng_generate_boleto_if_applicable(new_mode)

        new_lines = move.line_ids.filtered(
            lambda line: line.display_type == "payment_term" and not line.reconciled
        )
        new_lines_data = []
        for line in new_lines.sorted("date_maturity"):
            data = {
                "date_maturity": line.date_maturity,
                "amount_currency": line.amount_currency,
            }
            if hasattr(line, "payment_mode_id") and line.payment_mode_id:
                data["payment_mode"] = line.payment_mode_id.name
            new_lines_data.append(data)

        message = move._get_installment_renegotiation_message(
            old_lines_data, new_lines_data
        )
        move.message_post(body=message)
        move.message_post(
            body=_(
                "Invoice payment mode replaced during renegotiation: "
                "%(old)s → %(new)s",
                old=old_mode.name or _("(none)"),
                new=new_mode.name,
            )
        )

        return {"type": "ir.actions.act_window_close"}
