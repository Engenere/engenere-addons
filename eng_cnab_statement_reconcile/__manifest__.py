# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Engenere CNAB Statement Reconcile",
    "summary": """Reconcile each collection credit of the bank statement with
        the whole group of CNAB clearing lines due on its date, only when
        the amounts match exactly, with an exclusive routing, retries and
        a visible reason for the pending lines.""",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Engenere",
    "maintainers": ["felipemotter"],
    "website": "https://github.com/Engenere/engenere-addons",
    "depends": [
        "eng_cnab_clearing",
        "account_reconcile_oca",
        "account_statement_import_file",
    ],
    "data": [
        "data/ir_cron_data.xml",
        "views/account_reconcile_model_views.xml",
        "views/account_bank_statement_line_views.xml",
    ],
    "installable": True,
}
