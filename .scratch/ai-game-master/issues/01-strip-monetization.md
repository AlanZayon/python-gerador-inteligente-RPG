# 01: Strip monetization

**What to build:** The product runs as a personal/portfolio app with no Stripe, credits, plans, pricing pages, checkout, or plan-tied quotas. Clerk auth remains. A signed-in user can generate campaigns without hitting billing gates, on both API and Vue UI.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Stripe/credits/plan/pricing/checkout surfaces are removed or unreachable in backend and Vue
- [x] Generation and account flows no longer require credits or a paid plan
- [x] Clerk sign-in still works for protected routes
- [x] Existing non-billing tests still pass; billing-only tests are removed or rewritten as free-path tests
