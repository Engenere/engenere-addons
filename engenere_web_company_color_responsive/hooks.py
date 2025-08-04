import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """
    Executa apenas uma vez, logo após a instalação/upgrade do módulo.

    * Percorre TODAS as empresas.
    * Força a (re)geração do attachment SCSS.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env["res.company"].search([])
    _logger.info(
        "engenere_web_company_color_responsive: gerando SCSS para %d empresas",
        len(companies),
    )
    companies.scss_create_or_update_attachment()
