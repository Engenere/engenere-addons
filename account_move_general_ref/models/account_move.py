# Copyright (C) 2023-Today - Engenere (<https://engenere.one>).
# @author Felipe Motter Pereira <felipe@engenere.one>

from lxml import etree

from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def fields_view_get(
        self, view_id=None, view_type="form", toolbar=False, submenu=False
    ):
        """The purpose of this is to write a context on "invoice_line_ids" field
        respecting other contexts on this field.
        There is a PR (https://github.com/odoo/odoo/pull/26607) to odoo for
        avoiding this. If merged, remove this method and add the attribute
        in the field.
        """
        res = super(AccountMove, self).fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu,
        )
        if view_type == "form":
            move_xml = etree.XML(res["arch"])
            move_line_fields = move_xml.xpath("//field[@name='invoice_line_ids']")
            if move_line_fields:
                move_line_field = move_line_fields[0]
                context = move_line_field.attrib.get("context", "{}").replace(
                    "{",
                    "{'default_partner_order': ref, ",
                    1,
                )
                move_line_field.attrib["context"] = context
                res["arch"] = etree.tostring(move_xml)
        return res
