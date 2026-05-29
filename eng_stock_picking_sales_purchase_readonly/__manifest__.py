{
    "name": "Stock Picking - Read-Only for Sales & Purchase",
    "summary": (
        "Make stock transfers (picking, moves, move lines) read-only for the "
        "Sales, Purchase and Invoicing roles: they can view transfers but "
        "cannot edit, cancel, scrap, unreserve, return or add lines. "
        "Order-side flows (confirm/cancel SO/PO, qty bump, delivery address) "
        "keep working."
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
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "security/server_actions.xml",
        "views/stock_picking_views.xml",
        "views/sale_order_views.xml",
        "views/purchase_order_views.xml",
    ],
    "installable": True,
}
