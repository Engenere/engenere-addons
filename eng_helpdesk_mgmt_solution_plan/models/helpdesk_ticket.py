# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models

SOLUTION_PLAN_GROUP = "eng_helpdesk_mgmt_solution_plan.group_helpdesk_solution_plan"


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    # Real access control is enforced by the ACL on
    # helpdesk.ticket.solution.plan (only the group can read it). The ``groups``
    # attribute here just keeps the field/page out of the view (and out of reads)
    # for non-members, so loading a ticket never triggers an AccessError.
    solution_plan_ids = fields.One2many(
        comodel_name="helpdesk.ticket.solution.plan",
        inverse_name="ticket_id",
        string="Solution Plan",
        groups=SOLUTION_PLAN_GROUP,
        copy=False,
    )
