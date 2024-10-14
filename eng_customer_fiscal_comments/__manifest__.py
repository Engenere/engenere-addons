{
    "name": "Customer Fiscal Comments ",
    "summary": """
    The Customer Fiscal Comments module enables users
    to add tax-related comments to customer profiles,
    which are displayed on invoices for better compliance.
    """,
    "license": "AGPL-3",
    "author": "Engenere",
    "maintainers": ["cristianomafrajunior"],
    "website": "https://engenere.one",
    "category": "Services/Industry",
    "version": "14.0.1.0.0",
    "development_status": "Beta",
    "depends": [
        "account",
        "l10n_br_nfe",
    ],
    "data": [
        "views/res_partner_views.xml",
    ],
    "installable": True,
}
