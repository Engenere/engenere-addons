# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Engenere CNAB Clearing",
    "summary": """Settle CNAB return liquidations on the occurrence date
        against a bank clearing account, with no bank or tariff lines,
        so that the bank statement is the only source of the bank
        account.""",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Engenere",
    "maintainers": ["felipemotter"],
    "website": "https://github.com/Engenere/engenere-addons",
    "depends": [
        "l10n_br_account_payment_brcobranca",
        "l10n_br_account_payment_order",
        "account_move_base_import",
    ],
    "data": [
        "views/account_journal_views.xml",
        "views/l10n_br_cnab_return_views.xml",
    ],
    "installable": True,
}
