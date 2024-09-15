# Copyright 2024 - Engenere (<https://engenere.one>).
# @author Antônio S. Pereira Neto <neto@engenere.one>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # Verifique se o campo antigo existe no banco de dados
    if openupgrade.column_exists(
        env.cr, "account_payment_mode", "filename_sequence_id"
    ):
        # Atualizar o arquivo cnab_config_id com filename_sequence_id
        env.cr.execute(
            """
            UPDATE l10n_br_cnab_config cc
            SET filename_sequence_id = (
                SELECT filename_sequence_id
                FROM account_payment_mode apm
                WHERE apm.cnab_config_id = cc.id
            )
            WHERE EXISTS (
                SELECT 1
                FROM account_payment_mode apm
                WHERE apm.cnab_config_id = cc.id
                AND apm.filename_sequence_id IS NOT NULL
            )
        """
        )
