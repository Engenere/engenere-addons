Import the CNAB return files and the bank statement files as usual, in any
order:

- when the CNAB return comes first, the collection credit of the statement
  is reconciled as soon as its line is created;
- when the bank statement comes first, its collection credit waits for the
  return, and the scheduled action reconciles it after the import of the
  return.

On the reconciliation screen, a pending collection credit shows its reason
and the **Retry CNAB Matching** button; the list of statement lines shows
the status, and the filter **CNAB Pending** lists every pending one. A
difference or an ambiguity is never adjusted automatically: review the line
on the reconciliation screen, where it can still be reconciled by hand. A
line you unreconcile stays with you until you press **Retry CNAB Matching**.

A bank statement file is refused when one of its transactions was already
imported with the same identifier but another date or amount: check the file
with the bank.
