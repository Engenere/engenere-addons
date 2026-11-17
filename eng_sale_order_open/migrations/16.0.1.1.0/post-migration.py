# Copyright 2026 Engenere.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

from odoo.tools import split_every

_BATCH_SIZE = 500


@openupgrade.migrate()
def migrate(env, version):
    """Recompute ``is_open``: ``force_invoiced`` now always closes the order.

    Done in batches, dropping the cache in between: the order lines carry the
    whole fiscal document line, so prefetching every confirmed order at once
    runs out of memory.
    """
    sale_order = env["sale.order"]
    order_ids = sale_order.search([("state", "in", ("sale", "done"))]).ids
    for batch_ids in split_every(_BATCH_SIZE, order_ids):
        orders = sale_order.browse(batch_ids)
        env.add_to_compute(sale_order._fields["is_open"], orders)
        orders.flush_recordset(["is_open"])
        env.invalidate_all()
