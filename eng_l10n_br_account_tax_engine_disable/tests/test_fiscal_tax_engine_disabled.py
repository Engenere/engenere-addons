# Copyright 2025 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class TestFiscalDocumentLineMixinMethods(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.fiscal_taxes = (
            cls.env.ref("l10n_br_fiscal.tax_icms_7")
            + cls.env.ref("l10n_br_fiscal.tax_ipi_15")
            + cls.env.ref("l10n_br_fiscal.tax_pis_0_65")
            + cls.env.ref("l10n_br_fiscal.tax_cofins_3")
        )

        cls.fiscal_doc = cls.env["l10n_br_fiscal.document"].create(
            {
                "fiscal_operation_id": cls.env.ref("l10n_br_fiscal.fo_compras").id,
                "document_type_id": cls.env.ref("l10n_br_fiscal.document_55").id,
                "document_serie": 1,
                "document_number": 123,
                "issuer": "partner",
                "partner_id": cls.env["res.partner"]
                .create({"name": "Fornecedor X"})
                .id,
                "fiscal_operation_type": "in",
            }
        )

        cls.fiscal_line = cls.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": cls.fiscal_doc.id,
                "name": "Compra Teste",
                "product_id": cls.env["product.product"]
                .create({"name": "Produto Teste"})
                .id,
                "fiscal_operation_type": "in",
                "fiscal_operation_id": cls.env.ref("l10n_br_fiscal.fo_compras").id,
                "fiscal_operation_line_id": cls.env.ref(
                    "l10n_br_fiscal.fo_compras_compras"
                ).id,
                "icms_value": 10.0,
                "ipi_value": 15.0,
                "pis_value": 0.65,
                "cofins_value": 3.0,
            }
        )

    def test_is_fiscal_tax_engine_disabled(self):
        self.fiscal_doc.fiscal_tax_engine_disabled = False
        self.assertFalse(self.fiscal_line._is_fiscal_tax_engine_disabled())

        self.fiscal_doc.fiscal_tax_engine_disabled = True
        self.assertTrue(self.fiscal_line._is_fiscal_tax_engine_disabled())

    def test_remove_all_fiscal_tax_ids(self):
        self.fiscal_doc.fiscal_tax_engine_disabled = False
        self.assertEqual(self.fiscal_line.cofins_value, 3.0)
        self.assertEqual(self.fiscal_line.icms_value, 10.0)
        self.assertEqual(self.fiscal_line.ipi_value, 15.0)
        self.assertEqual(self.fiscal_line.pis_value, 0.65)

        self.fiscal_line._remove_all_fiscal_tax_ids()
        self.assertEqual(self.fiscal_line.cofins_value, 0.0)
        self.assertEqual(self.fiscal_line.icms_value, 0.0)
        self.assertEqual(self.fiscal_line.ipi_value, 0.0)
        self.assertEqual(self.fiscal_line.pis_value, 0.0)

    def test_prepare_tax_fields(self):
        self.assertEqual(self.fiscal_line._prepare_tax_fields({}), {})

        self.fiscal_doc.fiscal_tax_engine_disabled = True
        self.assertEqual(self.fiscal_line._prepare_tax_fields({}), {})

    def test_update_fiscal_taxes(self):
        self.fiscal_doc.fiscal_tax_engine_disabled = False
        initial_tax_included = self.fiscal_line.amount_tax_included
        initial_tax_not_included = self.fiscal_line.amount_tax_not_included
        self.fiscal_doc.fiscal_tax_engine_disabled = True

        self.fiscal_line._update_fiscal_taxes()
        self.assertNotEqual(self.fiscal_line.amount_tax_included, initial_tax_included)
        self.assertEqual(self.fiscal_line.amount_tax_included, 13.65)
        self.assertNotEqual(
            self.fiscal_line.amount_tax_not_included, initial_tax_not_included
        )
        self.assertEqual(self.fiscal_line.amount_tax_not_included, 15.0)
