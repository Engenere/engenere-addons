Adds the GUT priority matrix (Gravity, Urgency, Tendency) to OCA helpdesk
tickets so teams can classify and sort work by objective criteria instead of
gut feel.

## Problem

`helpdesk.ticket` exposes a single `priority` field (low/normal/high/urgent),
which is subjective and does not capture *why* a ticket deserves its priority.
Teams that need a structured triage methodology — e.g. support desks with
heterogeneous SLAs — lack a way to record the three dimensions classical GUT
uses to justify a priority score.

## Solution

Extend `helpdesk.ticket` with three independent Selection 1–5 fields
(Gravity, Urgency, Tendency) using the classical Meireles labels. A stored
computed `gut_score` field multiplies the three (1–125) when all are set.
A stored computed `gut_band` maps the score to five bands
(Unclassified / Low / Medium / High / Critical) following the canonical
Brazilian GUT bands (1–15 / 16–45 / 46–99 / 100–125), used for filters,
groupby and kanban/tree visual cues.

All three dimension fields are optional. **A ticket is considered
`unclassified` whenever any of Gravity, Urgency or Tendency is empty** —
partial fills are treated the same as no fill, so the score never reflects
an incomplete evaluation.

The native `priority` field is left untouched; GUT is an independent
classification that lives alongside it. The tickets action is adjusted to
open the kanban view first while preserving the existing pivot view
available in the menu.
