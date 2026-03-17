# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ConsortiumQuota(models.Model):
    _name = "consortium.quota"
    _description = "Consortium Quota"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        compute="_compute_name",
        store=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("active", "Active"),
            ("contemplated", "Contemplated"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.currency_id",
    )
    administrator_id = fields.Many2one(
        comodel_name="res.partner",
        required=True,
        tracking=True,
    )
    group_number = fields.Char(required=True)
    quota_number = fields.Char(required=True)
    proposal_number = fields.Char()
    credit_value = fields.Monetary(string="Original Credit")
    current_credit_value = fields.Monetary()
    released_credit_value = fields.Monetary()
    total_installments = fields.Integer(required=True)
    admin_fee_rate = fields.Float(digits=(5, 4))
    reserve_fund_rate = fields.Float(digits=(5, 4))
    life_insurance_rate = fields.Float(digits=(5, 4))
    start_date = fields.Date()
    contemplation_date = fields.Date(tracking=True)
    contemplation_type = fields.Selection(
        selection=[
            ("bid", "Bid"),
            ("draw", "Draw"),
            ("other", "Other"),
        ],
    )
    asset_description = fields.Char()
    product_id = fields.Many2one(comodel_name="product.product")
    readjustment_type = fields.Selection(
        selection=[
            ("asset_value", "Asset Value"),
            ("index", "Index"),
            ("manual", "Manual"),
        ],
        default="manual",
    )
    notes = fields.Html()
    installment_ids = fields.One2many(
        comodel_name="consortium.installment",
        inverse_name="quota_id",
    )
    readjustment_ids = fields.One2many(
        comodel_name="consortium.readjustment",
        inverse_name="quota_id",
    )
    component_config_ids = fields.One2many(
        comodel_name="consortium.quota.component",
        inverse_name="quota_id",
    )

    # Dashboard computed fields
    paid_installments_count = fields.Integer(
        compute="_compute_dashboard_fields",
        store=True,
    )
    remaining_installments_count = fields.Integer(
        compute="_compute_dashboard_fields",
        store=True,
    )
    total_paid = fields.Monetary(
        compute="_compute_dashboard_fields",
        store=True,
    )
    outstanding_balance = fields.Monetary(
        compute="_compute_dashboard_fields",
        store=True,
    )
    next_due_date = fields.Date(
        compute="_compute_dashboard_fields",
        store=True,
    )
    progress_percentage = fields.Float(
        compute="_compute_dashboard_fields",
        store=True,
    )

    _sql_constraints = [
        (
            "group_quota_admin_company_uniq",
            "UNIQUE(company_id, group_number, quota_number, administrator_id)",
            "Group and quota must be unique per administrator and company.",
        ),
    ]

    @api.depends("administrator_id", "group_number", "quota_number")
    def _compute_name(self):
        for quota in self:
            admin_name = quota.administrator_id.name if quota.administrator_id else ""
            quota.name = (
                f"{admin_name} - "
                f"G:{quota.group_number or ''} "
                f"Q:{quota.quota_number or ''}"
            )

    @api.depends(
        "installment_ids.state",
        "installment_ids.total_amount",
        "installment_ids.due_date",
        "total_installments",
    )
    def _compute_dashboard_fields(self):
        for quota in self:
            paid = quota.installment_ids.filtered(lambda inst: inst.state == "paid")
            unpaid = quota.installment_ids.filtered(
                lambda inst: inst.state in ("draft", "open")
            )
            quota.paid_installments_count = len(paid)
            quota.remaining_installments_count = len(unpaid)
            quota.total_paid = sum(paid.mapped("total_amount"))
            quota.outstanding_balance = sum(unpaid.mapped("total_amount"))
            unpaid_dates = unpaid.filtered("due_date").mapped("due_date")
            quota.next_due_date = min(unpaid_dates) if unpaid_dates else False
            if quota.total_installments:
                quota.progress_percentage = len(paid) / quota.total_installments * 100
            else:
                quota.progress_percentage = 0.0

    def action_activate(self):
        self.write({"state": "active"})

    def action_contemplate(self):
        self.write({"state": "contemplated"})

    def action_complete(self):
        self.write({"state": "completed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_draft(self):
        self.write({"state": "draft"})
