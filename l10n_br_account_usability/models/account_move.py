# Copyright (C) 2022-Today - Engenere (<https://engenere.one>).
# @author Antônio S. Pereira Neto <neto@engenere.one>

from odoo import models, fields


class AccountMove(models.Model):
    _inherit = "account.move"

    total_faturado = fields.Monetary(
        string="Faturamento",
        help="Exibe o total faturado bruto, sem descontar as retenções",
        compute="_compute_total_faturado",
        store=True,  # Adicione store=True para armazenar o resultado no banco de dados
    )

    total_faturado_global = fields.Monetary(
        string="Total Faturado Global",
        help="Total do faturamento de todos os registros",
        compute="_compute_total_faturado_global",
        store=True,  # Adicione store=True para armazenar o resultado no banco de dados
    )

    def _compute_total_faturado(self):
        for move in self:
            # consideramos o tatal faturado o amount_total nativo
            # que é a soma dos vencimentos, porem sem descontar o valor retido.
            # por isso que aqui o valor retido é somado novamente.
            move.total_faturado = move.amount_total + move.amount_tax_withholding

    def _compute_total_faturado_global(self):
        total_global = sum(self.mapped("total_faturado"))
        self.total_faturado_global = total_global
