# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)

OLD_GROUP_XMLID = "trento_invoice_change_payment_data.group_payment_data"
NEW_GROUP_XMLID = "eng_account_renegotiation.group_vendor_bill_renegotiation"


def post_init_hook(cr, registry):
    """Copy the members of the retired trento_invoice_change_payment_data
    group into the new unified group, when that module is installed.

    Idempotent: adding a user twice to a m2m is a no-op. Without this,
    the rollout would silently drop the access of the old group members.
    """
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    old_group = env.ref(OLD_GROUP_XMLID, raise_if_not_found=False)
    if not old_group:
        _logger.info("Old group %s not found; no members to migrate.", OLD_GROUP_XMLID)
        return
    new_group = env.ref(NEW_GROUP_XMLID)
    users = old_group.users
    if not users:
        _logger.info("Old group %s has no members to migrate.", OLD_GROUP_XMLID)
        return
    new_group.write({"users": [(4, user.id) for user in users]})
    _logger.info(
        "Migrated %s member(s) from %s to %s: %s",
        len(users),
        OLD_GROUP_XMLID,
        NEW_GROUP_XMLID,
        ", ".join(users.mapped("login")),
    )
