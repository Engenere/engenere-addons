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
        compute="_compute_sales_info",
        help="Date of the customer's most recent sale order",
    )
    last_order_status = fields.Selection(
        [
            ("draft", "Quotation"),
            ("sent", "Quotation Sent"),
            ("sale", "Sales Order"),
            ("done", "Locked"),
            ("cancel", "Cancelled"),
        ],
        compute="_compute_sales_info",
        help="Status of the customer's most recent sale order",
    )
    order_count = fields.Integer(
        string="Number of Orders",
        compute="_compute_sales_info",
        help="Total number of sale orders for this customer",
    )
    total_ordered = fields.Monetary(
        compute="_compute_sales_info",
        help="Sum of all sale order amounts for this customer",
    )
    average_ordered = fields.Monetary(
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
        compute="_compute_sales_info",
        help="Number of days since the most recent sale order",
    )
    last_invoice_date = fields.Date(
        compute="_compute_sales_info",
        help="Date of the customer's most recent invoice",
    )
    invoice_count = fields.Integer(
        string="Number of Invoices",
        compute="_compute_sales_info",
        help="Total number of invoices for this customer",
    )
    total_invoiced = fields.Monetary(
        compute="_compute_sales_info",
        help="Sum of all invoice amounts for this customer",
    )
    average_invoiced = fields.Monetary(
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
        compute="_compute_sales_info",
        help="Number of days since the most recent invoice",
    )
    analysis_message = fields.Text(
        compute="_compute_analysis_message",
        translate=True,
    )
    has_open_quotation = fields.Boolean(
        string="Open Quotation Exists",
        compute="_compute_open_quotation_info",
    )
    last_open_quotation_id = fields.Many2one(
        "sale.order",
        string="Last Open Quotation",
        compute="_compute_open_quotation_info",
    )
    last_open_quotation_date = fields.Date(
        string="Last Quotation Date",
        compute="_compute_open_quotation_info",
        help="Date of the most recent draft/sent quotation",
    )

    # ========== OPEN QUOTATIONS ==========

    def _compute_open_quotation_info(self):
        """Calculate open quotations (draft/sent)."""
        for partner in self:
            partner.has_open_quotation = False
            partner.last_open_quotation_id = False
            partner.last_open_quotation_date = False

        customer_partners = self.filtered(lambda p: p.customer_rank > 0)
        if not customer_partners:
            return

        open_quotations = self.env["sale.order"].search(
            [
                ("partner_id", "in", customer_partners.ids),
                ("state", "in", ["draft", "sent"]),
            ],
            order="date_order DESC, id DESC",
        )
        partner_quotations = {}
        for quot in open_quotations:
            if quot.partner_id.id not in partner_quotations:
                partner_quotations[quot.partner_id.id] = quot

        for partner in customer_partners:
            if partner.id in partner_quotations:
                last_quot = partner_quotations[partner.id]
                partner.has_open_quotation = True
                partner.last_open_quotation_id = last_quot.id
                if last_quot.date_order:
                    partner.last_open_quotation_date = last_quot.date_order.date()

    # ========== ANALYSIS MESSAGE ==========

    def _compute_analysis_message(self):
        config_param = self.env["ir.config_parameter"].sudo()
        months = config_param.get_param(
            "engenere_partner_sales_info.default_analysis_months", 24
        )
        analysis_months = int(months)
        message = _(
            "Analysis period: %(months)d months. "
            "Note: bonus amounts are not excluded."
        ) % {"months": analysis_months}
        for partner in self:
            partner.analysis_message = message

    # ========== AUXILIARY FUNCTIONS ==========

    def _get_analysis_months(self):
        config_param = self.env["ir.config_parameter"].sudo()
        return int(
            config_param.get_param(
                "engenere_partner_sales_info.default_analysis_months", 24
            )
        )

    def _get_start_date(self, analysis_months):
        return fields.Date.context_today(self) - relativedelta(months=analysis_months)

    def _group_records_by_partner(self, records):
        grouped = defaultdict(list)
        for record in records:
            grouped[record.partner_id.id].append(record)
        return grouped

    def _prepare_record_statistics_vals(
        self, records, date_extractor, amount_extractor
    ):
        """Calculate basic statistics for a list (orders or invoices)."""
        if not records:
            return None

        sorted_records = sorted(records, key=lambda r: date_extractor(r))
        dates = [date_extractor(r) for r in sorted_records]
        amounts = [amount_extractor(r) for r in sorted_records]
        count = len(sorted_records)
        total = sum(amounts)
        average = total / count if count else 0

        avg_no_outliers = average
        if count >= 3:
            mean = average
            variance = sum((x - mean) ** 2 for x in amounts) / count
            std_dev = math.sqrt(variance)
            filtered = [
                x
                for x in amounts
                if (mean - 1.5 * std_dev) <= x <= (mean + 1.5 * std_dev)
            ]
            avg_no_outliers = sum(filtered) / len(filtered) if filtered else mean

        avg_time_between = 0.0
        if count >= 2:
            total_days = sum((dates[i] - dates[i - 1]).days for i in range(1, count))
            avg_time_between = total_days / (count - 1)

        today = fields.Date.context_today(self)
        days_since_last = 0
        if dates and dates[-1]:
            days_since_last = (today - dates[-1]).days

        return {
            "last_record": sorted_records[-1],
            "last_date": dates[-1] if dates else False,
            "count": count,
            "total": total,
            "average": average,
            "avg_no_outliers": avg_no_outliers,
            "avg_time_between": avg_time_between,
            "days_since_last": days_since_last,
        }

    # ========== UPDATE FIELDS ==========

    def _update_sales_fields(self, stats):
        """Update sales-related fields using a dictionary."""
        last_order = stats.get("last_record")
        vals = {
            "last_order_id": last_order.id if last_order else False,
            "last_order_date": stats.get("last_date", False),
            "last_order_status": last_order.state if last_order else False,
            "order_count": stats.get("count", 0),
            "total_ordered": stats.get("total", 0),
            "average_ordered": stats.get("average", 0),
            "average_ordered_no_discrepancies": stats.get("avg_no_outliers", 0),
            "average_time_between_orders": stats.get("avg_time_between", 0),
            "days_since_last_order": stats.get("days_since_last", 0),
        }
        self.update(vals)

    def _update_invoice_fields(self, stats):
        """Update invoice-related fields using a dictionary."""
        last_invoice = stats.get("last_record")
        vals = {
            "last_invoice_id": last_invoice.id if last_invoice else False,
            "last_invoice_date": stats.get("last_date", False),
            "invoice_count": stats.get("count", 0),
            "total_invoiced": stats.get("total", 0),
            "average_invoiced": stats.get("average", 0),
            "average_invoiced_no_discrepancies": stats.get("avg_no_outliers", 0),
            "average_time_between_invoices": stats.get("avg_time_between", 0),
            "days_since_last_invoice": stats.get("days_since_last", 0),
        }
        self.update(vals)

    def _reset_sales_fields(self):
        """Reset all sales-related fields to default values."""
        self.update(
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
            }
        )

    def _reset_invoice_fields(self):
        """Reset all invoice-related fields to default values."""
        self.update(
            {
                "last_invoice_id": False,
                "last_invoice_date": False,
                "invoice_count": 0,
                "total_invoiced": 0,
                "average_invoiced": 0,
                "average_invoiced_no_discrepancies": 0,
                "average_time_between_invoices": 0,
                "days_since_last_invoice": 0,
            }
        )

    # ========== MAIN COMPUTE ==========

    def _compute_sales_info(self):
        """Calculate sales and invoice metrics within the configured period."""
        analysis_months = self._get_analysis_months()
        if analysis_months <= 0:
            for partner in self:
                partner._reset_sales_fields()
                partner._reset_invoice_fields()
            return

        start_date = self._get_start_date(analysis_months)
        customer_partners = self.filtered(lambda p: p.customer_rank > 0)

        # SÓ ORDENS CONFIRMADAS OU FECHADAS
        sale_orders = self.env["sale.order"].search(
            [
                ("partner_id", "in", customer_partners.ids),
                ("state", "in", ["sale", "done"]),
                ("date_order", ">=", start_date),
            ]
        )
        sales_group = self._group_records_by_partner(sale_orders)

        # SÓ FATURAS POSTADAS
        invoices = self.env["account.move"].search(
            [
                ("partner_id", "in", customer_partners.ids),
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("reversed_entry_id", "=", False),
                ("invoice_date", ">=", start_date),
            ]
        )
        invoices_group = self._group_records_by_partner(invoices)

        for partner in customer_partners:
            so_stats = self._prepare_record_statistics_vals(
                sales_group.get(partner.id, []),
                lambda r: r.date_order.date(),
                lambda r: r.amount_total,
            )
            if so_stats:
                partner._update_sales_fields(so_stats)
            else:
                partner._reset_sales_fields()

            inv_stats = self._prepare_record_statistics_vals(
                invoices_group.get(partner.id, []),
                lambda r: r.invoice_date,
                lambda r: r.amount_total,
            )
            if inv_stats:
                partner._update_invoice_fields(inv_stats)
            else:
                partner._reset_invoice_fields()

        not_customers = self - customer_partners
        not_customers._reset_sales_fields()
        not_customers._reset_invoice_fields()
