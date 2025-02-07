import math
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    last_order_id = fields.Many2one(
        "sale.order",
        string="Last Order",
        compute="_compute_sales_info",
        help="Last sale order of this customer",
    )
    last_order_date = fields.Date(
        string="Last Order Date",
        compute="_compute_sales_info",
        help="Date of the customer's most recent sale order",
    )
    last_order_status = fields.Char(
        string="Last Order Status",
        compute="_compute_sales_info",
        help="Status of the customer's most recent sale order",
    )
    last_invoice_date = fields.Date(
        string="Last Invoice Date",
        compute="_compute_sales_info",
        help="Date of the customer's most recent invoice",
    )
    invoice_count = fields.Integer(
        string="Number of Invoices",
        compute="_compute_sales_info",
        help="Total number of invoices for this customer",
    )
    total_invoiced = fields.Monetary(
        string="Total Invoiced",
        compute="_compute_sales_info",
        help="Sum of all invoice amounts for this customer",
    )
    average_invoiced = fields.Monetary(
        string="Average Invoiced",
        compute="_compute_sales_info",
        help="Average invoice amount for this customer",
    )
    average_invoiced_no_discrepancies = fields.Monetary(
        string="Average Invoiced (No Discrepancies)",
        compute="_compute_sales_info",
        help="Average invoice amount excluding outliers",
    )
    average_time_between_invoices = fields.Float(
        string="Average Time Between Invoices (Days)",
        compute="_compute_sales_info",
        help="Average number of days between invoices",
    )
    last_invoice_id = fields.Many2one(
        "account.move",
        string="Last Invoice",
        compute="_compute_sales_info",
        help="Most recent invoice of this customer",
    )
    days_since_last_invoice = fields.Integer(
        string="Days Since Last Invoice",
        compute="_compute_sales_info",
        help="Number of days since the most recent invoice",
    )

    @api.depends()
    def _compute_sales_info(self):
        config_param = self.env["ir.config_parameter"].sudo()
        months = config_param.get_param(
            "engenere_partner_sales_info.default_analysis_months", 24
        )
        analysis_months = int(months)
        start_date = fields.Date.context_today(self) - relativedelta(
            months=analysis_months
        )
        partners = self.filtered(lambda p: p.customer_rank > 0)
        partner_ids = partners.ids

        sale_orders = self.env["sale.order"].search(
            [
                ("partner_id", "in", partner_ids),
                ("state", "!=", "cancel"),
                ("date_order", ">=", start_date),
            ]
        )
        from_so = defaultdict(list)
        for so in sale_orders:
            from_so[so.partner_id.id].append(so)

        invoices = self.env["account.move"].search(
            [
                ("partner_id", "in", partner_ids),
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("reversed_entry_id", "=", False),
                ("invoice_date", ">=", start_date),
            ]
        )
        from_inv = defaultdict(list)
        for inv in invoices:
            from_inv[inv.partner_id.id].append(inv)

        for partner in partners:
            so_list = sorted(from_so.get(partner.id, []), key=lambda x: x.date_order)
            if so_list:
                partner.last_order_id = so_list[-1].id
                partner.last_order_date = so_list[-1].date_order.date()
                partner.last_order_status = so_list[-1].state
            else:
                partner.last_order_id = False
                partner.last_order_date = False
                partner.last_order_status = False

            inv_list = sorted(
                from_inv.get(partner.id, []), key=lambda x: x.invoice_date
            )
            if inv_list:
                partner.last_invoice_id = inv_list[-1].id
                partner.last_invoice_date = inv_list[-1].invoice_date
                count = len(inv_list)
                total = sum(i.amount_total for i in inv_list)
                avg = total / count if count else 0

                if count >= 3:
                    amounts = [i.amount_total for i in inv_list]
                    mean = total / count
                    var = sum((x - mean) ** 2 for x in amounts) / count
                    std_dev = math.sqrt(var)
                    lower = mean - 1.5 * std_dev
                    upper = mean + 1.5 * std_dev
                    filtered = [x for x in amounts if lower <= x <= upper]
                    if filtered:
                        avg_no_disc = sum(filtered) / len(filtered)
                    else:
                        avg_no_disc = mean
                else:
                    avg_no_disc = avg

                avg_time = 0
                if count >= 2:
                    dates = [i.invoice_date for i in inv_list]
                    total_days = 0
                    for i in range(1, len(dates)):
                        total_days += (dates[i] - dates[i - 1]).days
                    avg_time = total_days / (count - 1)

                partner.invoice_count = count
                partner.total_invoiced = total
                partner.average_invoiced = avg
                partner.average_invoiced_no_discrepancies = avg_no_disc
                partner.average_time_between_invoices = avg_time

                today = fields.Date.context_today(self)
                partner.days_since_last_invoice = (
                    (today - partner.last_invoice_date).days
                    if partner.last_invoice_date
                    else 0
                )
            else:
                partner.last_invoice_id = False
                partner.last_invoice_date = False
                partner.invoice_count = 0
                partner.total_invoiced = 0
                partner.average_invoiced = 0
                partner.average_invoiced_no_discrepancies = 0
                partner.average_time_between_invoices = 0
                partner.days_since_last_invoice = 0

        for partner in self - partners:
            partner.update(
                {
                    "last_order_id": False,
                    "last_order_date": False,
                    "last_order_status": False,
                    "last_invoice_date": False,
                    "invoice_count": 0,
                    "total_invoiced": 0,
                    "average_invoiced": 0,
                    "average_invoiced_no_discrepancies": 0,
                    "average_time_between_invoices": 0,
                    "last_invoice_id": False,
                    "days_since_last_invoice": 0,
                }
            )
