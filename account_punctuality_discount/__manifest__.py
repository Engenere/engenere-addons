# Copyright (C) 2022-Today - Engenere (<https://engenere.one>).
# @author Antônio S. Pereira Neto <neto@engenere.one>
{
    "name": "Account Punctuality Discount",
    "summary": "Allows to apply punctuality discount in invoices.",
    "category": "Accounting & Finance",
    "license": "AGPL-3",
    "author": "Engenere," "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "version": "14.0.1.0.0",
    "development_status": "Alpha",
    "depends": [
        "l10n_br_sale",
        "l10n_br_account",
        "l10n_br_account_payment_order",
    ],
    "data": [
        "views/res_partner_view.xml",
        "views/sale_order_view.xml",
        "views/account_move_view.xml",
        "views/account_payment_mode_view.xml",
    ],
}
