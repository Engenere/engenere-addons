# Copyright 2023 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, api, models


class Partner(models.Model):
    """
    Estende o modelo de parceiro para desativar a validação de CNPJ/IE
    """
    _inherit = "res.partner"

    @api.constrains("cnpj_cpf", "inscr_est")
    def _check_cnpj_inscr_est(self):
        """
        Desativa o método original de validação de CNPJ/IE
        """
        return
