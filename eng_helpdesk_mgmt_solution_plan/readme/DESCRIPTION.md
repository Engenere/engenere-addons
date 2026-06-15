Adds an **internal solution plan** to helpdesk tickets: a rich-text field where
developers/responsible people document the **origin/root cause**, the **real
problem**, **what will be done** and **how to verify** — the technical plan that
used to live in a throwaway local file, now saved on the ticket itself.

The plan is stored in a dedicated model (`helpdesk.ticket.solution.plan`) whose
access is restricted by ACL to the group **Helpdesk Solution Plan (internal)**.
Because the restriction is at model level, it holds against direct read, search,
`read_group` and export — not only the form view. Customers (portal) and regular
internal users that are not in the group cannot see it.

A new ticket has no plan; add one from the "Solution Plan" tab (it starts from a
template with the canonical sections).
