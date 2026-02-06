# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    cr = env.cr

    _migrate_vehicles(cr)
    _migrate_responsibles(cr)
    _cleanup(cr)


def _migrate_vehicles(cr):
    """Create partner.confirmation.vehicle records from referenced fleet.vehicle."""
    # Create new vehicle records from fleet.vehicle names
    openupgrade.logged_query(
        cr,
        """
        INSERT INTO partner_confirmation_vehicle (name, create_uid, create_date,
                                                  write_uid, write_date)
        SELECT fv.name, 1, NOW() AT TIME ZONE 'UTC', 1, NOW() AT TIME ZONE 'UTC'
        FROM fleet_vehicle fv
        WHERE fv.id IN (
            SELECT DISTINCT legacy_fleet_vehicle_id
            FROM account_invoice_partner_confirmation
            WHERE legacy_fleet_vehicle_id IS NOT NULL
        )
        """,
    )

    # Update vehicle_id in confirmation records mapping old fleet.vehicle to new records
    openupgrade.logged_query(
        cr,
        """
        UPDATE account_invoice_partner_confirmation aipc
        SET vehicle_id = pcv.id
        FROM partner_confirmation_vehicle pcv
        JOIN fleet_vehicle fv ON fv.name = pcv.name
        WHERE aipc.legacy_fleet_vehicle_id = fv.id
          AND aipc.legacy_fleet_vehicle_id IS NOT NULL
        """,
    )


def _migrate_responsibles(cr):
    """Create partner.confirmation.responsible records from referenced hr.employee."""
    # Create new responsible records from hr.employee names
    openupgrade.logged_query(
        cr,
        """
        INSERT INTO partner_confirmation_responsible (name, create_uid, create_date,
                                                      write_uid, write_date)
        SELECT he.name, 1, NOW() AT TIME ZONE 'UTC', 1, NOW() AT TIME ZONE 'UTC'
        FROM hr_employee he
        WHERE he.id IN (
            SELECT DISTINCT hr_employee_id
            FROM __legacy_confirmation_employee_rel
        )
        """,
    )

    # Populate new M2M relation table
    openupgrade.logged_query(
        cr,
        """
        INSERT INTO confirmation_responsible_rel
            (account_invoice_partner_confirmation_id,
             partner_confirmation_responsible_id)
        SELECT
            rel.account_invoice_partner_confirmation_id,
            pcr.id
        FROM __legacy_confirmation_employee_rel rel
        JOIN hr_employee he ON he.id = rel.hr_employee_id
        JOIN partner_confirmation_responsible pcr ON pcr.name = he.name
        """,
    )


def _cleanup(cr):
    """Drop legacy column and temporary table."""
    openupgrade.logged_query(
        cr,
        """
        ALTER TABLE account_invoice_partner_confirmation
        DROP COLUMN IF EXISTS legacy_fleet_vehicle_id
        """,
    )
    openupgrade.logged_query(
        cr,
        """
        DROP TABLE IF EXISTS __legacy_confirmation_employee_rel
        """,
    )
