# Copyright (C) 2023-Today - Engenere (<https://engenere.one>).
# @author Felipe Motter Pereira <felipe@engenere.one>

from lxml import etree

from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def fields_view_get(
        self, view_id=None, view_type="form", toolbar=False, submenu=False
    ):
        """The purpose of this is to write a context on "order_line" field
        respecting other contexts on this field.
        There is a PR (https://github.com/odoo/odoo/pull/26607) to odoo for
        avoiding this. If merged, remove this method and add the attribute
        in the field.
        """
        res = super(SaleOrder, self).fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu,
        )
        if view_type == "form":
            order_xml = etree.XML(res["arch"])
            order_line_fields = order_xml.xpath("//field[@name='order_line']")
            if order_line_fields:
                order_line_field = order_line_fields[0]
                context = order_line_field.attrib.get("context", "{}").replace(
                    "{",
                    "{'default_partner_order': client_order_ref, ",
                    1,
                )
                order_line_field.attrib["context"] = context
                res["arch"] = etree.tostring(order_xml)
        return res
