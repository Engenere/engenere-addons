# Copyright 2026 Engenere.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Sale Order Delivery Date in Header",
    "summary": """
        Delivery date in the sales order header and lists, optionally
        required to confirm the order.""",
    "version": "16.0.1.0.0",
    "category": "Sales",
    "license": "AGPL-3",
    "author": "Engenere",
    "maintainers": ["antoniospneto"],
    "website": "https://github.com/Engenere/engenere-addons",
    "depends": [
        "sale_stock",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/sale_order_views.xml",
    ],
}
