# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
{
    "name": "Web Statusbar Overflow Fix",
    "summary": "Prevents horizontal scroll when forms have many header buttons",
    "version": "16.0.1.0.0",
    "category": "Technical",
    "website": "https://github.com/Engenere/engenere-addons",
    "author": "Engenere, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "eng_web_statusbar_fix/static/src/scss/statusbar_fix.scss",
        ],
    },
    "maintainers": ["felipemotter"],
}
