from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    stage_state = fields.Selection(
        related="stage_id.state",
        string="Stage state",
    )

    @api.model
    def _is_draft_state(self, partner, new_stage_id=None):
        """Return True if the (future) stage is 'draft'."""
        if new_stage_id:
            new_stage = self.env["res.partner.stage"].browse(new_stage_id)
            return new_stage.state == "draft"
        return partner.stage_state == "draft"

    def write(self, vals):
        # Permit mudar apenas stage_id para/desde draft
        other_fields = set(vals) - {"stage_id"}
        for partner in self:
            will_be_draft = self._is_draft_state(partner, vals.get("stage_id"))
            if other_fields and not will_be_draft:
                raise UserError(
                    _("You can only edit a partner whose stage is in " "state 'draft'.")
                )
        return super().write(vals)
