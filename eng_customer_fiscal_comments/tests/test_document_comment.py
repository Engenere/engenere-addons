from odoo.tests.common import TransactionCase


class TestDocumentComment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Test Client", "fiscal_comments": "Comentário fiscal teste"}
        )
        cls.document = cls.env["l10n_br_fiscal.document"].create(
            {"partner_id": cls.partner.id}
        )

    def test_document_comment(self):
        self.document._document_comment()
        self.assertEqual(
            self.document.manual_fiscal_additional_data,
            "Comentário fiscal teste",
        )
