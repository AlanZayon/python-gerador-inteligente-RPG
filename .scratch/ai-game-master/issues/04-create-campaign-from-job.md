# 04: Create Campaign from Job

**What to build:** From a successful Job, the host explicitly creates a Campaign. That copies the Campaign Blueprint, book identity, and Character roster from sheets. The Vue result page exposes a Create Campaign CTA; the host can open/view the new Campaign.

**Blocked by:** 03 — Persist Campaign Blueprint seed on Job success

**Status:** resolved

- [x] Host can create a Campaign only from a Job they own that has a Blueprint seed
- [x] Campaign stores Blueprint copy, book identity, and claimable Character roster
- [x] Creating a Campaign does not start a GameSession by itself
- [x] Result UI offers Create Campaign and links to the Campaign view
- [x] Play Application boundary tests cover create + authorization failures
