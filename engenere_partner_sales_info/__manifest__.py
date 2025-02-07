{
    "name": "Partner Sales Information",
    "version": "14.0.1.0.0",
    "category": "Sales",
    "summary": "Add sales analysis fields to partners",
    "author": "Engenere",
    "maintainers": ["felipempereira"],
    "website": "https://engenere.one",
    "depends": ["sale", "account"],
    "data": [
        "security/partner_sales_analysis_security.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "AGPL-3",
}
