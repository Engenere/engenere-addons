{
    'name': 'Danfe Engenere Report',
    'description': """
        Generate a new danfe layout compatible with
        OCA/l10n brazil for the BrazilFiscalReport
        library and ErpBrasil.edoc""",
    "version": "14.0.1.0.0",
    'license': 'AGPL-3',
    "maintainers": ["cristianomafrajunior"],
    'author': 'Engenere',
    'website': 'https://engenere.one',
    'depends': [
        "l10n_br_account",
    ],
    'data': [
        "reports/danfe_report.xml"
    ],
}
