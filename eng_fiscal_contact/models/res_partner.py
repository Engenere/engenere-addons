from odoo import api, exceptions, models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    fiscal_contact_ids = fields.Many2many(
        'res.partner',
        relation='eng_fiscal_contact_res_partner_rel',
        column1='partner_id',
        column2='fiscal_contact_id',
        string='Contacts',
        domain="[ '|', ('parent_id', '=', parent_id), ('parent_id', '=', id) ]",
        help="The field enables users to add key individuals for tax-related matters, "
             "streamlining communication on document status changes. "
             "This addition simplifies contact management."
    )

    @api.constrains('fiscal_contact_ids')
    def _check_email_for_contacts(self):
        for contact in self.fiscal_contact_ids:
            if not contact.email:
                raise exceptions.ValidationError('All tax contacts are required to have an email address.')
