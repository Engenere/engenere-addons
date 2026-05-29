Restricts write/create/unlink permissions on stock transfers (`stock.picking`,
`stock.move` and `stock.move.line`) for the sale, purchase and invoicing roles that Odoo
ships open by default. Salesman, Sale Manager, Purchase User, Purchase Manager and the
Invoicing role keep read access on transfers but cannot create, edit, cancel, scrap,
unreserve, return them or add/remove their lines: only the standard `Stock User` /
`Stock Manager` roles can.

The order side keeps working through targeted `sudo()` patches in the overridden
methods: confirming or cancelling a sale or purchase order still creates/cancels the
related transfer, a confirmed-purchase quantity bump still adjusts it, and propagating a
sale order's delivery address to its open pickings still works.

Sales and purchase users still reach their transfers in read-only through the Delivery
and Receipt smart buttons on their own orders, which the module widens to those roles
(upstream they are gated to `Stock User`).
