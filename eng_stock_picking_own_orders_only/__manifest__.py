{
    "name": "Stock Picking - Own Orders Only",
    "summary": (
        "Restrict transfer visibility for Sales/Purchase roles to their own "
        "orders and hide destructive picking buttons from them. Stock and "
        "Shipping Viewer roles keep their broad visibility."
    ),
    "license": "LGPL-3",
    "author": "Engenere, Engenere.one",
    "maintainers": ["felipemotter"],
    "website": "https://github.com/Engenere/engenere-addons",
    "version": "16.0.1.0.0",
    "depends": [
        "sale_stock",
        "purchase_stock",
    ],
    "data": [
        "security/record_rules.xml",
        "security/server_actions.xml",
        "views/stock_picking_views.xml",
    ],
    "installable": True,
}
