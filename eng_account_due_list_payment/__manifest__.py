# Copyright 2025 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Engenere Account Due List Payment",
    "summary": """
        Allows you to make payments directly from the due list view""",
    "version": "16.0.1.0.1",
    "license": "AGPL-3",
    "maintainers": ["felipemotter"],
    "author": "Engenere,Odoo Community Association (OCA)",
    "website": "https://github.com/Engenere/engenere-addons",
    "depends": [
        "account_due_list",
    ],
    "data": [
        "views/account_move_line.xml",
    ],
    "demo": [],
}
