# Copyright (C) 2022-Today - Engenere (<https://engenere.one>).
# @author Antônio S. Pereira Neto <neto@engenere.one>
{
    "name": "Add Financial Discount Field",
    "summary": "A new field is added to inform a percentage of financial discount on"
    "the invoice if it is paid by the due date. ",
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "Engenere," "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "version": "14.0.1.0.0",
    "development_status": "Alpha",
    "depends": [
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
