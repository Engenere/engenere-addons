- The **Keep Suspense Accounts** reconcile mode needs its own tests before
  it is supported.
- Two simultaneous attempts on the same group, from two sessions, cannot be
  tested in the CI, where no two transactions see the test data: the lock
  and the retry of the transaction are covered there, the concurrent case
  must be checked on a test database.
