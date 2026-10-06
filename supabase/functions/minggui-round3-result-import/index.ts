
import postgres from "npm:postgres@3.4.5";
import JSZip from "npm:jszip@3.10.1";
import Papa from "npm:papaparse@5.4.1";

const DATASET="8261f970-adc3-4f9a-8043-9e0f6cb90be8";
const PROTOCOL_KEY="next-canonical-domain-generalization-round3-v1";
const WORKFLOW_RUN="37422079918";
const CODE_COMMIT="0e69db62e780b7aaa12dde66509eb13feede7cd5";
const SEED=20261006;

const APPROVED={
  "77bcb94394f0ae45fb1385dd20bdef30c004a3ed231f466dd4235d1e45eb5da8":{
    artifactId:"11393777604",scenario:"forward_era_v1"
  },
  "4a8edee6979b119ac404479029fa95d9cf7fc2a04026ec9dabbdac799761987d":{
    artifactId:"11393857279",scenario:"geo_us_holdout_v1"
  },
  "0b2932d341c169f5eecec3102d69820b0d9f828530dfbec9353851268ccc4061":{
    artifactId:"11393842460",scenario:"geo_france_holdout_v1"
  }
};

const VARIANTS=[
  "history_reality_v1",
  "raw_birth_calendar_v1",
  "bazi_objective_only_v1",
  "history_plus_bazi_v1",
  "bazi_decade_shuffle_placebo_v1"
];

const hex=(buf)=>Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,"0")).join("");

async function serverSecret(){
  const legacy=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const secretJson=Deno.env.get("SUPABASE_SECRET_KEYS");
  let secret=legacy;
  if(secretJson){try{secret=JSON.parse(secretJson)?.default||secret;}catch{}}
  return secret;
}

async function gunzip(bytes){
  const ds=new DecompressionStream("gzip");
  const stream=new Blob([bytes]).stream().pipeThrough(ds);
  return await new Response(stream).text();
}

function parseCsv(text){
  const out=Papa.parse(text,{header:true,skipEmptyLines:true,dynamicTyping:true});
  if(out.errors && out.errors.length) throw new Error("CSV parse error: "+JSON.stringify(out.errors.slice(0,3)));
  return out.data;
}

function runKey(scenario,variant){
  return "final-v1-r3-"+scenario+"-hgb-"+variant;
}

Deno.serve(async(req)=>{
  if(req.method!=="POST") return new Response("POST only",{status:405});
  const db=Deno.env.get("SUPABASE_DB_URL");
  const url=Deno.env.get("SUPABASE_URL");
  const secret=await serverSecret();
  if(!db||!url||!secret) return new Response("missing server credentials",{status:500});
  const sql=postgres(db,{prepare:false,max:1});
  const q=(text,params=[])=>sql.unsafe(text,params);

  try{
    const bytes=new Uint8Array(await req.arrayBuffer());
    const sha=hex(await crypto.subtle.digest("SHA-256",bytes));
    const approved=APPROVED[sha];
    if(!approved) throw new Error("unapproved artifact sha "+sha);

    const zip=await JSZip.loadAsync(bytes);
    const prefix="round3-results/"+approved.scenario+"/";
    async function bytesOf(rel){
      const f=zip.file(prefix+rel); if(!f) throw new Error("missing "+prefix+rel);
      return new Uint8Array(await f.async("uint8array"));
    }
    async function textOf(rel){ return new TextDecoder().decode(await bytesOf(rel)); }

    const summary=JSON.parse(await textOf("round3_summary.json"));
    const checksums=JSON.parse(await textOf("SHA256SUMS.json"));
    if(summary.dataset_id!==DATASET) throw new Error("dataset mismatch");
    if(summary.protocol_key!==PROTOCOL_KEY) throw new Error("protocol mismatch");
    if(summary.scenario!==approved.scenario) throw new Error("scenario mismatch");
    if(summary.dataset_fingerprint!=="a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888") throw new Error("dataset fingerprint mismatch");
    if(summary.placebo_mapping_fingerprint!=="3010d4188445645271ca771980f8947d20f96362f96f6b286e256610887cdd0e") throw new Error("placebo fingerprint mismatch");
    if(summary.no_hyperparameter_selection!==true) throw new Error("Round3 must have no hyperparameter selection");
    if(summary.frozen_config?.key!=="hgb_small") throw new Error("unexpected frozen config");

    const bundlePath="model-runs/final-v1-round3/"+approved.scenario+"/"+sha+"/bundle.zip";
    const res=await fetch(url+"/storage/v1/object/research-artifacts/"+bundlePath,{
      method:"POST",
      headers:{
        "Authorization":"Bearer "+secret,
        "apikey":secret,
        "Content-Type":"application/zip",
        "x-upsert":"true"
      },
      body:bytes
    });
    const body=await res.text();
    if(!res.ok) throw new Error("storage upload failed "+res.status+": "+body);

    await q(
      "insert into research.artifact_registry(artifact_key,provider,provider_artifact_id,artifact_name,artifact_kind,sha256,size_bytes,source_workflow_run_id,source_git_sha,storage_bucket,storage_path,status,metadata,archived_at,imported_at) "+
      "values($1,'github-actions',$2,$3,'model-benchmark-round3',$4,$5,$6,$7,'research-artifacts',$8,'archived',$9::jsonb,now(),now()) "+
      "on conflict(artifact_key) do update set storage_bucket=excluded.storage_bucket,storage_path=excluded.storage_path,size_bytes=excluded.size_bytes,status='archived',metadata=excluded.metadata,archived_at=coalesce(research.artifact_registry.archived_at,now()),imported_at=now()",
      [
        "github-actions:"+approved.artifactId+":"+sha,
        approved.artifactId,
        "minggui-final-v1-round3-"+approved.scenario,
        sha,bytes.length,WORKFLOW_RUN,CODE_COMMIT,bundlePath,
        JSON.stringify({dataset_id:DATASET,protocol_key:PROTOCOL_KEY,scenario:approved.scenario,round:"final-v1-round3",frozen_config:summary.frozen_config})
      ]
    );

    const runIds={};
    for(const variant of VARIANTS){
      const key=runKey(approved.scenario,variant);
      const config={
        benchmark_round:"final-v1-round3",
        protocol_key:PROTOCOL_KEY,
        target:"target_class_4",
        split_scenario:approved.scenario,
        dataset_fingerprint:summary.dataset_fingerprint,
        placebo_mapping_fingerprint:summary.placebo_mapping_fingerprint,
        model_family:"hist_gradient_boosting",
        feature_variant:variant,
        seed:SEED,
        frozen_config:summary.frozen_config,
        no_hyperparameter_selection:true,
        sample_weight:"balanced_from_scenario_train_only"
      };
      const rows=await q(
        "insert into research.model_runs(training_dataset_id,run_key,model_family,feature_variant,split_scenario_key,code_commit,random_seed,config,environment,status,notes,started_at,finished_at) "+
        "values($1::uuid,$2,'hist_gradient_boosting',$3,$4,$5,$6,$7::jsonb,$8::jsonb,'completed',$9,$10::timestamptz,$11::timestamptz) "+
        "on conflict(run_key) do update set config=excluded.config,environment=excluded.environment,status='completed',code_commit=excluded.code_commit,random_seed=excluded.random_seed,notes=excluded.notes,started_at=excluded.started_at,finished_at=excluded.finished_at returning id",
        [
          DATASET,key,variant,approved.scenario,CODE_COMMIT,SEED,
          JSON.stringify(config),JSON.stringify(summary.environment),
          "Final v1 Round 3 preregistered distribution-shift holdout. Frozen Round2 hgb_small; no Round3 hyperparameter selection.",
          "2026-10-06T06:08:45Z","2026-10-06T06:19:08Z"
        ]
      );
      runIds[variant]=String(rows[0].id);
    }

    const metrics=parseCsv(await textOf("metrics.csv"));
    for(const row of metrics){
      const rid=runIds[row.feature_variant];
      const details=JSON.parse(row.details||"{}");
      for(const key of ["n","accuracy","balanced_accuracy","macro_f1","log_loss","brier_multiclass","ece_10bin"]){
        await q(
          "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) values($1::uuid,$2,$3,$4,$5::jsonb) "+
          "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value,details=excluded.details",
          [rid,row.split_name,key,Number(row[key]),JSON.stringify(key==="n"?{}:details)]
        );
      }
    }

    const rawMetrics=parseCsv(await textOf("raw_domain_metrics.csv"));
    for(const row of rawMetrics){
      await q(
        "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) values($1::uuid,$2,'raw_domain_macro_f1',$3,$4::jsonb) "+
        "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value,details=excluded.details",
        [
          runIds[row.feature_variant],row.split_name,Number(row.macro_f1),
          JSON.stringify({n:Number(row.n),support:JSON.parse(row.support||"{}"),train_classes:JSON.parse(row.train_classes||"[]")})
        ]
      );
    }

    const cmp=summary.paired_cluster_bootstrap;
    const comparisons=[
      ["history_plus_bazi_minus_history","history_plus_bazi_v1","delta_macro_f1_vs_history_reality"],
      ["bazi_minus_raw_calendar","bazi_objective_only_v1","delta_macro_f1_vs_raw_birth_calendar"],
      ["bazi_minus_placebo","bazi_objective_only_v1","delta_macro_f1_vs_placebo"]
    ];
    for(const item of comparisons){
      const d=cmp[item[0]];
      await q(
        "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) values($1::uuid,'test',$2,$3,$4::jsonb) "+
        "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value,details=excluded.details",
        [runIds[item[1]],item[2],Number(d.delta_macro_f1),JSON.stringify(d)]
      );
    }

    const predictions=parseCsv(await gunzip(await bytesOf("predictions.csv.gz")));
    const batchSize=400;
    for(let start=0;start<predictions.length;start+=batchSize){
      const batch=predictions.slice(start,start+batchSize);
      const params=[]; const values=[]; let n=1;
      for(const r of batch){
        const rid=runIds[r.feature_variant];
        values.push("($"+(n++)+"::uuid,$"+(n++)+"::bigint,$"+(n++)+",$"+(n++)+",$"+(n++)+",$"+(n++)+"::jsonb,$"+(n++)+"::jsonb)");
        params.push(
          rid,Number(r.training_example_id),r.split_name,r.y_true,r.y_pred,
          JSON.stringify({career:Number(r.p_career),other:Number(r.p_other),recognition:Number(r.p_recognition),relationship:Number(r.p_relationship)}),
          JSON.stringify({round:"final-v1-round3",scenario:approved.scenario,person_id:Number(r.person_id),frozen_config:"hgb_small"})
        );
      }
      await q(
        "insert into research.model_predictions(run_id,training_example_id,split_name,y_true,y_pred,probabilities,metadata) values "+values.join(",")+
        " on conflict(run_id,training_example_id) do update set split_name=excluded.split_name,y_true=excluded.y_true,y_pred=excluded.y_pred,probabilities=excluded.probabilities,metadata=excluded.metadata",
        params
      );
    }

    for(const variant of VARIANTS){
      const rid=runIds[variant];
      const modelRel="models/"+variant+".joblib";
      const artifacts=[
        ["benchmark_bundle_zip","storage://research-artifacts/"+bundlePath,sha,{github_artifact_id:approved.artifactId,workflow_run_id:WORKFLOW_RUN,scenario:approved.scenario}],
        ["round3_summary_json","storage://research-artifacts/"+bundlePath+"#"+prefix+"round3_summary.json",checksums["round3_summary.json"],{scenario:approved.scenario}],
        ["model_joblib","storage://research-artifacts/"+bundlePath+"#"+prefix+modelRel,checksums[modelRel],{feature_variant:variant,scenario:approved.scenario,frozen_config:summary.frozen_config}]
      ];
      for(const a of artifacts){
        await q(
          "insert into research.model_artifacts(run_id,artifact_type,uri,sha256,metadata) values($1::uuid,$2,$3,$4,$5::jsonb) "+
          "on conflict(run_id,artifact_type,sha256) do update set uri=excluded.uri,metadata=excluded.metadata",
          [rid,a[0],a[1],a[2],JSON.stringify(a[3])]
        );
      }
    }

    await q("with r as (select id from research.model_runs where run_key like 'final-v1-r3-'+$1+'-hgb-%') update research.model_runs set config=(config #>> '{}')::jsonb where id in (select id from r) and jsonb_typeof(config)='string'",[approved.scenario]);
    await q("with r as (select id from research.model_runs where run_key like 'final-v1-r3-'+$1+'-hgb-%') update research.model_runs set environment=(environment #>> '{}')::jsonb where id in (select id from r) and jsonb_typeof(environment)='string'",[approved.scenario]);
    await q("with r as (select id from research.model_runs where run_key like 'final-v1-r3-'+$1+'-hgb-%') update research.model_metrics set details=(details #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(details)='string'",[approved.scenario]);
    await q("with r as (select id from research.model_runs where run_key like 'final-v1-r3-'+$1+'-hgb-%') update research.model_predictions set probabilities=(probabilities #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(probabilities)='string'",[approved.scenario]);
    await q("with r as (select id from research.model_runs where run_key like 'final-v1-r3-'+$1+'-hgb-%') update research.model_predictions set metadata=(metadata #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(metadata)='string'",[approved.scenario]);
    await q("with r as (select id from research.model_runs where run_key like 'final-v1-r3-'+$1+'-hgb-%') update research.model_artifacts set metadata=(metadata #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(metadata)='string'",[approved.scenario]);
    await q("update research.artifact_registry set metadata=(metadata #>> '{}')::jsonb where provider_artifact_id=$1 and jsonb_typeof(metadata)='string'",[approved.artifactId]);

    await sql.end({timeout:5});
    return Response.json({
      ok:true,scenario:approved.scenario,sha256:sha,artifact_id:approved.artifactId,
      predictions:predictions.length,run_ids:runIds,storage_path:bundlePath
    });
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e && e.stack ? e.stack : e)},{status:500});
  }
});
