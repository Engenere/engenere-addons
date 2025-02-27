from odoo.tests.common import TransactionCase


class TestFileName(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Journal 1",
                "code": "J1",
                "type": "bank",
                "company_id": cls.company.id,
            }
        )
        cls.manual_out = cls.env.ref("account.account_payment_method_manual_out")
        cls.partner_id = cls.env.ref("base.res_partner_12")
        cls.sequence = cls.env["ir.sequence"].create(
            {
                "name": "test seq",
                "implementation": "standard",
                "padding": 5,
                "number_increment": 1,
            }
        )
        cls.cnab_config = cls.env["l10n_br_cnab.config"].create(
            {
                "name": "CNAB config test",
                "company_id": cls.company.id,
                "filename_sequence_id": cls.sequence.id,
            }
        )
        cls.payment_mode = cls.env["account.payment.mode"].create(
            {
                "name": "Test Payment Mode",
                "bank_account_link": "variable",
                "payment_method_id": cls.manual_out.id,
                "company_id": cls.company.id,
                "fixed_journal_id": cls.journal.id,
                "variable_journal_ids": [(6, 0, [cls.journal.id])],
                "cnab_config_id": cls.cnab_config.id,
            }
        )

    def test_file_name(self):
        self.payment_order_id = self.env["account.payment.order"].create(
            {
                "payment_mode_id": self.payment_mode.id,
                "journal_id": self.journal.id,
                "payment_type": "outbound",
                "payment_line_ids": [
                    (
                        0,
                        0,
                        {
                            "amount_currency": 200.00,
                            "partner_id": self.partner_id.id,
                            "communication": "TEST",
                        },
                    )
                ],
            }
        )

        self.payment_order_id.draft2open()
        self.payment_order_id.open2generated()
        filename = self.payment_order_id.get_file_name("240")
        self.assertEqual("00001.REM", filename)
