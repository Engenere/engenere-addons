# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models


class HelpdeskTicketSolutionPlan(models.Model):
    _name = "helpdesk.ticket.solution.plan"
    _description = "Helpdesk Ticket Solution Plan"

    ticket_id = fields.Many2one(
        comodel_name="helpdesk.ticket",
        string="Ticket",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="ticket_id.company_id",
        store=True,
        index=True,
    )
    content = fields.Html(
        string="Solution Plan",
        sanitize_style=True,
        default=lambda self: self._default_content(),
    )

    _sql_constraints = [
        (
            "ticket_uniq",
            "unique(ticket_id)",
            "A ticket can only have one solution plan.",
        ),
    ]

    @api.model
    def _default_content(self):
        """Return an empty plan skeleton with the canonical sections."""
        sections = [
            _("Origin / root cause"),
            _("Real problem"),
            _("What will be done"),
            _("How to verify"),
        ]
        return "".join(f"<h3>{section}</h3><p><br/></p>" for section in sections)
