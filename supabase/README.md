# MingGui LifeGraph database

The production research database lives in a dedicated Supabase project:

- project ref: `nyafyhtwwxezzvbvtykv`
- region: `us-west-1`
- project name: `minggui-life-trajectory`

No API keys or database passwords belong in this repository.

## Security boundary

`research.*` contains research source data, provenance, BaZi features, and life-event timelines. Browser roles do not receive grants on this schema.

The browser-facing product tables are separate:

- `public.user_profiles`
- `public.prediction_ledger`

Both use RLS keyed to `auth.uid()`.

Server-side LifeGraph access goes through five curated `public` views. They are revoked from `anon` and `authenticated` and granted only to `service_role`:

- `lifegraph_people_v1`
- `lifegraph_events_v1`
- `lifegraph_model_inputs_v1`
- `lifegraph_year_states_v1`
- `lifegraph_dataset_status_v1`

Use `lib/lifegraph-db.ts` from Server Components, Route Handlers, workers, or research jobs. Never import it into a Client Component.

## Environment

Server:

```text
SUPABASE_URL=https://nyafyhtwwxezzvbvtykv.supabase.co
SUPABASE_SECRET_KEY=...
```

The secret key bypasses RLS. It must never use a `NEXT_PUBLIC_` prefix.

If client-side auth is later enabled, use the separate publishable variables already shown in `.env.example`.

## Current frozen core

Snapshot: `timed-core / v0.1-interim`

Imported complete sources:

- verified timed people: 3,076
- canonical birth records: 3,076
- BaZi feature sets: 3,076
- raw complete events: 14,136
  - Wikidata: 12,510
  - OpenAlex: 1,626
- external identity rows: 6,961

Quality-gated trajectory state:

- model-eligible events: 14,023
- posthumous rows retained but excluded: 109
- impossible pre-birth intervals retained but excluded: 4
- coarse birth-overlap intervals corrected for model-facing age: 7
- annual cutoff-safe states: 39,065 across 1,610 people

MusicBrainz events from the timed-core workflow were incomplete when the job hit its time limit and were deliberately **not imported**. The MusicBrainz identity bridge is retained so the complete addon can be attached later.

## Temporal policy

`observable_from` is the earliest safe information cutoff for modeling. For coarse dates, it is the **latest possible date** in the source precision interval. Annual state rows only use events whose `observable_from` is on or before that year-end.

Posthumous events remain historical facts but have `model_eligible=false`. Events whose source interval overlaps the person's birth date keep their original values in `quality_flags`, while the model-facing age interval is clipped to age zero.

## Thickness

`research.person_thickness_v1` computes per-person coverage using model-eligible events.

The strict current research-ready rule is:

- at least 15 events
- at least 4 domains
- at least 3 life stages
- at least 2 independent source families

This is intentionally strict. Biography and complete MusicBrainz enrichment are expected to improve source diversity and domain breadth.

## Versioning

Every frozen import is registered in:

- `research.dataset_snapshots`
- `research.import_batches`
- `research.dataset_membership`

Every model feature snapshot should point to a dataset snapshot and information cutoff. Do not overwrite a frozen snapshot to make a later experiment look better.


## Preservation policy

Sparse public records are **not** treated as low-quality people and are never deleted merely for being sparse.

Every source-backed person remains in `research.people`, including people with zero currently usable life events. Every source-backed event remains in `research.life_events`; quality flags determine whether an event is suitable for a particular modeling task, not whether the historical fact is kept.

Two server-only views make this explicit:

- `lifegraph_observation_profiles_v1`: describes documentation density, temporal precision, life-stage coverage, domain coverage, and source coverage.
- `lifegraph_model_eligibility_v1`: task-specific eligibility flags such as next-event, sequence, hazard, multi-source validation, and strict dense benchmark.

Current documentation-density distribution:

- none: 1,451
- sparse (1–4 events): 869
- light (5–14): 497
- moderate (15–39): 230
- dense (40+): 29

These labels describe the **record**, not the person.

Current task-specific usable counts:

- any trajectory task: 1,610
- next-event task: 1,147
- sequence task: 961
- hazard task: 723
- multi-source validation: 10
- strict dense benchmark: 4

A person can therefore be valuable for one analysis and unusable for another without being dropped from the database.
