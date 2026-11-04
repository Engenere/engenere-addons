This module reconciles the bank statement with the CNAB clearing lines of
`eng_cnab_clearing`, so that each collection credit of the bank statement
settles exactly the liquidations the bank credited on that day.

A reconciliation model with **CNAB Clearing Matching** matches a statement
line with the **whole group** of open CNAB clearing lines that:

- are in the clearing account of the journal of the statement line, of the
  same company and currency, and posted;
- are due (`date_maturity`) on the date of the statement line, which is the
  credit date of the liquidations;
- belong to the receiving bank class of the rule: any bank, the bank of the
  journal only, or the other banks only, for the banks that split the
  collection credit of a day by receiving bank. For Ailos, the bank of the
  journal is its own credit union: a title paid at another credit union
  counts as another bank.

The statement line is reconciled only when the whole group sums exactly its
amount. There is no search for a subset of the group, no tolerance and no
write-off. Only a statement line that is still fully open is matched.

The routing is exclusive: a statement line that meets the conditions of a
CNAB rule is matched by the CNAB rules only. When its group does not close,
no other reconciliation model is tried, so that a manual receipt of the same
amount in the same account is never consumed by chance. The routing holds
even when the CNAB configuration of the journal has become invalid since it
was saved, for instance when the account of its CNAB receipt method was
cleared: the line then gets no proposal at all. When the CNAB rules that
route the same line close distinct groups of its exact amount, none of them is
applied. Neither is a group of its exact amount that another fully open
collection credit of the same day also meets under one of these rules: no rule
wins the line by its sequence.

The matching runs:

- when the statement line is created, through the automatic reconciliation
  of `account_reconcile_oca`;
- after each CNAB return import, by a trigger of a scheduled action that
  runs after the import, in a transaction of its own: the import never
  reconciles anything by itself;
- every 30 minutes, by the same scheduled action, for every pending line;
- from the **Retry CNAB Matching** button of the statement line.

Each collection credit shows the reason it is still open: awaiting the CNAB
return, amount difference (with the difference), partially reconciled,
ambiguous (another fully open collection credit of the same day meets the
same rule, or two rules close distinct groups), invalid configuration of the
journal, unreconciled by hand, or error; or that it is reconciled. A
reconciliation made by hand on the reconciliation screen clears the reason.

A statement line unreconciled by hand leaves the CNAB matching: neither the
scheduled action nor the automatic reconciliation match it again, until its
**Retry CNAB Matching** button.

Concurrent attempts lock the statement line and then its candidate clearing
lines in id order. A concurrency error is never caught: the whole
transaction is repeated, by the RPC layer for the button or by the next run
of the scheduled action. The scheduled action runs each line in a savepoint
of its own, so that a business error of one line is shown as its reason
while the other lines go on.

The module also refuses a bank statement file in which a transaction
already imported comes back with the same identifier (the FITID of an OFX
file) but another date or amount. The same transaction imported again with
the same content is still skipped, as before. In a journal with the CNAB
clearing flow, it also refuses a file with lines dated before the bank cutover
date: until that date the CNAB returns post through the bank account, so these
lines would enter it a second time.
