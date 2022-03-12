# Copyright 2022 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Account Invoice Partner Confirmation",
    "summary": """
        This module is for companies that need to control the receipt of goods and invoices by partners.""",
    "version": "14.0.0.0.0",
    "author": "Engenere,Odoo Community Association (OCA)",
    "maintainers": ["felipemotter", "netosjb"],
    "website": "engenere.one",
    "depends": ["mail", "fleet", "hr", "account"],
    "data": [
        "wizards/account_invoice_partner_confirmation_register.xml",
        "views/account_move.xml",
        "security/ir.model.access.csv",
        "views/account_invoice_partner_confirmation.xml",
    ],
    "demo": [],
}
