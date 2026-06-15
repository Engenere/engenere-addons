# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user


class TestSolutionPlan(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Plan = cls.env["helpdesk.ticket.solution.plan"]
        cls.ticket = cls.env["helpdesk.ticket"].create(
            {"name": "T1", "description": "<p>problem</p>"}
        )
        cls.member = new_test_user(
            cls.env,
            login="plan_member",
            groups="base.group_user,helpdesk_mgmt.group_helpdesk_user,"
            "eng_helpdesk_mgmt_solution_plan.group_helpdesk_solution_plan",
        )
        cls.outsider = new_test_user(
            cls.env,
            login="plan_outsider",
            groups="base.group_user,helpdesk_mgmt.group_helpdesk_user",
        )

    def test_member_can_crud(self):
        plan = self.Plan.with_user(self.member).create(
            {"ticket_id": self.ticket.id, "content": "<p>fix it</p>"}
        )
        self.assertIn("fix it", plan.content)
        plan.write({"content": "<p>updated</p>"})
        self.assertIn("updated", plan.content)

    def test_member_sees_plan_on_ticket(self):
        self.Plan.create({"ticket_id": self.ticket.id})
        ticket = self.ticket.with_user(self.member)
        self.assertEqual(len(ticket.solution_plan_ids), 1)

    def test_default_content_has_sections(self):
        plan = self.Plan.create({"ticket_id": self.ticket.id})
        self.assertIn("<h3>", plan.content)

    def test_outsider_cannot_read(self):
        plan = self.Plan.create(
            {"ticket_id": self.ticket.id, "content": "<p>secret</p>"}
        )
        with self.assertRaises(AccessError):
            self.Plan.with_user(self.outsider).browse(plan.id).read(["content"])

    def test_outsider_cannot_search(self):
        self.Plan.create({"ticket_id": self.ticket.id})
        with self.assertRaises(AccessError):
            self.Plan.with_user(self.outsider).search([])

    def test_outsider_cannot_read_group(self):
        self.Plan.create({"ticket_id": self.ticket.id})
        with self.assertRaises(AccessError):
            self.Plan.with_user(self.outsider).read_group(
                [], ["ticket_id"], ["ticket_id"]
            )

    def test_outsider_cannot_create(self):
        with self.assertRaises(AccessError):
            self.Plan.with_user(self.outsider).create(
                {"ticket_id": self.ticket.id, "content": "<p>x</p>"}
            )

    def test_outsider_cannot_write(self):
        plan = self.Plan.create({"ticket_id": self.ticket.id})
        with self.assertRaises(AccessError):
            plan.with_user(self.outsider).write({"content": "<p>x</p>"})

    def test_outsider_cannot_unlink(self):
        plan = self.Plan.create({"ticket_id": self.ticket.id})
        with self.assertRaises(AccessError):
            plan.with_user(self.outsider).unlink()

    def test_company_id_follows_ticket(self):
        plan = self.Plan.create({"ticket_id": self.ticket.id})
        self.assertEqual(plan.company_id, self.ticket.company_id)

    def test_multicompany_rule_is_global(self):
        # The cross-company isolation is enforced by a global ir.rule (same
        # pattern as helpdesk_mgmt's own company rule). Assert it is installed,
        # global (no groups) and scoped by company_id.
        rule = self.env.ref(
            "eng_helpdesk_mgmt_solution_plan.solution_plan_company_rule"
        )
        self.assertFalse(rule.groups)
        self.assertIn("company_id", rule.domain_force)
