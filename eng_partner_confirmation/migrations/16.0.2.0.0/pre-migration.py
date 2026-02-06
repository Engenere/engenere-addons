# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    cr = env.cr

    # Rename vehicle_id column to preserve legacy fleet.vehicle references
    openupgrade.logged_query(
        cr,
        """
        ALTER TABLE account_invoice_partner_confirmation
        RENAME COLUMN vehicle_id TO legacy_fleet_vehicle_id
        """,
    )

    # Drop stored computed column part_confirm_vehicle_id from account_move
    # (it will be recreated by ORM with new comodel)
    openupgrade.logged_query(
        cr,
        """
        ALTER TABLE account_move
        DROP COLUMN IF EXISTS part_confirm_vehicle_id
        """,
    )

    # Save M2M data from the old hr.employee relation table
    openupgrade.logged_query(
        cr,
        """
        CREATE TABLE IF NOT EXISTS __legacy_confirmation_employee_rel AS
        SELECT *
        FROM account_invoice_partner_confirmation_hr_employee_rel
        """,
    )
