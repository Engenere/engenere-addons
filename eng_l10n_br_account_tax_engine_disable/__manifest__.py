# Copyright 2024 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Account Tax Engine Disable",
    "sumarry": """This module disables the automatic tax calculation on Odoo invoices,
    allowing manual entry based
    on the supplier's invoice, useful for cases like imports.
    """,
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Engenere",
    "maintainers": ["felipemotter"],
    "website": "https://github.com/Engenere/engenere-addons",
    "depends": [
        "l10n_br_account",
    ],
    "data": [
        "views/l10n_br_fiscal_document.xml",
    ],
    "demo": [],
}
