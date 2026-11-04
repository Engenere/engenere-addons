1. Configure the CNAB clearing flow of the bank journal (module
   `eng_cnab_clearing`). The journal must reconcile its statement lines in
   the **Edit Move** mode, and its suspense account cannot be the clearing
   account.
2. Create one reconciliation model (Invoicing > Configuration >
   Reconciliation Models) for each collection credit of the bank statement:
   - type **Rule to match invoices/bills**, with **Auto-validate**;
   - the bank journal, the amount type **Received** and a label condition
     that only the collection credit meets;
   - **CNAB Clearing Matching** enabled;
   - the **Receiving Bank** filter: **Any Bank** when the bank credits the
     collection of a day at once, or **Own Bank** and **Other Banks** in two
     rules when the statement splits it by receiving bank.
3. Give the CNAB rules a sequence lower than the other rules.
4. The tariffs and the movements of an investment account can be posted by
   rules of the type **Rule to suggest counterpart entry**, with
   **Auto-validate**.

The scheduled action **CNAB Clearing: Reconcile Pending Bank Statement
Lines** runs every 30 minutes; its interval can be changed.
