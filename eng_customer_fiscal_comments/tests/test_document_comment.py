from odoo.tests.common import TransactionCase


class TestDocumentComment(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {"name": "Test Client", "fiscal_comments": "Comentário fiscal teste"}
        )
        self.document = self.env["l10n_br_fiscal.document"].create(
            {"partner_id": self.partner.id}
        )

    def test_document_comment(self):
        self.document._document_comment()
        self.assertEqual(
            self.document.manual_fiscal_additional_data,
            "Comentário fiscal teste",
        )
