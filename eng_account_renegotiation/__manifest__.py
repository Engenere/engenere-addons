# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Engenere Account Renegotiation",
    "summary": """Unified payment renegotiation: a dedicated group lets
        Billing users renegotiate vendor bill installments without
        Invoicing Manager rights, and the renegotiation wizard can also
        replace the invoice payment mode and reissue CNAB boletos when a
        boleto provider such as l10n_br_account_payment_brcobranca is
        installed (absorbing trento_invoice_change_payment_data).""",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Engenere",
    "website": "https://github.com/Engenere/engenere-addons",
    "maintainers": ["felipemotter"],
    "depends": [
        "l10n_br_account_renegotiation",
        # The upstream wizard calls account.move.update_payment_term_number(),
        # which is defined in l10n_br_account but missing from its manifest
        "l10n_br_account",
        # load_cnab_info() / generate_boleto_pdf() for the CNAB reissue
        "l10n_br_account_payment_order",
    ],
    "data": [
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "views/account_move_views.xml",
        "wizards/installment_renegotiation_wizard_views.xml",
    ],
    "demo": [],
    "post_init_hook": "post_init_hook",
}
