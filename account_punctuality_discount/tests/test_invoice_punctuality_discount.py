# Copyright (C) 2022 - Engenere (<https://engenere.one>).
# @author Antônio S. Pereira Neto <neto@engenere.one>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestInvoicePunctualityDiscount(AccountTestInvoicingCommon):
    """
    Test Invoice Punctuality Discount
    """

    @classmethod
    def setUpClass(
        cls, chart_template_ref="l10n_br_coa_generic.l10n_br_coa_generic_template"
    ):
        """Extend default setUpClass"""
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.partner_a.update({"punctuality_discount": 10})
