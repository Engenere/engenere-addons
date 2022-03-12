# Copyright 2022 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class AccountMove(models.Model):

    _inherit = "account.move"

    part_conf_one_id = fields.Many2one(
        comodel_name="account.invoice.partner.confirmation",
        string="Partner Confirmation",
        help="Informations about the partner confirmation.",
        readonly=True,
        compute="_compute_part_conf",
    )

    part_confirm_id = fields.One2many(
        comodel_name="account.invoice.partner.confirmation",
        inverse_name="invoice_id",
        readonly=True,
    )

    part_confirm_date = fields.Date(
        "Confirmation Date",
        compute="_compute_confirmation",
        store=True,
        tracking=True,
    )

    part_confirm_state = fields.Selection(
        string="Partner Confirmation State",
        readonly=True,
        related="part_confirm_id.state",
    )

    part_confirm_responsible_employee_ids = fields.Many2many(
        "hr.employee",
        string="Responsible Employees",
        readonly=True,
        related="part_confirm_id.responsible_employee_ids",
    )

    part_confirm_vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Delivery Vehicle",
        compute="_compute_confirmation",
        store=True,
    )

    @api.depends("part_confirm_id")
    def _compute_part_conf(self):
        if self.part_confirm_id:
            self.part_conf_one_id = self.part_confirm_id[0]
        else:
            self.part_conf_one_id = False

    @api.depends(
        "part_confirm_id",
        "part_confirm_id.confirmation_date",
        "part_confirm_id.vehicle_id",
    )
    def _compute_confirmation(self):
        for record in self:
            record.part_confirm_date = record.part_confirm_id.confirmation_date
            record.part_confirm_vehicle_id = record.part_confirm_id.vehicle_id

    def action_register_partner_confirmation(self):
        """Open the account.invoice.partner.confirmation.register wizard to confirm the delivery to the partner.
        :return: An action opening the account.invoice.partner.confirmation.register wizard.
        """
        return {
            "name": _("Register Partner Confirmation"),
            "res_model": "account.invoice.partner.confirmation.register",
            "view_mode": "form",
            "context": {
                "active_model": "account.move",
                "active_ids": self.ids,
            },
            "target": "new",
            "type": "ir.actions.act_window",
        }

    def action_cancel_partner_confirmation(self):

        part_conf = self.part_confirm_id
        msg = self.get_delete_partner_conf_message(part_conf)

        part_conf.unlink()

        self.message_post(body=msg)

    def get_delete_partner_conf_message(self, part_conf):
        msg = _("The following Partner Confirmation has been cancelled: <br/>")

        date = part_conf.confirmation_date.strftime("%d/%m/%Y")
        msg = _("%s <li>Date: %s </li>") % (msg, date)

        state = part_conf.state
        msg = _("%s <li>State: %s </li>") % (msg, state)

        if part_conf.vehicle_id:
            vehicle = part_conf.vehicle_id.name
            msg = _("%s <li>Vehicle: %s </li>") % (msg, vehicle)

        if part_conf.receipt_person:
            receipt_person = part_conf.receipt_person
            msg = _("%s <li>Receipt Person: %s </li>") % (msg, receipt_person)

        if part_conf.responsible_employee_ids:
            employees = ", ".join([e.name for e in part_conf.responsible_employee_ids])
            msg = _("%s <li>Employees: %s </li>") % (msg, employees)

        if part_conf.observations:
            observations = part_conf.observations
            msg = _("%s <li>Observations: %s </li>") % (msg, observations)

        return msg
