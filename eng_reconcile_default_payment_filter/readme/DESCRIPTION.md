Este módulo força o filtro **"Outstanding Payments/Receipts"** (Pagamentos/Recebimentos
Pendentes) a ficar sempre ativo por padrão na tela de reconciliação bancária do Odoo.

## Problema

O módulo `account_reconcile_oca_add_default_filters` ativa os filtros padrão na
reconciliação bancária apenas quando a linha do extrato possui um parceiro definido.
Quando não há parceiro, os filtros ficam desativados e o usuário precisa ativá-los
manualmente.

## Solução

Este módulo sobrescreve o contexto do campo de reconciliação para que o filtro de
pagamentos/recebimentos pendentes (`payment_asset_current`) seja sempre ativado,
independente de haver parceiro na linha do extrato.

Os filtros de contas a pagar (`trade_payable`) e a receber (`trade_receivable`)
continuam condicionados à presença do parceiro, conforme o comportamento original.
