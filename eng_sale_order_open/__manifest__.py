# Copyright 2026 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Engenere Sale Order Open",
    "summary": """
        Adds an 'Open' filter to sale orders (confirmed with pending delivery
        or pending invoice).""",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Engenere",
    "maintainers": ["antoniospneto"],
    "website": "https://github.com/Engenere/engenere-addons",
    "depends": [
        "l10n_br_sale_stock",
    ],
    "data": [
        "views/sale_order_view.xml",
    ],
    "demo": [],
}
