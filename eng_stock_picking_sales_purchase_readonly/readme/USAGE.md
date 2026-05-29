Install the module on any database where the sales/purchase teams should not be able to
mutate transfers from the Inventory side. After install:

- Users with `Sales / User: Own Documents Only`, `Sales / Administrator`,
  `Purchase / User` or `Purchase / Administrator` see transfers in read-only mode and
  the destructive buttons (Cancel, Scrap, Unreserve, Return) on the picking form are
  hidden for them.
- Confirming and cancelling sale and purchase orders continues to work out of the box;
  the receipts/deliveries are still created and cancelled during those flows.
- Users that should keep mutating pickings need the standard `Inventory / User` or
  `Inventory / Administrator` group, as usual.
