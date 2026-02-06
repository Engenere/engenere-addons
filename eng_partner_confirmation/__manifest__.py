# Copyright 2022 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Account Invoice Partner Confirmation",
    "summary": """
        This module is for companies that need to control
        the receipt of goods and invoices by partners.""",
    "version": "16.0.2.0.0",
    "author": "Engenere,Odoo Community Association (OCA)",
    "maintainers": ["felipemotter", "antoniospneto"],
    "website": "https://github.com/Engenere/engenere-addons",
    "license": "AGPL-3",
    "depends": ["mail", "account"],
    "data": [
        "security/partner_confirmation_security.xml",
        "security/ir.model.access.csv",
        "wizards/account_invoice_partner_confirmation_register.xml",
        "views/account_move.xml",
        "views/account_invoice_partner_confirmation.xml",
        "views/partner_confirmation_vehicle.xml",
        "views/partner_confirmation_responsible.xml",
    ],
    "demo": [],
}
