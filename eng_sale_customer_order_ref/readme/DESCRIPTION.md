Este módulo faz o número do pedido do cliente ser digitado uma única vez no pedido de
venda.

O campo *Referência do Cliente* (`client_order_ref`) passa a ficar no cabeçalho do
pedido, junto do cliente, e as linhas herdam o valor como pedido do parceiro
(`partner_order`), que sai na NF-e como `xPed`. A linha ainda aceita um número próprio,
que vale até a referência do pedido mudar. Um pedido duplicado nasce sem o número.
