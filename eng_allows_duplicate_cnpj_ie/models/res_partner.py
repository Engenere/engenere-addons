# Copyright 2023 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class Partner(models.Model):
    _inherit = "res.partner"

    @api.constrains("cnpj_cpf", "inscr_est")
    def _check_cnpj_inscr_est(self):
        """
        Desativa o método original de validação de CNPJ/IE
        Permitir CNPJs e IEs duplicados
        """
        return

    @api.constrains("vat", "l10n_br_ie_code")
    def _check_cnpj_l10n_br_ie_code(self):
        """
        Mesma desativação para a constraint que substituiu a de cima no
        l10n_br_base: sem este override o módulo deixou de ter efeito, e
        cadastros com CNPJ repetido voltaram a ser recusados.
        """
        return
