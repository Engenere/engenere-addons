{
    "name": "Engenere Danfe Boleto",
    "summary": """
        Print Boleto Button Visualization and Danfe + Boleto Generation
    """,
    "license": "AGPL-3",
    "maintainers": ["cristianomafrajunior"],
    "website": "https://engenere.one",
    "version": "14.0.1.0.0",
    "author": "Engenere",
    "depends": [
        "l10n_br_account",
        "l10n_br_account_nfe",
        "l10n_br_account_payment_brcobranca",
    ],
    "data": [
        "views/l10n_br_fiscal_document_view.xml",
        "views/account_move_view.xml",
    ],
    "installable": True,
}
