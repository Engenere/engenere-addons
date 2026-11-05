# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountReconcileModel(models.Model):
    _inherit = "account.reconcile.model"

    eng_cnab_clearing_match = fields.Boolean(
        string="CNAB Clearing Matching",
        tracking=True,
        help="Match the bank statement line with the whole group of open CNAB "
        "clearing lines of its journal due on its date, and only when the "
        "group sums exactly the amount of the line: no partial group, no "
        "tolerance and no write-off. A statement line that meets the "
        "conditions of such a rule is matched by these rules only, never by "
        "the other reconciliation models.",
    )
    eng_receiving_bank_filter = fields.Selection(
        selection=[
            ("any", "Any Bank"),
            ("own", "Own Bank"),
            ("other", "Other Banks"),
        ],
        string="Receiving Bank",
        default="any",
        required=True,
        tracking=True,
        help="CNAB clearing lines of the group, by the bank where the "
        "customer paid: any bank, the bank of the journal only, or the other "
        "banks only. Use the last two when the bank statement splits the "
        "collection credit of a day by receiving bank. For Ailos, the bank of "
        "the journal is its own credit union: a title paid at another credit "
        "union counts as another bank.",
    )

    @api.constrains("eng_cnab_clearing_match", "rule_type", "auto_reconcile")
    def _check_eng_cnab_clearing_match(self):
        for rule in self.filtered("eng_cnab_clearing_match"):
            if rule.rule_type != "invoice_matching":
                raise ValidationError(
                    _(
                        "The CNAB clearing matching of the rule %(rule)s needs "
                        "the type 'Rule to match invoices/bills'.",
                        rule=rule.display_name,
                    )
                )
            if not rule.auto_reconcile:
                raise ValidationError(
                    _(
                        "The rule %(rule)s matches CNAB clearing lines, which is "
                        "always automatic: enable its Auto-validate option.",
                        rule=rule.display_name,
                    )
                )

    # Exclusive routing

    @api.model
    def _eng_cnab_get_routing_rules(self, st_line, partner):
        """CNAB clearing rules whose conditions the statement line meets.

        Only a statement line of a journal with the CNAB clearing flow, dated
        on or after its cutover date, is routed, even when the configuration
        of the journal has become invalid since: the older lines and the
        other journals keep the generic matching.
        """
        if not st_line._eng_cnab_in_clearing_flow():
            return self.browse()
        rules = self.search(
            [
                ("eng_cnab_clearing_match", "=", True),
                ("rule_type", "=", "invoice_matching"),
                ("company_id", "=", st_line.company_id.id),
            ]
        )
        return rules.filtered(lambda rule: rule._is_applicable_for(st_line, partner))

    def _apply_rules(self, st_line, partner):
        routing_rules = self._eng_cnab_get_routing_rules(st_line, partner)
        if routing_rules:
            # Exclusive routing: a collection credit is matched by the CNAB
            # rules only. When its group does not close, no other rule is
            # tried, so that an unrelated open item of the same amount, such
            # as a manual receipt in the same account, is never consumed.
            cnab_rules = self & routing_rules
            if (
                cnab_rules
                and st_line._eng_cnab_evaluate_rules(cnab_rules)["status"]
                == "ambiguous"
            ):
                # The rules close distinct exact groups, or other open lines
                # compete for the exact group under one of them: no rule may
                # win by sequence
                return {}
            return super(AccountReconcileModel, cnab_rules)._apply_rules(
                st_line, partner
            )
        return super()._apply_rules(st_line, partner)

    # Matching

    def _get_invoice_matching_rules_map(self):
        if self.eng_cnab_clearing_match:
            # Only the CNAB group, whatever other modules add to the map
            return {10: [self._get_invoice_matching_amls_candidates]}
        return super()._get_invoice_matching_rules_map()

    def _get_invoice_matching_amls_candidates(self, st_line, partner):
        if not self.eng_cnab_clearing_match:
            return super()._get_invoice_matching_amls_candidates(st_line, partner)
        if not st_line._eng_cnab_in_clearing_flow():
            # Out of the clearing flow (another journal, or before the
            # cutover date): no CNAB group, the next rules are tried
            return None
        evaluation = self._eng_cnab_evaluate(st_line)
        if evaluation["status"] != "match":
            return None
        return {"amls": evaluation["lines"], "allow_auto_reconcile": True}

    def _get_invoice_matching_amls_result(self, st_line, partner, candidate_vals):
        if not self.eng_cnab_clearing_match:
            return super()._get_invoice_matching_amls_result(
                st_line, partner, candidate_vals
            )
        # The candidates already are an exact group: no early payment
        # discount, no tolerance, no write-off and no single line picked out
        # of the group
        return {
            "amls": candidate_vals["amls"],
            "auto_reconcile": bool(
                candidate_vals["allow_auto_reconcile"] and self.auto_reconcile
            ),
        }

    def _eng_cnab_evaluate(self, st_line):
        """Evaluate the CNAB clearing group of the statement line.

        The status is, in this order of precedence:

        - "excluded": the statement line was unreconciled by hand, and stays
          out of the CNAB matching until its Retry button;
        - "invalid_config": the CNAB clearing configuration of the journal is
          invalid now, so its clearing account cannot be trusted;
        - "partial": the statement line is not fully open, either reconciled,
          with a counterpart already applied or with a residual amount that is
          not its whole amount (the residual has the sign of the suspense
          line: -amount on an open line);
        - "ambiguous": another fully open statement line of the journal, on
          the same date, meets the conditions of this rule;
        - "awaiting": no open clearing line is due on the date of the line;
        - "difference": the whole group does not sum the amount of the line;
        - "match": the whole group sums exactly the amount of the line.
        """
        self.ensure_one()
        currency = st_line.foreign_currency_id or st_line.currency_id
        amount = (
            st_line.amount_currency if st_line.foreign_currency_id else st_line.amount
        )
        clearing_account = st_line._eng_cnab_get_clearing_account()
        evaluation = {
            "rule": self,
            "currency": currency,
            "amount": amount,
            "account": clearing_account,
            "lines": self.env["account.move.line"],
            "total": 0.0,
            "competitors": self.env["account.bank.statement.line"],
            # Whether the whole group sums exactly the amount of the line,
            # with or without competitors
            "exact": False,
            # Set by the evaluation of all the routing rules of the line
            "ambiguous_rules": self.browse(),
            "configuration_error": "",
        }
        if st_line.eng_cnab_excluded:
            evaluation["status"] = "excluded"
            return evaluation
        configuration_error = st_line.journal_id._eng_cnab_get_configuration_error()
        if configuration_error:
            evaluation.update(
                {"status": "invalid_config", "configuration_error": configuration_error}
            )
            return evaluation
        if not st_line._eng_cnab_is_fully_open():
            evaluation["status"] = "partial"
            return evaluation
        lines = self._eng_cnab_get_clearing_lines(st_line, clearing_account, currency)
        evaluation.update(
            {
                "lines": lines,
                "total": sum(lines.mapped("amount_residual_currency")),
                "competitors": self._eng_cnab_get_competitors(st_line),
            }
        )
        evaluation["exact"] = bool(lines) and not currency.compare_amounts(
            evaluation["total"], amount
        )
        if evaluation["competitors"]:
            evaluation["status"] = "ambiguous"
        elif not lines:
            evaluation["status"] = "awaiting"
        elif currency.compare_amounts(evaluation["total"], amount):
            evaluation["status"] = "difference"
        else:
            evaluation["status"] = "match"
        return evaluation

    def _eng_cnab_get_clearing_lines(self, st_line, clearing_account, currency):
        """Whole group of open CNAB clearing lines of the statement line.

        No search for a subset: the group is every posted clearing line of
        the clearing account of the journal, open, of the same company and
        currency, due on the date of the statement line and of a receiving
        bank class compatible with the filter of the rule. A line without
        class only belongs to the group of the "any" filter.
        """
        self.ensure_one()
        domain = [
            ("eng_cnab_clearing", "=", True),
            ("parent_state", "=", "posted"),
            ("reconciled", "=", False),
            ("amount_residual", ">", 0.0),
            ("company_id", "=", st_line.company_id.id),
            ("currency_id", "=", currency.id),
            ("account_id", "=", clearing_account.id),
            ("date_maturity", "=", st_line.date),
        ]
        if self.eng_receiving_bank_filter != "any":
            domain.append(
                ("eng_cnab_receiving_bank_class", "=", self.eng_receiving_bank_filter)
            )
        return self.env["account.move.line"].search(domain, order="id")

    def _eng_cnab_get_competitors(self, st_line):
        """Other statement lines that this rule would match with the same
        group: same journal, same date, same sign, fully open as the line
        itself must be, and the conditions of the rule. Nothing tells which
        one the group belongs to."""
        self.ensure_one()
        same_day_lines = self.env["account.bank.statement.line"].search(
            [
                # _origin: the reconciliation widget evaluates new records too
                ("id", "!=", st_line._origin.id),
                ("journal_id", "=", st_line.journal_id.id),
                ("date", "=", st_line.date),
                ("state", "=", "posted"),
                ("is_reconciled", "=", False),
                ("amount", ">", 0.0) if st_line.amount > 0 else ("amount", "<=", 0.0),
            ]
        )
        # A line reconciled in part is out of the matching, so it never
        # competes for the group
        return same_day_lines.filtered(
            lambda other_line: other_line._eng_cnab_is_fully_open()
            and self._is_applicable_for(other_line, other_line._retrieve_partner())
        )
