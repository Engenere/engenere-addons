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
    has_open_quotation = fields.Boolean(
        string="Open Quotation Exists",
        compute="_compute_open_quotation_info",
        help="Indicates if there are any draft/sent quotations for this customer",
    )
    last_open_quotation_id = fields.Many2one(
        "sale.order",
        string="Last Open Quotation",
        compute="_compute_open_quotation_info",
        help="Reference to the most recent open quotation",
    )
    last_open_quotation_date = fields.Datetime(
        string="Last Quotation Date",
        related="last_open_quotation_id.date_order",
        store=False,
        help="Date of the most recent draft/sent quotation",
    )

    def _compute_open_quotation_info(self):
        """Calcula cotações em aberto com referência direta"""
        self.update({"has_open_quotation": False, "last_open_quotation_id": False})
        customer_partners = self.filtered(lambda p: p.customer_rank > 0)
        if not customer_partners:
            return

        # Busca todas as cotações abertas ordenadas por data
        open_quotations = self.env["sale.order"].search(
            [
                ("partner_id", "in", customer_partners.ids),
                ("state", "in", ["draft", "sent"]),
            ],
            order="date_order DESC, id DESC",
        )

        # Mapeia última cotação por partner
        partner_quotations = {}
        for quot in open_quotations:
            if quot.partner_id.id not in partner_quotations:
                partner_quotations[quot.partner_id.id] = quot.id

        # Atribui valores
        for partner in customer_partners:
            if partner.id in partner_quotations:
                partner.update(
                    {
                        "has_open_quotation": True,
                        "last_open_quotation_id": partner_quotations[partner.id],
                    }
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

    def _get_analysis_months(self):
        """Retorna o número de meses configurados para análise."""
        config_param = self.env["ir.config_parameter"].sudo()
        return int(
            config_param.get_param(
                "engenere_partner_sales_info.default_analysis_months", 24
            )
        )

    def _get_start_date(self, analysis_months):
        """Calcula a data de início com base nos meses de análise."""
        return fields.Date.context_today(self) - relativedelta(months=analysis_months)

    def _group_records_by_partner(self, records):
        """Agrupa registros por partner_id."""
        grouped = defaultdict(list)
        for record in records:
            grouped[record.partner_id.id].append(record)
        return grouped

    def _compute_record_stats(self, records, date_extractor, amount_extractor):
        """Calcula estatísticas comuns para uma lista de registros."""
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
        return {
            "last_record": sorted_records[-1],
            "last_date": dates[-1] if dates else None,
            "count": count,
            "total": total,
            "average": average,
            "avg_no_outliers": avg_no_outliers,
            "avg_time_between": avg_time_between,
            "days_since_last": (today - dates[-1]).days if dates else 0,
        }

    def _update_sales_fields(self, stats):
        """Atualiza campos de vendas com base nas estatísticas."""
        self.update(
            {
                "last_order_id": stats["last_record"].id if stats else False,
                "last_order_date": stats["last_date"],
                "last_order_status": stats["last_record"].state if stats else False,
                "order_count": stats["count"] or 0,
                "total_ordered": stats["total"] or 0,
                "average_ordered": stats["average"] or 0,
                "average_ordered_no_discrepancies": stats["avg_no_outliers"] or 0,
                "average_time_between_orders": stats["avg_time_between"] or 0,
                "days_since_last_order": stats["days_since_last"] or 0,
            }
        )

    def _update_invoice_fields(self, stats):
        """Atualiza campos de faturas com base nas estatísticas."""
        self.update(
            {
                "last_invoice_id": stats["last_record"].id if stats else False,
                "last_invoice_date": stats["last_date"],
                "invoice_count": stats["count"] or 0,
                "total_invoiced": stats["total"] or 0,
                "average_invoiced": stats["average"] or 0,
                "average_invoiced_no_discrepancies": stats["avg_no_outliers"] or 0,
                "average_time_between_invoices": stats["avg_time_between"] or 0,
                "days_since_last_invoice": stats["days_since_last"] or 0,
            }
        )

    def _reset_sales_fields(self):
        """Reseta campos relacionados a vendas."""
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
        """Reseta campos relacionados a faturas."""
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

    def _compute_sales_info(self):
        """Calcula principais métricas de vendas e faturas."""
        analysis_months = self._get_analysis_months()
        start_date = self._get_start_date(analysis_months)
        customer_partners = self.filtered(lambda p: p.customer_rank > 0)

        # Processar pedidos de venda
        sale_orders = self.env["sale.order"].search(
            [
                ("partner_id", "in", customer_partners.ids),
                ("state", "in", ["sale", "done"]),
                ("date_order", ">=", start_date),
            ]
        )
        sales_group = self._group_records_by_partner(sale_orders)

        # Processar faturas
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
            # Processar vendas
            so_stats = self._compute_record_stats(
                sales_group.get(partner.id, []),
                lambda r: r.date_order.date(),
                lambda r: r.amount_total,
            )
            if so_stats:
                partner._update_sales_fields(so_stats)
            else:
                partner._reset_sales_fields()

            # Processar faturas
            inv_stats = self._compute_record_stats(
                invoices_group.get(partner.id, []),
                lambda r: r.invoice_date,
                lambda r: r.amount_total,
            )
            if inv_stats:
                partner._update_invoice_fields(inv_stats)
            else:
                partner._reset_invoice_fields()

        # Resetar parceiros que não são clientes
        (self - customer_partners).write(
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
