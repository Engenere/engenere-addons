# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools.misc import format_date, formatLang

CNAB_RECONCILE_STATUSES = [
    ("awaiting", "Awaiting CNAB Return"),
    ("difference", "Amount Difference"),
    ("partial", "Partially Reconciled"),
    ("ambiguous", "Ambiguous"),
    ("invalid_config", "Invalid Configuration"),
    ("excluded", "Unreconciled by Hand"),
    ("error", "Error"),
    ("reconciled", "Reconciled"),
]


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    eng_cnab_reconcile_status = fields.Selection(
        selection=CNAB_RECONCILE_STATUSES,
        string="CNAB Matching",
        readonly=True,
        copy=False,
        help="Outcome of the last CNAB clearing matching of this collection "
        "credit. Empty when no CNAB clearing rule routes the line.",
    )
    eng_cnab_reconcile_message = fields.Text(
        string="CNAB Matching Reason",
        readonly=True,
        copy=False,
    )
    eng_cnab_reconcile_difference = fields.Monetary(
        string="CNAB Matching Difference",
        readonly=True,
        copy=False,
        help="Amount of the statement line minus the sum of its group of CNAB "
        "clearing lines, when they differ.",
    )
    eng_cnab_excluded = fields.Boolean(
        string="Out of the CNAB Matching",
        readonly=True,
        copy=False,
        help="Set when the line is unreconciled by hand: neither the "
        "scheduled action nor the automatic reconciliation match it with "
        "CNAB clearing lines again, until the Retry CNAB Matching button.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        st_lines = super().create(vals_list)
        # The automatic reconciliation of account_reconcile_oca already ran,
        # through the CNAB rules only for the collection credits: record its
        # outcome on each of them
        st_lines._eng_cnab_try_reconcile()
        return st_lines

    def _eng_cnab_in_clearing_flow(self):
        """Whether the CNAB clearing flow covers this line: its journal has
        the flow enabled and the line is dated on or after the bank cutover
        date of the journal.

        Such a line is routed to the CNAB rules only, even when the
        configuration of its journal has become invalid since.
        """
        self.ensure_one()
        journal = self.journal_id
        return bool(
            journal.eng_cnab_clearing_enabled
            and journal.eng_bank_cutover_date
            and self.date
            and self.date >= journal.eng_bank_cutover_date
        )

    def _eng_cnab_get_clearing_account(self):
        """Clearing account the CNAB matching reconciles this line with.

        Empty out of the clearing flow: the clearing lines only exist from
        the cutover date on. In the flow, the matching only uses it once the
        configuration of the journal is valid.
        """
        self.ensure_one()
        if not self._eng_cnab_in_clearing_flow():
            return self.env["account.account"]
        return self.journal_id.eng_cnab_receipt_method_line_id.payment_account_id

    def _eng_cnab_is_fully_open(self):
        """Whether nothing of the line is reconciled yet: not reconciled,
        with no counterpart applied and with a residual amount that is its
        whole amount (the residual has the sign of the suspense line:
        -amount on an open line)."""
        self.ensure_one()
        currency = self.foreign_currency_id or self.currency_id
        amount = self.amount_currency if self.foreign_currency_id else self.amount
        _liquidity_lines, _suspense_lines, other_lines = self._seek_for_lines()
        return not (
            self.is_reconciled
            or other_lines
            or currency.compare_amounts(self.amount_residual, -amount)
        )

    def _eng_cnab_get_routing_rules(self):
        """CNAB clearing rules that route this statement line, by sequence."""
        self.ensure_one()
        rule_model = self.env["account.reconcile.model"]
        if not self._eng_cnab_in_clearing_flow():
            return rule_model
        return rule_model._eng_cnab_get_routing_rules(self, self._retrieve_partner())

    def action_eng_cnab_retry(self):
        # Retry also hands a line unreconciled by hand back to the CNAB
        # matching
        self.filtered("eng_cnab_excluded").with_context(
            skip_account_move_synchronization=True
        ).write({"eng_cnab_excluded": False})
        self._eng_cnab_try_reconcile()
        return True

    def reconcile_bank_line(self):
        result = super().reconcile_bank_line()
        # Reconciled on the reconciliation screen: the reason of the last
        # CNAB matching no longer applies
        self._eng_cnab_write_outcome()
        return result

    def action_undo_reconciliation(self):
        result = super().action_undo_reconciliation()
        # Unreconciled by hand, on the reconciliation screen (its Unreconcile
        # button ends here in the "Edit Move" mode) or with the Revert
        # reconciliation button of the list of statement lines: the CNAB
        # matching must not reconcile the line again by itself, neither from
        # the scheduled action nor on the reconciliation screen, until the
        # Retry CNAB Matching button
        self.filtered(
            lambda st_line: st_line._eng_cnab_get_routing_rules()
        ).with_context(skip_account_move_synchronization=True).write(
            {"eng_cnab_excluded": True}
        )
        self._eng_cnab_try_reconcile()
        return result

    def _eng_cnab_try_reconcile(self):
        """Single service of the CNAB clearing matching of statement lines.

        Runs after the creation of the lines, after an unreconciliation by
        hand, from the Retry button and from the cron (which every CNAB
        import triggers). Before reconciling, it locks the statement line and
        then its candidate clearing lines in id order, so that two attempts
        on the same group never deadlock, and invalidates the cache after the
        locks.

        There is no savepoint and no generic except here: a concurrency
        error (serialization failure, deadlock, lock not available) raises
        and rolls back the whole transaction, which the RPC layer (retrying)
        or the next run of the cron repeats with a new snapshot. Only
        business outcomes are written on the line, as its reason. The cron
        alone runs each line in a savepoint, to record a business error of
        one line without stopping the others.
        """
        for st_line in self:
            st_line = st_line.with_company(st_line.company_id)
            routing_rules = st_line._eng_cnab_get_routing_rules()
            if not routing_rules:
                # Not a collection credit (any more): no reason to show
                st_line._eng_cnab_write_outcome()
                continue
            st_line._eng_cnab_lock_statement_line()
            if st_line.is_reconciled:
                st_line._eng_cnab_write_outcome("reconciled", _("Reconciled."))
                continue
            evaluation = st_line._eng_cnab_evaluate_rules(routing_rules)
            if evaluation["status"] == "match":
                st_line._eng_cnab_lock_clearing_lines(evaluation["lines"])
                self.env.invalidate_all()
                st_line._eng_cnab_reconcile_group(evaluation["lines"])
                evaluation["status"] = "reconciled"
            st_line._eng_cnab_write_outcome(*st_line._eng_cnab_get_outcome(evaluation))

    def _eng_cnab_evaluate_rules(self, routing_rules):
        """Evaluation of the CNAB rules that route this line.

        Every rule is evaluated, and every group that sums exactly the
        amount of the line counts, even one that other open lines also
        compete for:
        - exact groups that are distinct: nothing tells which one is right,
          the result is "ambiguous", with those rules;
        - one exact group that other lines compete for under any of the
          rules: the result is that "ambiguous" evaluation, with its
          competitors, so that another rule never wins the group by
          sequence;
        - otherwise, the first "match", the one _apply_rules() picks, or,
          without one, the evaluation of the first rule.
        """
        self.ensure_one()
        evaluations = [rule._eng_cnab_evaluate(self) for rule in routing_rules]
        exact_evaluations = [
            evaluation for evaluation in evaluations if evaluation["exact"]
        ]
        if len({evaluation["lines"] for evaluation in exact_evaluations}) > 1:
            return dict(
                exact_evaluations[0],
                status="ambiguous",
                ambiguous_rules=routing_rules.browse(
                    [evaluation["rule"].id for evaluation in exact_evaluations]
                ),
            )
        contested_evaluations = [
            evaluation for evaluation in exact_evaluations if evaluation["competitors"]
        ]
        if contested_evaluations:
            return contested_evaluations[0]
        matches = [
            evaluation for evaluation in evaluations if evaluation["status"] == "match"
        ]
        return matches[0] if matches else evaluations[0]

    def _eng_cnab_lock_statement_line(self):
        self.env.cr.execute(
            "SELECT id FROM account_bank_statement_line WHERE id IN %s FOR UPDATE",
            [tuple(self.ids)],
        )

    @api.model
    def _eng_cnab_lock_clearing_lines(self, clearing_lines):
        self.env.cr.execute(
            "SELECT id FROM account_move_line WHERE id IN %s ORDER BY id FOR UPDATE",
            [tuple(clearing_lines.ids)],
        )

    def _eng_cnab_reconcile_group(self, clearing_lines):
        """Reconcile the statement line with the whole group, as the
        automatic reconciliation of account_reconcile_oca does when the line
        is created, in the "Edit Move" mode."""
        self.ensure_one()
        liquidity_lines, _suspense_lines, _other_lines = self._seek_for_lines()
        data = []
        for line in liquidity_lines:
            data += self._get_reconcile_line(line, "liquidity", move=True)[1]
        for line in clearing_lines:
            data += self._get_reconcile_line(
                line, "other", is_counterpart=True, move=True
            )[1]
        reconcile_data = self._recompute_suspense_line(data, 1, False)
        self._reconcile_bank_line_edit(
            self._prepare_reconcile_line_data(reconcile_data["data"])
        )
        # As reconcile_bank_line() does: a draft of the reconciliation screen
        # no longer applies
        self.reconcile_data = False

    def _eng_cnab_get_outcome(self, evaluation):
        """Status, reason and difference to write on the line."""
        self.ensure_one()
        status = evaluation["status"]
        currency = evaluation["currency"]
        rule_name = evaluation["rule"].display_name
        account_name = evaluation["account"].display_name
        line_date = format_date(self.env, self.date)
        count = len(evaluation["lines"])
        if status == "reconciled":
            message = _(
                "Reconciled with the whole group of CNAB clearing lines of "
                "%(account)s due on %(date)s: %(count)s line(s).",
                count=count,
                account=account_name,
                date=line_date,
            )
        elif status == "excluded":
            message = _(
                "Unreconciled by hand: the CNAB matching no longer reconciles "
                "this line by itself. Reconcile it on the reconciliation "
                "screen, or use Retry CNAB Matching to hand it back to the "
                "CNAB matching."
            )
        elif status == "invalid_config":
            message = _(
                "Invalid configuration: %(error)s Until it is fixed, no "
                "reconciliation model proposes anything for this collection "
                "credit.",
                error=evaluation["configuration_error"],
            )
        elif status == "partial":
            message = _(
                "Partially reconciled: the statement line already has a "
                "counterpart, or its residual amount is not its whole amount, so "
                "the CNAB matching left it out. Review it on the reconciliation "
                "screen."
            )
        elif status == "ambiguous" and evaluation["ambiguous_rules"]:
            message = _(
                "Ambiguous: the rules %(rules)s each match a different group of "
                "open CNAB clearing lines of %(account)s due on %(date)s that "
                "sums exactly the amount of the statement line, so none of them "
                "is reconciled automatically. Review them on the "
                "reconciliation screen.",
                rules=", ".join(evaluation["ambiguous_rules"].mapped("display_name")),
                account=account_name,
                date=line_date,
            )
        elif status == "ambiguous":
            competitors = evaluation["competitors"]
            message = _(
                "Ambiguous: %(others)s other open statement lines of the journal "
                "on %(date)s (%(lines)s) also meet the conditions of the rule "
                "%(rule)s, so its CNAB clearing lines are not assigned "
                "automatically. Review them on the reconciliation screen.",
                others=len(competitors),
                date=line_date,
                lines=", ".join(competitors.mapped("display_name")),
                rule=rule_name,
            )
        elif status == "awaiting":
            message = _(
                "Awaiting the CNAB return: no open CNAB clearing line of "
                "%(account)s due on %(date)s matches the rule %(rule)s yet.",
                account=account_name,
                date=line_date,
                rule=rule_name,
            )
        else:
            difference = currency.round(evaluation["amount"] - evaluation["total"])
            message = _(
                "Amount difference of %(difference)s: the statement line amount "
                "is %(amount)s, and the %(count)s open CNAB clearing lines of "
                "%(account)s due on %(date)s for the rule %(rule)s sum "
                "%(total)s. Nothing was reconciled: review it on the "
                "reconciliation screen.",
                difference=formatLang(self.env, difference, currency_obj=currency),
                amount=formatLang(
                    self.env, evaluation["amount"], currency_obj=currency
                ),
                count=count,
                account=account_name,
                date=line_date,
                rule=rule_name,
                total=formatLang(self.env, evaluation["total"], currency_obj=currency),
            )
            return status, message, difference
        return status, message, 0.0

    def _eng_cnab_write_outcome(self, status=False, message=False, difference=0.0):
        self.ensure_one()
        # The message tells the difference: comparing it is enough
        if (self.eng_cnab_reconcile_status, self.eng_cnab_reconcile_message) == (
            status,
            message,
        ):
            return
        self.with_context(skip_account_move_synchronization=True).write(
            {
                "eng_cnab_reconcile_status": status,
                "eng_cnab_reconcile_message": message,
                "eng_cnab_reconcile_difference": difference,
            }
        )

    @api.model
    def _eng_cron_cnab_reconcile(self):
        """Try again every pending statement line of the journals with the
        CNAB clearing flow, dated on or after their cutover date, except the
        lines unreconciled by hand.

        Recurring, and triggered after each import of a CNAB return, in a
        transaction of its own. Each line runs in a savepoint: a business
        error (UserError or ValidationError) rolls back that line only, is
        written on it as its reason and the next lines go on. Any other
        error, above all a concurrency one (serialization failure, deadlock,
        lock not available), is not caught: it fails the whole run, which
        rolls back, and the next run tries again with a new snapshot.
        """
        journals = self.env["account.journal"].search(
            [("eng_cnab_clearing_enabled", "=", True)]
        )
        journal_domain = expression.OR(
            [
                [
                    ("journal_id", "=", journal.id),
                    ("date", ">=", journal.eng_bank_cutover_date),
                ]
                for journal in journals
            ]
        )
        st_lines = self.search(
            expression.AND(
                [
                    journal_domain,
                    [
                        ("is_reconciled", "=", False),
                        ("state", "=", "posted"),
                        ("eng_cnab_excluded", "=", False),
                    ],
                ]
            ),
            order="internal_index",
        )
        for st_line in st_lines:
            # The reason stays on the line as text, for the users of the
            # company: not in the language of the user of the scheduled action
            st_line = st_line.with_context(
                lang=st_line.company_id.partner_id.lang or self.env.lang
            )
            try:
                with self.env.cr.savepoint():
                    st_line._eng_cnab_try_reconcile()
            except (UserError, ValidationError) as error:
                st_line._eng_cnab_write_error(error)

    def _eng_cnab_write_error(self, error):
        self._eng_cnab_write_outcome(
            "error",
            _(
                "Error: the CNAB matching of this line failed, and the "
                "scheduled action went on with the other lines. Fix "
                "the cause, then retry.\n%(error)s",
                error=str(error),
            ),
        )
