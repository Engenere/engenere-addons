## Contas Contábeis

Antes de usar o módulo, configure as contas contábeis para cada tipo de componente.
Isso pode ser feito de duas formas:

### Configuração global (por tipo de componente)

1. Acesse **Financeiro > Consórcios > Tipos de Componente**
2. Para cada tipo, defina a **Conta Padrão** que será usada quando não houver
   configuração específica na cota

### Configuração por cota

1. Abra a cota do consórcio
2. Na aba **Account Configuration**, mapeie cada tipo de componente para a conta
   contábil desejada
3. Essa configuração tem prioridade sobre a conta padrão do tipo de componente

### Contas sugeridas

| Componente | Tipo de Conta | Exemplo |
|---|---|---|
| Fundo Comum | Passivo Circulante | 2.1.x - Consórcios a Pagar |
| Taxa de Administração | Despesa | 3.x - Despesas Administrativas |
| Fundo de Reserva | Ativo Circulante | 1.1.x - Fundo de Reserva (restituível) |
| Seguro de Vida | Despesa | 3.x - Seguros |
| Multa / Juros | Despesa Financeira | 3.x - Despesas Financeiras |

## Permissões

O módulo cria dois grupos de acesso na categoria **Consortium**:

- **User**: pode visualizar e criar cotas, parcelas e gerar faturas
- **Manager**: acesso completo, incluindo reajustes e exclusão de registros

Usuários com o grupo **Administration / Settings** recebem automaticamente o grupo
**Manager**.
