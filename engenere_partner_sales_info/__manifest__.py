{
    "name": "Partner Sales Information",
    "version": "16.0.1.0.0",
    "category": "Sales",
    "summary": "Add sales analysis fields to partners",
    "author": "Engenere",
    "maintainers": ["felipemotter"],
    "website": "https://github.com/Engenere/engenere-addons",
    "depends": ["sale_management", "account"],
    "data": [
        "security/partner_sales_analysis_security.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "AGPL-3",
}
