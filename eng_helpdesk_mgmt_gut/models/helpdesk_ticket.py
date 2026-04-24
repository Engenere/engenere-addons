from odoo import api, fields, models

GUT_GRAVITY_SELECTION = [
    ("1", "1 - No gravity"),
    ("2", "2 - Low gravity"),
    ("3", "3 - Grave"),
    ("4", "4 - Very grave"),
    ("5", "5 - Extremely grave"),
]

GUT_URGENCY_SELECTION = [
    ("1", "1 - Can wait"),
    ("2", "2 - Low urgency"),
    ("3", "3 - Urgent, needs attention"),
    ("4", "4 - Very urgent"),
    ("5", "5 - Immediate action"),
]

GUT_TENDENCY_SELECTION = [
    ("1", "1 - Will not change"),
    ("2", "2 - Will worsen long term"),
    ("3", "3 - Will worsen medium term"),
    ("4", "4 - Will worsen short term"),
    ("5", "5 - Will worsen rapidly"),
]

GUT_BAND_SELECTION = [
    ("unclassified", "Unclassified"),
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    gut_gravity = fields.Selection(
        selection=GUT_GRAVITY_SELECTION,
        string="Gravity (G)",
        tracking=True,
        help="How serious is the problem: impact if nothing is done.",
    )
    gut_urgency = fields.Selection(
        selection=GUT_URGENCY_SELECTION,
        string="Urgency (U)",
        tracking=True,
        help="How much time is available before the problem must be solved.",
    )
    gut_tendency = fields.Selection(
        selection=GUT_TENDENCY_SELECTION,
        string="Tendency (T)",
        tracking=True,
        help="How the problem evolves if nothing is done.",
    )
    gut_score = fields.Integer(
        string="GUT Score",
        compute="_compute_gut_score",
        store=True,
        help="Product of Gravity × Urgency × Tendency (1-125). "
        "Zero when any of the three is not set.",
    )
    gut_band = fields.Selection(
        selection=GUT_BAND_SELECTION,
        string="GUT Band",
        compute="_compute_gut_band",
        store=True,
        help="Classification band derived from GUT Score: "
        "Unclassified (0), Low (1-15), Medium (16-45), "
        "High (46-99), Critical (100-125).",
    )

    @api.depends("gut_gravity", "gut_urgency", "gut_tendency")
    def _compute_gut_score(self):
        for ticket in self:
            g = ticket.gut_gravity
            u = ticket.gut_urgency
            t = ticket.gut_tendency
            if g and u and t:
                ticket.gut_score = int(g) * int(u) * int(t)
            else:
                ticket.gut_score = 0

    @api.depends("gut_score")
    def _compute_gut_band(self):
        for ticket in self:
            score = ticket.gut_score
            if score <= 0:
                ticket.gut_band = "unclassified"
            elif score <= 15:
                ticket.gut_band = "low"
            elif score <= 45:
                ticket.gut_band = "medium"
            elif score <= 99:
                ticket.gut_band = "high"
            else:
                ticket.gut_band = "critical"
