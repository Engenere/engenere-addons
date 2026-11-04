This module changes how a CNAB return file settles the boletos of a bank
journal, so that the bank statement becomes the only source of the bank
account.

For a journal with the **CNAB Clearing Flow** enabled, each liquidation
credited on or after the **Bank Cutover Date** is settled by one journal
entry that:

- is dated on the **occurrence date** (the day the customer paid), not on the
  credit date nor on the import date;
- debits a single **clearing account** line with the received amount, due on
  the **credit date** and tagged with the class of the receiving bank (own
  bank or other banks), where the bank statement line of that credit date
  will reconcile it;
- keeps the installment line (reconciled with the invoice as before) and the
  interest, discount and rebate lines in their result accounts;
- has no line in the bank account of the journal and no tariff line: the
  tariff stays on the CNAB return event, and the bank statement is the only
  source of bank tariffs.

The whole return file is validated before any record is processed. The file
is refused, with the file name, the sequence number of each faulty record
(or, for a record without one, its position among the records read from the
file) and the reason, when a detail record has no valid occurrence date (no
fallback to the credit date or to today), when a liquidation has no valid
credit date, or when an Ailos liquidation does not state the receiving bank.

The module also:

- links every event, entry and clearing line to the position of its record
  in the file;
- refuses a file already imported in the same journal (SHA-256 of the file,
  unique per company and journal);
- refuses to post a clearing entry when a lock date would replace its
  occurrence date, also when a draft entry is posted later, and cancels the
  posting when any module changes that date while posting.

Liquidations credited before the cutover date, and journals without the
clearing flow, keep the original import of `l10n_br_account_payment_brcobranca`.
