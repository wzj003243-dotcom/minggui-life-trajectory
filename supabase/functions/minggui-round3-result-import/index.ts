
import postgres from "npm:postgres@3.4.5";
import JSZip from "npm:jszip@3.10.1";
import Papa from "npm:papaparse@5.4.1";

const APPROVED_SHA="5344a9c993602c29ced4c6453ccee4bd78f782046b2f08b1374619c2a451c293";
const DATASET="8261f970-adc3-4f9a-8043-9e0f6cb90be8";
const WORKFLOW_RUN="37417426946";
const ARTIFACT_ID="11392340286";
const CODE_COMMIT="718ddc4814ce17b476e195117cc5bd655e1ee30f";
const SEED=20261006;
const SCENARIOS=["forward_era_v1","geo_us_holdout_v1","geo_france_holdout_v1"];
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
    if(sha!==APPROVED_SHA) throw new Error("unapproved artifact sha "+sha);

    const zip=await JSZip.loadAsync(bytes);
    async function bytesOf(path){
      const f=zip.file(path);
      if(!f) throw new Error("missing "+path);
      return new Uint8Array(await f.async("uint8array"));
    }
    async function textOf(path){
      return new TextDecoder().decode(await bytesOf(path));
    }

    const summary=JSON.parse(await textOf("round3-results/round3_summary.json"));
    const checksums=JSON.parse(await textOf("round3-results/SHA256SUMS.json"));
    if(summary.dataset_id!==DATASET) throw new Error("dataset mismatch");
    if(summary.protocol_key!=="next-canonical-domain-ood-round3-v1") throw new Error("protocol mismatch");
    if(summary.dataset_fingerprint!=="a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888") throw new Error("dataset fingerprint mismatch");
    if(summary.placebo_mapping_fingerprint!=="3010d4188445645271ca771980f8947d20f96362f96f6b286e256610887cdd0e") throw new Error("placebo fingerprint mismatch");
    if(summary.no_round3_hyperparameter_selection!==true) throw new Error("round3 tuning invariant failed");
    if(summary.fixed_config?.key!=="hgb_small") throw new Error("fixed config mismatch");

    async function uploadZip(path,data){
      const res=await fetch(url+"/storage/v1/object/research-artifacts/"+path,{
        method:"POST",
        headers:{
          "Authorization":"Bearer "+secret,
          "apikey":secret,
          "Content-Type":"application/zip",
          "x-upsert":"true"
        },
        body:data
      });
      const body=await res.text();
      if(!res.ok) throw new Error("storage upload failed "+res.status+": "+body);
    }

    const bundlePath="model-runs/final-v1-round3/"+sha+"/bundle.zip";
    await uploadZip(bundlePath,bytes);

    await q(
      "insert into research.artifact_registry(artifact_key,provider,provider_artifact_id,artifact_name,artifact_kind,sha256,size_bytes,source_workflow_run_id,source_git_sha,storage_bucket,storage_path,status,metadata,archived_at,imported_at) "+
      "values($1,'github-actions',$2,'minggui-final-v1-round3','model-benchmark-round3',$3,$4,$5,$6,'research-artifacts',$7,'archived',$8::jsonb,now(),now()) "+
      "on conflict(artifact_key) do update set storage_bucket=excluded.storage_bucket,storage_path=excluded.storage_path,size_bytes=excluded.size_bytes,status='archived',metadata=research.artifact_registry.metadata||excluded.metadata,archived_at=coalesce(research.artifact_registry.archived_at,now()),imported_at=now()",
      [
        "github-actions:"+ARTIFACT_ID+":"+sha,
        ARTIFACT_ID,sha,bytes.length,WORKFLOW_RUN,CODE_COMMIT,bundlePath,
        JSON.stringify({
          dataset_id:DATASET,
          round:"final-v1-round3",
          protocol_key:"next-canonical-domain-ood-round3-v1",
          scenarios:SCENARIOS
        })
      ]
    );

    const runIds={};
    for(const scenario of SCENARIOS){
      for(const variant of VARIANTS){
        const key=runKey(scenario,variant);
        const config={
          benchmark_round:"final-v1-round3",
          protocol_key:"next-canonical-domain-ood-round3-v1",
          target:"target_class_4",
          split_scenario:scenario,
          dataset_fingerprint:summary.dataset_fingerprint,
          placebo_mapping_fingerprint:summary.placebo_mapping_fingerprint,
          model_family:"hist_gradient_boosting",
          feature_variant:variant,
          seed:SEED,
          fixed_config_source:summary.fixed_config_source,
          fixed_config:summary.fixed_config,
          no_round3_hyperparameter_selection:true,
          class_weight:"balanced_sample_weights_from_scenario_train_only"
        };
        const rows=await q(
          "insert into research.model_runs(training_dataset_id,run_key,model_family,feature_variant,split_scenario_key,code_commit,random_seed,config,environment,status,notes,started_at,finished_at) "+
          "values($1::uuid,$2,'hist_gradient_boosting',$3,$4,$5,$6,$7::jsonb,$8::jsonb,'completed',$9,$10::timestamptz,$11::timestamptz) "+
          "on conflict(run_key) do update set config=excluded.config,environment=excluded.environment,status='completed',code_commit=excluded.code_commit,random_seed=excluded.random_seed,notes=excluded.notes,started_at=excluded.started_at,finished_at=excluded.finished_at returning id",
          [
            DATASET,key,variant,scenario,CODE_COMMIT,SEED,
            JSON.stringify(config),JSON.stringify(summary.environment),
            "Final v1 Round 3 preregistered OOD benchmark; fixed Round-2 hgb_small with no holdout-specific tuning.",
            "2026-10-06T05:14:28Z","2026-10-06T05:29:14Z"
          ]
        );
        runIds[scenario+"|"+variant]=String(rows[0].id);
      }
    }

    const metrics=parseCsv(await textOf("round3-results/metrics.csv"));
    for(const row of metrics){
      const rid=runIds[row.scenario_key+"|"+row.feature_variant];
      if(!rid) throw new Error("missing run for metric "+row.scenario_key+" "+row.feature_variant);
      const details=JSON.parse(row.details||"{}");
      for(const key of ["n","accuracy","balanced_accuracy","macro_f1","log_loss","brier_multiclass","ece_10bin"]){
        await q(
          "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) values($1::uuid,$2,$3,$4,$5::jsonb) "+
          "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value,details=excluded.details",
          [rid,row.split_name,key,Number(row[key]),JSON.stringify(key==="n"?{}:details)]
        );
      }
    }

    const rawMetrics=parseCsv(await textOf("round3-results/raw_domain_metrics.csv"));
    for(const row of rawMetrics){
      const rid=runIds[row.scenario_key+"|"+row.feature_variant];
      await q(
        "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) values($1::uuid,$2,'raw_domain_macro_f1',$3,$4::jsonb) "+
        "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value,details=excluded.details",
        [
          rid,row.split_name,Number(row.macro_f1),
          JSON.stringify({
            n:Number(row.n),
            support:JSON.parse(row.support||"{}"),
            train_classes:JSON.parse(row.train_classes||"[]")
          })
        ]
      );
    }

    for(const scenario of SCENARIOS){
      const cmp=summary.paired_cluster_bootstrap[scenario];
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
          [
            runIds[scenario+"|"+item[1]],
            item[2],Number(d.delta_macro_f1),JSON.stringify(d)
          ]
        );
      }
    }

    const predictions=parseCsv(await gunzip(await bytesOf("round3-results/predictions.csv.gz")));
    const batchSize=300;
    for(let start=0;start<predictions.length;start+=batchSize){
      const batch=predictions.slice(start,start+batchSize);
      const params=[];
      const values=[];
      let n=1;
      for(const r of batch){
        const rid=runIds[r.scenario_key+"|"+r.feature_variant];
        if(!rid) throw new Error("missing run for prediction "+r.scenario_key+" "+r.feature_variant);
        values.push("($"+(n++)+"::uuid,$"+(n++)+"::bigint,$"+(n++)+",$"+(n++)+",$"+(n++)+",$"+(n++)+"::jsonb,$"+(n++)+"::jsonb)");
        params.push(
          rid,Number(r.training_example_id),r.split_name,r.y_true,r.y_pred,
          JSON.stringify({
            career:Number(r.p_career),
            other:Number(r.p_other),
            recognition:Number(r.p_recognition),
            relationship:Number(r.p_relationship)
          }),
          JSON.stringify({
            round:"final-v1-round3",
            scenario_key:r.scenario_key,
            person_id:Number(r.person_id)
          })
        );
      }
      await q(
        "insert into research.model_predictions(run_id,training_example_id,split_name,y_true,y_pred,probabilities,metadata) values "+values.join(",")+
        " on conflict(run_id,training_example_id) do update set split_name=excluded.split_name,y_true=excluded.y_true,y_pred=excluded.y_pred,probabilities=excluded.probabilities,metadata=excluded.metadata",
        params
      );
    }

    for(const scenario of SCENARIOS){
      for(const variant of VARIANTS){
        const rid=runIds[scenario+"|"+variant];
        const modelRel="models/"+scenario+"/"+variant+".joblib";
        await q(
          "insert into research.model_artifacts(run_id,artifact_type,uri,sha256,metadata) values($1::uuid,'benchmark_bundle_zip',$2,$3,$4::jsonb) "+
          "on conflict(run_id,artifact_type,sha256) do update set uri=excluded.uri,metadata=excluded.metadata",
          [
            rid,"storage://research-artifacts/"+bundlePath,sha,
            JSON.stringify({github_artifact_id:ARTIFACT_ID,workflow_run_id:WORKFLOW_RUN,scenario_key:scenario})
          ]
        );
        await q(
          "insert into research.model_artifacts(run_id,artifact_type,uri,sha256,metadata) values($1::uuid,'round3_summary_json',$2,$3,$4::jsonb) "+
          "on conflict(run_id,artifact_type,sha256) do update set uri=excluded.uri,metadata=excluded.metadata",
          [
            rid,
            "storage://research-artifacts/"+bundlePath+"#round3-results/round3_summary.json",
            checksums["round3_summary.json"],
            JSON.stringify({round:"final-v1-round3",scenario_key:scenario})
          ]
        );
        await q(
          "insert into research.model_artifacts(run_id,artifact_type,uri,sha256,metadata) values($1::uuid,'model_joblib',$2,$3,$4::jsonb) "+
          "on conflict(run_id,artifact_type,sha256) do update set uri=excluded.uri,metadata=excluded.metadata",
          [
            rid,
            "storage://research-artifacts/"+bundlePath+"#round3-results/"+modelRel,
            checksums[modelRel],
            JSON.stringify({feature_variant:variant,scenario_key:scenario,fixed_config:summary.fixed_config})
          ]
        );
      }
    }

    // Normalize driver-produced JSON strings to actual JSONB objects.
    await q(
      "with r as (select id from research.model_runs where run_key like 'final-v1-r3-%') update research.model_runs set config=(config #>> '{}')::jsonb where id in (select id from r) and jsonb_typeof(config)='string'"
    );
    await q(
      "with r as (select id from research.model_runs where run_key like 'final-v1-r3-%') update research.model_runs set environment=(environment #>> '{}')::jsonb where id in (select id from r) and jsonb_typeof(environment)='string'"
    );
    await q(
      "with r as (select id from research.model_runs where run_key like 'final-v1-r3-%') update research.model_metrics set details=(details #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(details)='string'"
    );
    await q(
      "with r as (select id from research.model_runs where run_key like 'final-v1-r3-%') update research.model_predictions set probabilities=(probabilities #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(probabilities)='string'"
    );
    await q(
      "with r as (select id from research.model_runs where run_key like 'final-v1-r3-%') update research.model_predictions set metadata=(metadata #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(metadata)='string'"
    );
    await q(
      "with r as (select id from research.model_runs where run_key like 'final-v1-r3-%') update research.model_artifacts set metadata=(metadata #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(metadata)='string'"
    );
    await q(
      "update research.artifact_registry set metadata=(metadata #>> '{}')::jsonb where provider_artifact_id=$1 and jsonb_typeof(metadata)='string'",
      [ARTIFACT_ID]
    );

    await sql.end({timeout:5});
    return Response.json({
      ok:true,
      sha256:sha,
      artifact_id:ARTIFACT_ID,
      workflow_run_id:WORKFLOW_RUN,
      run_count:Object.keys(runIds).length,
      predictions:predictions.length,
      metrics_rows:metrics.length,
      raw_metric_rows:rawMetrics.length,
      storage_path:bundlePath
    });
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e && e.stack ? e.stack : e)},{status:500});
  }
});
