Install the module on any database where the sales, purchase and invoicing teams should
not be able to mutate transfers. After install:

- Users with `Sales / User`, `Sales / Administrator`, `Purchase / User`,
  `Purchase / Administrator` or the `Invoicing` role see transfers in read-only mode;
  the destructive buttons (Cancel, Scrap, Unreserve, Return) on the picking form are
  hidden for them, and they cannot add or edit picking lines.
- They can still open the related transfers through the Delivery / Receipt smart buttons
  on their own sale and purchase orders.
- Confirming and cancelling sale and purchase orders, bumping a confirmed purchase
  quantity and updating a sale order's delivery address keep working out of the box.
- Users that should keep mutating pickings need the standard `Inventory / User` or
  `Inventory / Administrator` group, as usual.
