from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestHelpdeskTicketGUT(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Ticket = cls.env["helpdesk.ticket"]
        cls.ticket = cls.Ticket.create(
            {
                "name": "GUT Test Ticket",
                "description": "desc",
            }
        )

    def test_unclassified_when_no_fields_set(self):
        self.assertEqual(self.ticket.gut_score, 0)
        self.assertEqual(self.ticket.gut_band, "unclassified")

    def test_unclassified_when_partially_filled(self):
        self.ticket.gut_gravity = "5"
        self.assertEqual(self.ticket.gut_score, 0)
        self.assertEqual(self.ticket.gut_band, "unclassified")

        self.ticket.gut_urgency = "5"
        self.assertEqual(self.ticket.gut_score, 0)
        self.assertEqual(self.ticket.gut_band, "unclassified")

    def test_score_is_product_of_the_three_values(self):
        self.ticket.write({"gut_gravity": "3", "gut_urgency": "4", "gut_tendency": "5"})
        self.assertEqual(self.ticket.gut_score, 60)

    def test_band_low_range(self):
        # 1*1*1 = 1 and 3*1*5 = 15 both map to low
        self.ticket.write({"gut_gravity": "1", "gut_urgency": "1", "gut_tendency": "1"})
        self.assertEqual(self.ticket.gut_score, 1)
        self.assertEqual(self.ticket.gut_band, "low")

        self.ticket.write({"gut_gravity": "3", "gut_urgency": "1", "gut_tendency": "5"})
        self.assertEqual(self.ticket.gut_score, 15)
        self.assertEqual(self.ticket.gut_band, "low")

    def test_band_medium_range(self):
        # 16 -> medium
        self.ticket.write({"gut_gravity": "2", "gut_urgency": "4", "gut_tendency": "2"})
        self.assertEqual(self.ticket.gut_score, 16)
        self.assertEqual(self.ticket.gut_band, "medium")
        # 45 -> still medium
        self.ticket.write({"gut_gravity": "3", "gut_urgency": "3", "gut_tendency": "5"})
        self.assertEqual(self.ticket.gut_score, 45)
        self.assertEqual(self.ticket.gut_band, "medium")

    def test_band_high_range(self):
        # 46 (no clean product) — use 48 = 2*4*6? Max is 5. Use 3*4*4=48
        self.ticket.write({"gut_gravity": "3", "gut_urgency": "4", "gut_tendency": "4"})
        self.assertEqual(self.ticket.gut_score, 48)
        self.assertEqual(self.ticket.gut_band, "high")
        # 99 not representable; 4*5*5=100 is already critical; test 4*4*5=80
        self.ticket.write({"gut_gravity": "4", "gut_urgency": "4", "gut_tendency": "5"})
        self.assertEqual(self.ticket.gut_score, 80)
        self.assertEqual(self.ticket.gut_band, "high")

    def test_band_critical_range(self):
        # 100 boundary -> critical
        self.ticket.write({"gut_gravity": "4", "gut_urgency": "5", "gut_tendency": "5"})
        self.assertEqual(self.ticket.gut_score, 100)
        self.assertEqual(self.ticket.gut_band, "critical")
        # 125 max -> critical
        self.ticket.write({"gut_gravity": "5", "gut_urgency": "5", "gut_tendency": "5"})
        self.assertEqual(self.ticket.gut_score, 125)
        self.assertEqual(self.ticket.gut_band, "critical")

    def test_clearing_one_value_returns_to_unclassified(self):
        self.ticket.write({"gut_gravity": "5", "gut_urgency": "5", "gut_tendency": "5"})
        self.assertEqual(self.ticket.gut_band, "critical")

        self.ticket.gut_tendency = False
        self.assertEqual(self.ticket.gut_score, 0)
        self.assertEqual(self.ticket.gut_band, "unclassified")

    def test_changing_values_recomputes(self):
        self.ticket.write({"gut_gravity": "1", "gut_urgency": "1", "gut_tendency": "1"})
        self.assertEqual(self.ticket.gut_band, "low")

        self.ticket.gut_gravity = "5"
        self.assertEqual(self.ticket.gut_score, 5)
        self.assertEqual(self.ticket.gut_band, "low")

        self.ticket.gut_urgency = "5"
        self.ticket.gut_tendency = "5"
        self.assertEqual(self.ticket.gut_score, 125)
        self.assertEqual(self.ticket.gut_band, "critical")

    def test_create_with_full_gut(self):
        ticket = self.Ticket.create(
            {
                "name": "GUT on create",
                "description": "desc",
                "gut_gravity": "4",
                "gut_urgency": "3",
                "gut_tendency": "2",
            }
        )
        self.assertEqual(ticket.gut_score, 24)
        self.assertEqual(ticket.gut_band, "medium")

    def test_search_by_band(self):
        # unclassified ticket from setUpClass + new critical one
        critical = self.Ticket.create(
            {
                "name": "Critical",
                "description": "desc",
                "gut_gravity": "5",
                "gut_urgency": "5",
                "gut_tendency": "5",
            }
        )
        found = self.Ticket.search([("gut_band", "=", "critical")])
        self.assertIn(critical, found)
        self.assertNotIn(self.ticket, found)

    def test_tickets_action_opens_kanban_first(self):
        action = self.env.ref("helpdesk_mgmt.helpdesk_ticket_action")
        self.assertEqual(action.view_mode, "kanban,tree,form,pivot")

    def test_inherited_views_render(self):
        # Rendering each view validates XPath inheritance and field presence.
        for view_xmlid in (
            "helpdesk_mgmt.ticket_view_form",
            "helpdesk_mgmt.ticket_view_tree",
            "helpdesk_mgmt.view_helpdesk_ticket_kanban",
            "helpdesk_mgmt.helpdesk_ticket_view_search",
        ):
            view = self.env.ref(view_xmlid)
            arch = self.Ticket.get_view(view_id=view.id, view_type=view.type)["arch"]
            self.assertIn("gut_", arch)

    def test_kanban_field_declaration_not_duplicated(self):
        # Regression: the narrow XPath must add gut_score/gut_band as top-level
        # kanban field declarations only, not inside the card template.
        view = self.env.ref("helpdesk_mgmt.view_helpdesk_ticket_kanban")
        arch = self.Ticket.get_view(view_id=view.id, view_type="kanban")["arch"]
        # Exactly one declaration of each GUT field (outside any <t> template)
        self.assertEqual(arch.count('name="gut_score"'), 1)
        self.assertEqual(arch.count('name="gut_band"'), 1)

    def test_kanban_default_order_by_gut_score(self):
        view = self.env.ref("helpdesk_mgmt.view_helpdesk_ticket_kanban")
        arch = self.Ticket.get_view(view_id=view.id, view_type="kanban")["arch"]
        self.assertIn('default_order="gut_score desc, priority desc, id desc"', arch)
