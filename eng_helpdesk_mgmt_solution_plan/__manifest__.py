# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Helpdesk Solution Plan (internal)",
    "version": "16.0.1.0.0",
    "category": "After-Sales",
    "summary": "Internal technical solution plan on helpdesk tickets, "
    "visible only to a dedicated group",
    "author": "Engenere,Odoo Community Association (OCA)",
    "maintainers": ["felipemotter"],
    "website": "https://github.com/Engenere/engenere-addons",
    "depends": ["helpdesk_mgmt"],
    "data": [
        "security/helpdesk_solution_plan_security.xml",
        "security/ir.model.access.csv",
        "views/helpdesk_ticket_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "AGPL-3",
}
