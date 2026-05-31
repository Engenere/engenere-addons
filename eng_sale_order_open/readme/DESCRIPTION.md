Adds an `Open` boolean to `sale.order` and a matching filter in the search view.

A sale order is considered **open** when it is confirmed (`state == 'sale'` or `'done'`) **and** any of:

- there is a related stock picking not in `done`/`cancel` state (pending delivery);
- the order is not fully invoiced **and** some line still has `qty_to_invoice > 0` (pending invoice);
- the order has **no net activity** — nothing delivered and nothing invoiced. This keeps freshly-confirmed orders open and also forces explicit handling of full-reversal scenarios (delivered + returned + invoiced + refunded back to zero), pushing the user to cancel the order.

Short-shipment within tolerance closes naturally: once pickings are validated without backorder and the delivered quantity is invoiced, both `qty_to_invoice` and pending-picking checks return false, regardless of `qty_delivered < product_uom_qty`. Manual overrides like `force_invoiced` (from `sale_force_invoiced`) are honored because they set `invoice_status='invoiced'`.

This helps the sales team quickly answer "what is still pending for customer X?" without combining multiple filters.
