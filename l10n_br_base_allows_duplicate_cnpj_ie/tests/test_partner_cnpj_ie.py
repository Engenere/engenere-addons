# Copyright 2025 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class TestPartnerCNPJIE(TransactionCase):
    def test_create_partner_validation(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Company",
                "cnpj_cpf": "12345678000195",
                "inscr_est": "123456789",
            }
        )
        self.assertTrue(partner.id)
        self.assertEqual(partner.cnpj_cpf, "12345678000195")
        self.assertEqual(partner.inscr_est, "123456789")

        partner_duplicate = self.env["res.partner"].create(
            {
                "name": "Test Company 1",
                "cnpj_cpf": "12345678000195",
                "inscr_est": "123456789",
            }
        )
        self.assertTrue(partner_duplicate.id)
        self.assertEqual(partner_duplicate.cnpj_cpf, "12345678000195")
        self.assertEqual(partner_duplicate.inscr_est, "123456789")
