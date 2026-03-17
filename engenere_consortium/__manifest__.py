# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Brazilian Consortium Management",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "maintainers": ["felipemotter"],
    "author": "Engenere",
    "website": "https://github.com/Engenere/engenere-addons",
    "depends": ["account", "mail"],
    "data": [
        "security/engenere_consortium.xml",
        "security/ir.model.access.csv",
        "data/consortium_component_type_data.xml",
        "views/consortium_component_type.xml",
        "views/consortium_installment.xml",
        "views/consortium_readjustment.xml",
        "views/consortium_quota.xml",
        "wizards/consortium_readjustment_wizard.xml",
        "wizards/consortium_generate_invoice_wizard.xml",
        "views/menu.xml",
    ],
    "demo": [],
}
