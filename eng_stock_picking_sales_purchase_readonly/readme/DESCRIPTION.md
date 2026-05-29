Restricts `stock.picking` write/create/unlink permissions for the sale and purchase
roles that Odoo ships open by default. Salesman, Sale Manager, Purchase User and
Purchase Manager keep read access on transfers but cannot edit, cancel, scrap, unreserve
or return a picking directly: only the standard `Stock User`/`Stock Manager` roles do.

The order side keeps working: confirming or cancelling a sale or purchase order
continues to create/cancel the related picking through targeted `sudo()` patches in the
overridden methods.
