import math
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import _, fields, models


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
    order_count = fields.Integer(
        string="Number of Orders",
        compute="_compute_sales_info",
        help="Total number of sale orders for this customer",
    )
    total_ordered = fields.Monetary(
        string="Total Ordered",
        compute="_compute_sales_info",
        help="Sum of all sale order amounts for this customer",
    )
    average_ordered = fields.Monetary(
        string="Average Ordered",
        compute="_compute_sales_info",
        help="Average sale order amount for this customer",
    )
    average_ordered_no_discrepancies = fields.Monetary(
        string="Average Ordered (No Discrepancies)",
        compute="_compute_sales_info",
        help="Average order amount excluding outliers",
    )
    average_time_between_orders = fields.Float(
        string="Average Time Between Orders (Days)",
        compute="_compute_sales_info",
        help="Average number of days between sale orders",
    )
    days_since_last_order = fields.Integer(
        string="Days Since Last Order",
        compute="_compute_sales_info",
        help="Number of days since the most recent sale order",
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
    analysis_message = fields.Html(
        string="Analysis Message",
        compute="_compute_analysis_message",
        sanitize=False,
        translate=True,
    )

    def _compute_analysis_message(self):
        """Compute the HTML message for analysis."""
        config_param = self.env["ir.config_parameter"].sudo()
        months = config_param.get_param(
            "engenere_partner_sales_info.default_analysis_months", 24
        )
        analysis_months = int(months)
        msg_text = _(
            "Analysis period: %(months)d months. "
            "Note: bonus amounts are not excluded."
        ) % {"months": analysis_months}
        message = (
            "<div style='font-size:16px; color:#005cbf; font-weight:bold;"
            " text-align:center;'>"
            f"{msg_text}"
            "</div>"
        )
        for partner in self:
            partner.analysis_message = message

    def _compute_sales_info(self):
        """Compute stats for sale orders and invoices."""
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

        # Sale Orders
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

        # Invoices
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
                count_so = len(so_list)
                total_so = sum(o.amount_total for o in so_list)
                avg_so = total_so / count_so if count_so else 0
                if count_so >= 3:
                    amounts_so = [o.amount_total for o in so_list]
                    mean_so = total_so / count_so
                    var_so = sum((x - mean_so) ** 2 for x in amounts_so) / count_so
                    std_dev_so = math.sqrt(var_so)
                    lower_so = mean_so - 1.5 * std_dev_so
                    upper_so = mean_so + 1.5 * std_dev_so
                    filtered_so = [x for x in amounts_so if lower_so <= x <= upper_so]
                    avg_no_disc_so = (
                        (sum(filtered_so) / len(filtered_so))
                        if filtered_so
                        else mean_so
                    )
                else:
                    avg_no_disc_so = avg_so

                avg_time_so = 0
                if count_so >= 2:
                    dates_so = [o.date_order.date() for o in so_list]
                    total_days_so = 0
                    for idx in range(1, len(dates_so)):
                        total_days_so += (dates_so[idx] - dates_so[idx - 1]).days
                    avg_time_so = total_days_so / (count_so - 1)

                partner.order_count = count_so
                partner.total_ordered = total_so
                partner.average_ordered = avg_so
                partner.average_ordered_no_discrepancies = avg_no_disc_so
                partner.average_time_between_orders = avg_time_so
                today = fields.Date.context_today(self)
                partner.days_since_last_order = (
                    (today - so_list[-1].date_order.date()).days
                    if so_list[-1].date_order
                    else 0
                )
            else:
                partner.last_order_id = False
                partner.last_order_date = False
                partner.last_order_status = False
                partner.order_count = 0
                partner.total_ordered = 0
                partner.average_ordered = 0
                partner.average_ordered_no_discrepancies = 0
                partner.average_time_between_orders = 0
                partner.days_since_last_order = 0

            inv_list = sorted(
                from_inv.get(partner.id, []), key=lambda x: x.invoice_date
            )
            if inv_list:
                partner.last_invoice_id = inv_list[-1].id
                partner.last_invoice_date = inv_list[-1].invoice_date
                count_inv = len(inv_list)
                total_inv = sum(i.amount_total for i in inv_list)
                avg_inv = total_inv / count_inv if count_inv else 0
                if count_inv >= 3:
                    amounts_inv = [i.amount_total for i in inv_list]
                    mean_inv = total_inv / count_inv
                    var_inv = sum((x - mean_inv) ** 2 for x in amounts_inv) / count_inv
                    std_dev_inv = math.sqrt(var_inv)
                    lower_inv = mean_inv - 1.5 * std_dev_inv
                    upper_inv = mean_inv + 1.5 * std_dev_inv
                    filtered_inv = [
                        x for x in amounts_inv if lower_inv <= x <= upper_inv
                    ]
                    avg_no_disc_inv = (
                        (sum(filtered_inv) / len(filtered_inv))
                        if filtered_inv
                        else mean_inv
                    )
                else:
                    avg_no_disc_inv = avg_inv

                avg_time_inv = 0
                if count_inv >= 2:
                    dates_inv = [i.invoice_date for i in inv_list]
                    total_days_inv = 0
                    for i in range(1, len(dates_inv)):
                        total_days_inv += (dates_inv[i] - dates_inv[i - 1]).days
                    avg_time_inv = total_days_inv / (count_inv - 1)

                partner.invoice_count = count_inv
                partner.total_invoiced = total_inv
                partner.average_invoiced = avg_inv
                partner.average_invoiced_no_discrepancies = avg_no_disc_inv
                partner.average_time_between_invoices = avg_time_inv
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

        # Reset stats for non-customers
        for partner in self - partners:
            partner.update(
                {
                    "last_order_id": False,
                    "last_order_date": False,
                    "last_order_status": False,
                    "order_count": 0,
                    "total_ordered": 0,
                    "average_ordered": 0,
                    "average_ordered_no_discrepancies": 0,
                    "average_time_between_orders": 0,
                    "days_since_last_order": 0,
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
