Unified payment renegotiation on posted invoices, on top of the upstream
`l10n_br_account_renegotiation` wizard.

**Dedicated security group.** The upstream module restricts its
"Renegotiate Installments" button to Invoicing Managers. This module adds
the **Renegotiate Vendor Bill Installments** group: Billing users holding
it can renegotiate installments of vendor documents
(`in_invoice`/`in_receipt`) only. Customer documents still require
Invoicing Manager, and the group grants nothing on its own (Billing
rights are also required).

**Invoice payment mode replacement.** The wizard gains a "New Invoice
Payment Mode" field: filling it replaces the mode on the invoice header
and on every new installment, in a single consistent operation (CNAB
write-off with the old configuration, registration and boleto with the
new one). This absorbs the retired `trento_invoice_change_payment_data`
module — a `post_init_hook` migrates the members of its old group.

**CNAB boleto reissue.** Any renegotiation of an inbound document whose
payment mode uses a CNAB method (240/400/500) reissues the boleto PDF
after the CNAB registration. The declared dependency only ships a no-op
stub for `generate_boleto_pdf()`: the actual PDF comes from a boleto
provider module such as `l10n_br_account_payment_brcobranca`, expected to
be installed in the target database.

**Safety guards.** Installments with a partial payment are refused with a
clean error (upstream would crash midway through the surgery); a header
mode swap cannot be mixed with divergent per-installment modes.

The module also ships pt_BR translations for its own strings and for the
upstream module's model terms (via `i18n_extra`). Python messages of the
upstream module itself (manager-only paths) remain in English — an Odoo
16 limitation, since code translations only load from the po files of the
module that owns the string.
