# Copyright 2025 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Engenere Sale First Time State",
    "summary": """
        Indicates whether the product is sold for the first time to the partner.""",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Engenere",
    "maintainers": ["felipemotter"],
    "website": "https://github.com/Engenere/engenere-addons",
    "depends": [
        "l10n_br_sale",  # TODO só sale da conflito nos testes por causa da l10n_brazil
    ],
    "data": [
        "views/sale_order_view.xml",
        "views/sale_config_settings.xml",
    ],
    "demo": [],
}
