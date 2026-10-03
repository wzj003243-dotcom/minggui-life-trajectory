# Historical split policy v1

Random train/test is not sufficient for MingGui. It allows the model to exploit historical and geographic similarity in ways that will not generalize.

## Required evaluations

### 1. Forward-era holdout
Example:
- train: people born <= 1940
- validation: 1941–1960
- test: 1961–1980

Exact years depend on target maturity. A person must have enough future horizon to observe the target.

### 2. Geography holdout
Train without one country/region group and test there. This detects whether an apparent “BaZi signal” is actually a proxy for geography, seasonality, institutions or naming/data conventions.

### 3. Notability strata
Report performance separately for high-, medium- and low-notability historical records. Biography completeness is itself a confounder.

### 4. Birth-time precision
Separate:
- full day only
- approximate time
- high-reliability timed birth

Never compare four-pillar performance against a three-pillar baseline on different people without controlling cohort composition.

### 5. Birthday placebo
Within era × geography strata, permute birthday month/day (and separately time where available), rebuild BaZi features, retrain the exact same pipeline, and repeat many times.

The result to report is not “BaZi accuracy”; it is:

`performance(real birth features) - distribution(performance(shuffled birth features))`

with confidence intervals.

## Target maturity
A 10-year target at age 30 requires biography coverage through at least age 40. Right-censored persons cannot silently become negative labels.
