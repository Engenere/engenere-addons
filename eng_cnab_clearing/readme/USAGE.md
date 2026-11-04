Import the CNAB return file as usual, from the journal (**Import batch
file**). For the liquidations credited on or after the cutover date:

- the invoice is paid on the occurrence date of the return;
- the clearing line waits for the bank statement line of its credit date,
  with the receiving bank class on it;
- the return log shows the journal and the hash of the file, and each event
  shows its position in the file, the receiving bank and the clearing entry.

When the file is refused, nothing is imported: no log, no attachment, no
event, no entry and no CNAB state change. Ask the bank for a corrected file,
or review the lock date with the accounting team, and import it again.

With **Automatic Reconcile payment returns** disabled on the journal, the
clearing entries stay in draft; posting them later goes through the same
lock date protection.
