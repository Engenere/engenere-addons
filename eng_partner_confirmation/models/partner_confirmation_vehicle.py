# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PartnerConfirmationVehicle(models.Model):
    _name = "partner.confirmation.vehicle"
    _description = "Partner Confirmation Vehicle"

    name = fields.Char(required=True)
