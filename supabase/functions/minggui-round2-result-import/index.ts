
import postgres from "npm:postgres@3.4.5";
import JSZip from "npm:jszip@3.10.1";
import Papa from "npm:papaparse@5.4.1";

const APPROVED_SHA="39337ab164b62a7301eae7c7ca260d48065751f7bcad482efd2c552d80ed46bd";
const DATASET="8261f970-adc3-4f9a-8043-9e0f6cb90be8";
const PROTOCOL="next-canonical-domain-nonlinear-round2-v1";
const WORKFLOW_RUN="37413437609";
const ARTIFACT_ID="11390157851";
const CODE_COMMIT="c388413394e76ffd4acc50b10f208191a038a8e9";
const SEED=20261006;

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
function runKey(variant){ return "final-v1-r2-person-hash-hgb-"+variant; }

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
      const f=zip.file(path); if(!f) throw new Error("missing "+path);
      return new Uint8Array(await f.async("uint8array"));
    }
    async function textOf(path){ return new TextDecoder().decode(await bytesOf(path)); }

    const summary=JSON.parse(await textOf("round2-results/round2_summary.json"));
    const selection=JSON.parse(await textOf("round2-results/selection.json"));
    const checksums=JSON.parse(await textOf("round2-results/SHA256SUMS.json"));
    if(summary.dataset_id!==DATASET) throw new Error("dataset mismatch");
    if(summary.protocol_key!==PROTOCOL) throw new Error("protocol mismatch");
    if(summary.dataset_fingerprint!=="a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888") throw new Error("dataset fingerprint mismatch");
    if(summary.placebo_mapping_fingerprint!=="3010d4188445645271ca771980f8947d20f96362f96f6b286e256610887cdd0e") throw new Error("placebo fingerprint mismatch");
    if(summary.selected_config?.key!=="hgb_small") throw new Error("unexpected selected config");

    const bundlePath="model-runs/final-v1-round2/"+sha+"/bundle.zip";
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
    const rb=await res.text();
    if(!res.ok) throw new Error("storage upload failed "+res.status+": "+rb);

    await q(
      "insert into research.artifact_registry(artifact_key,provider,provider_artifact_id,artifact_name,artifact_kind,sha256,size_bytes,source_workflow_run_id,source_git_sha,storage_bucket,storage_path,status,metadata,archived_at,imported_at) "+
      "values($1,'github-actions',$2,'minggui-final-v1-round2','model-benchmark-round2',$3,$4,$5,$6,'research-artifacts',$7,'archived',$8::jsonb,now(),now()) "+
      "on conflict(artifact_key) do update set storage_bucket=excluded.storage_bucket,storage_path=excluded.storage_path,size_bytes=excluded.size_bytes,status='archived',metadata=excluded.metadata,archived_at=coalesce(research.artifact_registry.archived_at,now()),imported_at=now()",
      ["github-actions:"+ARTIFACT_ID+":"+sha,ARTIFACT_ID,sha,bytes.length,WORKFLOW_RUN,CODE_COMMIT,bundlePath,
       JSON.stringify({dataset_id:DATASET,protocol_key:PROTOCOL,round:"final-v1-round2",selected_config:summary.selected_config})]
    );

    const candidateRows=parseCsv(await textOf("round2-results/candidate_validation_metrics.csv"));
    const cfgByKey={};
    for(const c of selection.candidate_summary) cfgByKey[c.candidate_key]=c.config;
    for(const r of candidateRows){
      await q(
        "insert into research.model_selection_trials(training_dataset_id,protocol_key,model_family,candidate_key,feature_variant,split_scenario_key,split_name,candidate_order,selected,config,metrics,source_artifact_sha256,code_commit) "+
        "values($1::uuid,$2,'hist_gradient_boosting',$3,$4,'person_hash_v1','validation',$5,$6,$7::jsonb,$8::jsonb,$9,$10) "+
        "on conflict(protocol_key,candidate_key,feature_variant,split_scenario_key,split_name) do update set candidate_order=excluded.candidate_order,selected=excluded.selected,config=excluded.config,metrics=excluded.metrics,source_artifact_sha256=excluded.source_artifact_sha256,code_commit=excluded.code_commit",
        [DATASET,PROTOCOL,r.candidate_key,r.feature_variant,Number(r.candidate_order),r.candidate_key===summary.selected_config.key,
         JSON.stringify(cfgByKey[r.candidate_key]||{}),
         JSON.stringify({
           macro_f1:Number(r.validation_macro_f1),
           balanced_accuracy:Number(r.validation_balanced_accuracy),
           log_loss:Number(r.validation_log_loss),
           brier_multiclass:Number(r.validation_brier_multiclass),
           ece_10bin:Number(r.validation_ece_10bin),
           n:Number(r.validation_n)
         }),sha,CODE_COMMIT]
      );
    }

    const variants=[
      "history_reality_v1","raw_birth_calendar_v1","bazi_objective_only_v1",
      "history_plus_bazi_v1","bazi_decade_shuffle_placebo_v1"
    ];
    const runIds={};
    for(const variant of variants){
      const config={
        benchmark_round:"final-v1-round2",
        protocol_key:PROTOCOL,
        target:"target_class_4",
        split_scenario:"person_hash_v1",
        dataset_fingerprint:summary.dataset_fingerprint,
        placebo_mapping_fingerprint:summary.placebo_mapping_fingerprint,
        selected_config:summary.selected_config,
        selection_rule:selection.selection_rule,
        model_family:"hist_gradient_boosting",
        feature_variant:variant,
        seed:SEED,
        balanced_sample_weights_from_train_only:true,
        early_stopping:false,
        rejected_candidates_test_evaluated:false
      };
      const rows=await q(
        "insert into research.model_runs(training_dataset_id,run_key,model_family,feature_variant,split_scenario_key,code_commit,random_seed,config,environment,status,notes,started_at,finished_at) "+
        "values($1::uuid,$2,'hist_gradient_boosting',$3,'person_hash_v1',$4,$5,$6::jsonb,$7::jsonb,'completed',$8,$9::timestamptz,$10::timestamptz) "+
        "on conflict(run_key) do update set config=excluded.config,environment=excluded.environment,status='completed',code_commit=excluded.code_commit,random_seed=excluded.random_seed,notes=excluded.notes,started_at=excluded.started_at,finished_at=excluded.finished_at returning id",
        [DATASET,runKey(variant),variant,CODE_COMMIT,SEED,JSON.stringify(config),JSON.stringify(summary.environment),
         "Final v1 Round 2 preregistered nonlinear HGB benchmark; one shared validation-selected config; rejected configs never evaluated on test.",
         "2026-10-06T04:23:50Z","2026-10-06T04:34:31Z"]
      );
      runIds[variant]=String(rows[0].id);
    }

    const metrics=parseCsv(await textOf("round2-results/metrics.csv"));
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

    const rawMetrics=parseCsv(await textOf("round2-results/raw_domain_metrics.csv"));
    for(const row of rawMetrics){
      await q(
        "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) values($1::uuid,$2,'raw_domain_macro_f1',$3,$4::jsonb) "+
        "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value,details=excluded.details",
        [runIds[row.feature_variant],row.split_name,Number(row.macro_f1),
         JSON.stringify({n:Number(row.n),support:JSON.parse(row.support||"{}"),train_classes:JSON.parse(row.train_classes||"[]")})]
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

    const predictions=parseCsv(await gunzip(await bytesOf("round2-results/predictions.csv.gz")));
    for(let start=0;start<predictions.length;start+=400){
      const batch=predictions.slice(start,start+400);
      const params=[]; const values=[]; let n=1;
      for(const r of batch){
        values.push("($"+(n++)+"::uuid,$"+(n++)+"::bigint,$"+(n++)+",$"+(n++)+",$"+(n++)+",$"+(n++)+"::jsonb,$"+(n++)+"::jsonb)");
        params.push(
          runIds[r.feature_variant],Number(r.training_example_id),r.split_name,r.y_true,r.y_pred,
          JSON.stringify({career:Number(r.p_career),other:Number(r.p_other),recognition:Number(r.p_recognition),relationship:Number(r.p_relationship)}),
          JSON.stringify({round:"final-v1-round2",person_id:Number(r.person_id)})
        );
      }
      await q(
        "insert into research.model_predictions(run_id,training_example_id,split_name,y_true,y_pred,probabilities,metadata) values "+values.join(",")+
        " on conflict(run_id,training_example_id) do update set split_name=excluded.split_name,y_true=excluded.y_true,y_pred=excluded.y_pred,probabilities=excluded.probabilities,metadata=excluded.metadata",
        params
      );
    }

    for(const variant of variants){
      const rid=runIds[variant];
      const modelRel="models/"+variant+".joblib";
      const artifacts=[
        ["benchmark_bundle_zip","storage://research-artifacts/"+bundlePath,sha,{github_artifact_id:ARTIFACT_ID,workflow_run_id:WORKFLOW_RUN}],
        ["round2_summary_json","storage://research-artifacts/"+bundlePath+"#round2-results/round2_summary.json",checksums["round2_summary.json"],{round:"final-v1-round2"}],
        ["selection_json","storage://research-artifacts/"+bundlePath+"#round2-results/selection.json",checksums["selection.json"],{selected_config:summary.selected_config}],
        ["model_joblib","storage://research-artifacts/"+bundlePath+"#round2-results/"+modelRel,checksums[modelRel],{feature_variant:variant,selected_config:summary.selected_config}]
      ];
      for(const a of artifacts){
        await q(
          "insert into research.model_artifacts(run_id,artifact_type,uri,sha256,metadata) values($1::uuid,$2,$3,$4,$5::jsonb) "+
          "on conflict(run_id,artifact_type,sha256) do update set uri=excluded.uri,metadata=excluded.metadata",
          [rid,a[0],a[1],a[2],JSON.stringify(a[3])]
        );
      }
    }

    await q(
      "update research.training_benchmark_protocols set metadata=metadata||jsonb_build_object('official_artifact_id',$1,'official_artifact_sha256',$2,'official_workflow_run_id',$3,'selected_config',$4::jsonb,'completed_at','2026-10-06T04:34:31Z') where protocol_key=$5",
      [ARTIFACT_ID,sha,WORKFLOW_RUN,JSON.stringify(summary.selected_config),PROTOCOL]
    );

    // Normalize any JSON-string payloads created through unsafe parameter binding.
    await q("with r as (select id from research.model_runs where run_key like 'final-v1-r2-person-hash-hgb-%') update research.model_runs set config=(config #>> '{}')::jsonb where id in (select id from r) and jsonb_typeof(config)='string'");
    await q("with r as (select id from research.model_runs where run_key like 'final-v1-r2-person-hash-hgb-%') update research.model_runs set environment=(environment #>> '{}')::jsonb where id in (select id from r) and jsonb_typeof(environment)='string'");
    await q("with r as (select id from research.model_runs where run_key like 'final-v1-r2-person-hash-hgb-%') update research.model_metrics set details=(details #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(details)='string'");
    await q("with r as (select id from research.model_runs where run_key like 'final-v1-r2-person-hash-hgb-%') update research.model_predictions set probabilities=(probabilities #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(probabilities)='string'");
    await q("with r as (select id from research.model_runs where run_key like 'final-v1-r2-person-hash-hgb-%') update research.model_predictions set metadata=(metadata #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(metadata)='string'");
    await q("with r as (select id from research.model_runs where run_key like 'final-v1-r2-person-hash-hgb-%') update research.model_artifacts set metadata=(metadata #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(metadata)='string'");
    await q("update research.model_selection_trials set config=(config #>> '{}')::jsonb where protocol_key=$1 and jsonb_typeof(config)='string'",[PROTOCOL]);
    await q("update research.model_selection_trials set metrics=(metrics #>> '{}')::jsonb where protocol_key=$1 and jsonb_typeof(metrics)='string'",[PROTOCOL]);
    await q("update research.artifact_registry set metadata=(metadata #>> '{}')::jsonb where provider_artifact_id=$1 and jsonb_typeof(metadata)='string'",[ARTIFACT_ID]);

    await sql.end({timeout:5});
    return Response.json({
      ok:true,sha256:sha,artifact_id:ARTIFACT_ID,workflow_run_id:WORKFLOW_RUN,
      selected_config:summary.selected_config,
      predictions:predictions.length,metrics_rows:metrics.length,selection_trials:candidateRows.length,
      run_ids:runIds,storage_path:bundlePath
    });
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e && e.stack ? e.stack : e)},{status:500});
  }
});
