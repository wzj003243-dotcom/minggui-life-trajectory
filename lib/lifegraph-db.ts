import "server-only";

import type { Database } from "./database.types";

export type LifeGraphDatasetStatus =
  Database["public"]["Views"]["lifegraph_dataset_status_v1"]["Row"];
export type LifeGraphPerson =
  Database["public"]["Views"]["lifegraph_people_v1"]["Row"];
export type LifeGraphEvent =
  Database["public"]["Views"]["lifegraph_events_v1"]["Row"];
export type LifeGraphModelInput =
  Database["public"]["Views"]["lifegraph_model_inputs_v1"]["Row"];
export type LifeGraphYearState =
  Database["public"]["Views"]["lifegraph_year_states_v1"]["Row"];
export type LifeGraphObservationProfile =
  Database["public"]["Views"]["lifegraph_observation_profiles_v1"]["Row"];
export type LifeGraphModelEligibility =
  Database["public"]["Views"]["lifegraph_model_eligibility_v1"]["Row"];
export type LifeGraphTrainingExample =
  Database["public"]["Views"]["lifegraph_training_examples_v1"]["Row"];
export type LifeGraphTrainingSplit =
  Database["public"]["Views"]["lifegraph_training_splits_v1"]["Row"];
export type LifeGraphTrainingReadiness =
  Database["public"]["Views"]["lifegraph_training_readiness_v1"]["Row"];

function getConfig() {
  const url =
    process.env.SUPABASE_URL ??
    process.env.NEXT_PUBLIC_SUPABASE_URL ??
    "https://nyafyhtwwxezzvbvtykv.supabase.co";
  const key = process.env.SUPABASE_SECRET_KEY;

  if (!key) return null;
  return { url: url.replace(/\/$/, ""), key };
}

async function supabaseRest<T>(path: string): Promise<T | null> {
  const config = getConfig();
  if (!config) return null;

  const headers: Record<string, string> = {
    apikey: config.key,
    Accept: "application/json",
  };

  // Legacy service-role keys are JWTs and historically use Authorization too.
  // New sb_secret_* keys must be sent only as apikey.
  if (!config.key.startsWith("sb_secret_")) {
    headers.Authorization = `Bearer ${config.key}`;
  }

  const response = await fetch(`${config.url}/rest/v1/${path}`, {
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(
      `LifeGraph database request failed (${response.status}): ${detail.slice(0, 500)}`,
    );
  }

  return (await response.json()) as T;
}

function eq(value: string) {
  return encodeURIComponent(`eq.${value}`);
}

export async function getLifeGraphDatasetStatus() {
  const rows = await supabaseRest<LifeGraphDatasetStatus[]>(
    "lifegraph_dataset_status_v1?select=*&order=created_at.desc&limit=1",
  );
  return rows?.[0] ?? null;
}

export async function getLifeGraphPersonByWikidataId(wikidataId: string) {
  const rows = await supabaseRest<LifeGraphPerson[]>(
    `lifegraph_people_v1?select=*&wikidata_id=${eq(wikidataId)}&limit=1`,
  );
  return rows?.[0] ?? null;
}

export async function getLifeGraphModelInput(wikidataId: string) {
  const rows = await supabaseRest<LifeGraphModelInput[]>(
    `lifegraph_model_inputs_v1?select=*&wikidata_id=${eq(wikidataId)}&limit=1`,
  );
  return rows?.[0] ?? null;
}

export async function getLifeGraphEvents(
  wikidataId: string,
  options: { includeExcluded?: boolean; limit?: number } = {},
) {
  const limit = Math.min(Math.max(options.limit ?? 500, 1), 2000);
  const eligible = options.includeExcluded ? "" : "&model_eligible=eq.true";
  return (
    (await supabaseRest<LifeGraphEvent[]>(
      `lifegraph_events_v1?select=*&wikidata_id=${eq(wikidataId)}${eligible}&order=event_date_min.asc.nullslast&limit=${limit}`,
    )) ?? []
  );
}

export async function getLifeGraphYearStates(
  wikidataId: string,
  fromYear?: number,
  toYear?: number,
) {
  const range = [
    fromYear == null ? "" : `&year=gte.${Math.trunc(fromYear)}`,
    toYear == null ? "" : `&year=lte.${Math.trunc(toYear)}`,
  ].join("");

  return (
    (await supabaseRest<LifeGraphYearState[]>(
      `lifegraph_year_states_v1?select=*&wikidata_id=${eq(wikidataId)}${range}&order=year.asc`,
    )) ?? []
  );
}


export async function getLifeGraphObservationProfile(wikidataId: string) {
  const rows = await supabaseRest<LifeGraphObservationProfile[]>(
    `lifegraph_observation_profiles_v1?select=*&wikidata_id=${eq(wikidataId)}&limit=1`,
  );
  return rows?.[0] ?? null;
}

export async function getLifeGraphModelEligibility(wikidataId: string) {
  const rows = await supabaseRest<LifeGraphModelEligibility[]>(
    `lifegraph_model_eligibility_v1?select=*&wikidata_id=${eq(wikidataId)}&limit=1`,
  );
  return rows?.[0] ?? null;
}


export async function getLifeGraphTrainingReadiness(datasetVersion?: string) {
  const version = datasetVersion ? `&version=${eq(datasetVersion)}` : "";
  return (
    (await supabaseRest<LifeGraphTrainingReadiness[]>(
      `lifegraph_training_readiness_v1?select=*${version}&order=version.desc`,
    )) ?? []
  );
}

export async function getLifeGraphTrainingExamples(
  datasetVersion: string,
  options: {
    split?: string;
    classificationEligibleOnly?: boolean;
    limit?: number;
  } = {},
) {
  const limit = Math.min(Math.max(options.limit ?? 1000, 1), 5000);
  const split = options.split ? `&person_hash_split=${eq(options.split)}` : "";
  const rows =
    (await supabaseRest<LifeGraphTrainingExample[]>(
      `lifegraph_training_examples_v1?select=*&dataset_version=${eq(datasetVersion)}${split}&order=wikidata_id.asc,cutoff_age.asc&limit=${limit}`,
    )) ?? [];

  if (!options.classificationEligibleOnly) return rows;
  return rows.filter((row) => {
    const flags = row.eligibility_flags;
    return (
      flags &&
      typeof flags === "object" &&
      !Array.isArray(flags) &&
      flags.classification_eligible === true
    );
  });
}

export async function getLifeGraphTrainingSplits(
  datasetVersion: string,
  scenarioKey: string,
) {
  return (
    (await supabaseRest<LifeGraphTrainingSplit[]>(
      `lifegraph_training_splits_v1?select=*&dataset_version=${eq(datasetVersion)}&scenario_key=${eq(scenarioKey)}&order=wikidata_id.asc`,
    )) ?? []
  );
}
