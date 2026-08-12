1. Open the user form (Settings > Users & Companies > Users).
2. In the access rights tab, section **Installment Renegotiation**, pick
   **Renegotiate Vendor Bill Installments**.
3. The user also needs the Accounting **Billing** access level (or
   higher). The group grants nothing without it.

Users that renegotiate installments also need the **Payment Orders** group
(`account_payment_order`), whatever the payment mode: with
`l10n_br_account_payment_order` installed, the renegotiation write-off
always reads the payment lines in the acting user's environment.
