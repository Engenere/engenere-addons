## Fluxo Geral

```
1. CRIAR COTA → 2. CONFIGURAR CONTAS → 3. REGISTRAR PARCELAS → 4. GERAR FATURAS → 5. REAJUSTAR
```

## 1. Criar a Cota do Consórcio

Acesse **Financeiro > Consórcios > Cotas** e crie um registro com:

- **Administradora**: parceiro cadastrado (ex: "Portobens Mercedes-Benz")
- **Grupo / Cota**: identificação do consórcio (ex: 18102 / 214)
- **Valor do crédito**: valor original da carta de crédito
- **Total de parcelas**: prazo do consórcio
- **Taxas**: administração, fundo de reserva, seguro de vida (percentuais totais)
- **Dados de contemplação**: data, tipo (lance ou sorteio)
- **Tipo de reajuste**: por valor do bem, por índice ou manual

### Status da cota

A cota passa pelos estados: **Rascunho → Ativo → Contemplado → Concluído**

## 2. Configurar Contas Contábeis

Na aba **Account Configuration** da cota, mapeie cada tipo de componente para a conta
contábil correspondente. Essa configuração é feita uma vez por cota e será usada
automaticamente ao criar parcelas.

## 3. Registrar Parcelas

Na aba **Installments** da cota, registre cada parcela com sua composição. Exemplo:

| Componente | Valor |
|---|---|
| Fundo Comum | R$ 2.800,00 |
| Taxa de Administração | R$ 400,00 |
| Fundo de Reserva | R$ 150,00 |
| Seguro | R$ 19,47 |
| **Total** | **R$ 3.369,47** |

O total é calculado automaticamente pela soma dos componentes. A conta contábil de cada
linha vem da configuração da cota (aba Account Configuration).

Para **lances** (pagamentos antecipados de maior valor), marque o checkbox **"Is Lance"**
na parcela.

## 4. Gerar Faturas

1. Selecione uma ou mais parcelas na lista
2. Use a ação **"Generate Invoices"** (menu de contexto / Action)
3. O wizard cria uma **fatura de fornecedor em rascunho** para a administradora
4. Cada componente da parcela vira uma **linha da fatura** com a conta contábil correta
5. A parcela fica vinculada à fatura (smart button para navegação)
6. O status da parcela muda para **"Open"**

Revise a fatura, confirme e pague normalmente pelo fluxo do Odoo. Após o pagamento,
marque a parcela como **"Paid"**.

## 5. Reajustar

Quando a administradora comunica um reajuste do valor do bem ou da carta de crédito:

1. Abra a cota e clique no botão **"Apply Readjustment"**
2. Informe o **novo valor do crédito** (ou o percentual de reajuste — os campos são
   interligados)
3. Opcionalmente marque **"Recalculate Future"** para recalcular o fundo comum das
   parcelas futuras proporcionalmente
4. O wizard registra o histórico completo (valor anterior → novo, percentual, data,
   quem aplicou)

> **Nota:** O módulo não tenta prever reajustes futuros. Cada reajuste é aplicado
> manualmente quando comunicado pela administradora. As parcelas futuras podem ser
> ajustadas individualmente conforme os boletos chegam.

## Dashboard

Na listagem de cotas, cada registro mostra:

- Parcelas pagas / restantes
- Total pago / Saldo devedor
- Próximo vencimento
- Barra de progresso
