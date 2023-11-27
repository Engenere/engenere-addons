# Copyright 2023 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': 'Engenere Danfe',
    'description': """
        Generate a new danfe layout compatible with OCA/l10n_brazil""",
    'version': '12.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Engenere.one',
    'website': 'https://engenere.one',
    'depends': [
        "l10n_br_account",
    ],
    'data': [
        "reports/danfe_report.xml"
    ],
    'demo': [
    ],
}
