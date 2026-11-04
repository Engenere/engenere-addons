1. Create the clearing account of the bank: a current asset account of the
   company of the journal, which allows reconciliation and is not the bank
   account of the journal.
2. Open the bank journal (Invoicing > Configuration > Journals), tab
   **Import related infos**, and:
   - enable **CNAB Clearing Flow**;
   - set the **Bank Cutover Date**: liquidations credited on or after it use
     the clearing flow, the older ones keep the legacy flow;
   - pick the **CNAB Receipt Method**, an inbound payment method of the
     journal whose **Outstanding Receipts** account is the clearing account.
     The account must be set on the method itself: the default account of the
     company is not used as a fallback.
3. Point the other inbound payment methods of the journal to the same
   clearing account, so that manual receipts are reconciled by the bank
   statement as well.

The clearing flow supports Banco do Brasil CNAB 400 and Ailos CNAB 240
return files only. Any other layout needs its own tests first.
