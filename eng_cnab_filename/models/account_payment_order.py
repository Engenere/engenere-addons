from odoo import models


class AccountPaymentOrder(models.Model):
    _inherit = "account.payment.order"

    def get_file_name(self, cnab_type):
        """
        Sobrescreve a lógica para a criação do nome a partir do sequenciador.
        """
        sequence = self.payment_mode_id.filename_sequence_id
        if sequence:
            filename = f"{sequence.next_by_id()}.REM"
        else:
            filename = super().get_file_name(cnab_type)
        return filename
