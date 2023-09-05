# Copyright (C) 2022-Today - Engenere (<https://engenere.one>).
# @author Antônio S. Pereira Neto <neto@engenere.one>

from odoo import models, fields


class AccountMove(models.Model):
    """Extend Account Move"""

    _inherit = "account.move"

    total_faturado = fields.Float(
        string="Faturamento",
        help="Exibe o total faturado bruto, sem descontar as retenções",
        compute="_compute_total_faturado",
    )

    def _compute_total_faturado(self):
        for move in self:
            # consideramos o tatal faturado o amount_total nativo
            # que é a soma dos vencimentos, porem sem descontar o valor retido.
            # por isso que aqui o valor retido é somado novamente.
            move.total_faturado = move.amount_total + move.amount_tax_withholding

