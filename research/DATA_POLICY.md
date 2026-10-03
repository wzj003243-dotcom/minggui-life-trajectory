# Data & Licensing Policy

This repository should remain publishable. Data ingestion code may be open while raw third-party datasets are excluded from git.

## Preferred public backbone

### Wikidata
Use entity IDs, birth/date/place, occupations, education and other structured facts where available. Preserve source IDs and statement precision. Do not assume absence = negative.

### Pantheon / A Brief History of Human Time
Use as research cohorts / benchmarks according to their release licenses. Store dataset version and citation.

### Biography text
Store source URL, retrieval date and extraction confidence. Prefer event facts and short normalized descriptions rather than redistributing long copyrighted biography prose.

## Restricted / conditional sources

### Astro-Databank
Birth facts shown publicly can be useful for research, but bulk XML exports have a separate time-limited license. Never commit licensed exports. Carry Rodden/source reliability ratings into derived research records.

### CBDB
As of the 2026 licensing revision, the current standalone release has non-commercial share-alike terms, while data beyond that release can have stricter no-derivatives / no-public-access conditions. Do not use restricted newer records as the backing store of a public interactive service without authorization.

## Personal user data
- private by default
- encrypted in transit / at rest through the hosting stack
- strict row-level access control
- export + delete path
- no public training use without explicit opt-in
- prediction ledger can retain anonymized evaluation fields only under explicit consent
