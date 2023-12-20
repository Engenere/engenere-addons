from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = "account.move"

    document_number_integer = fields.Integer(string='document_number_integer', compute='_compute_document_member_integer',store=True)

    @api.depends('document_number')
    def _compute_document_member_integer(self):
        for record in self:
            record.document_number_integer = int(record.document_number)
