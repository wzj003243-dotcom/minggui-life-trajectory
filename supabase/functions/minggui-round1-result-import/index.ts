
import postgres from "npm:postgres@3.4.5";
import JSZip from "npm:jszip@3.10.1";
import Papa from "npm:papaparse@5.4.1";

const APPROVED_SHA="e39ef02bd94cbab2d767d9c786679d48528b4317e85fbdccf12d3b9d822ba387";
const DATASET="8261f970-adc3-4f9a-8043-9e0f6cb90be8";
const WORKFLOW_RUN="37412032573";
const ARTIFACT_ID="11389687413";
const CODE_COMMIT="87f30c9a5f4d4d77af5e934edff0444d63f2eeea";
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

function runKey(modelFamily,variant){
  if(modelFamily==="majority_prior") return "final-v1-r1-person-hash-majority-prior";
  return "final-v1-r1-person-hash-logistic-"+variant;
}

function contentType(path){
  if(path.endsWith(".json")) return "application/json";
  if(path.endsWith(".csv")) return "text/csv";
  if(path.endsWith(".gz")) return "application/gzip";
  if(path.endsWith(".joblib")) return "application/octet-stream";
  return "application/octet-stream";
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
    async function textOf(path){ return new TextDecoder().decode(await bytesOf(path)); }

    const summary=JSON.parse(await textOf("round1-results/round1_summary.json"));
    const checksums=JSON.parse(await textOf("round1-results/SHA256SUMS.json"));
    if(summary.dataset_id!==DATASET) throw new Error("dataset mismatch");
    if(summary.dataset_fingerprint!=="a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888") throw new Error("dataset fingerprint mismatch");
    if(summary.placebo_mapping_fingerprint!=="3010d4188445645271ca771980f8947d20f96362f96f6b286e256610887cdd0e") throw new Error("placebo fingerprint mismatch");

    async function upload(path,data,ctype){
      const res=await fetch(url+"/storage/v1/object/research-artifacts/"+path,{
        method:"POST",
        headers:{
          "Authorization":"Bearer "+secret,
          "apikey":secret,
          "Content-Type":ctype,
          "x-upsert":"true"
        },
        body:data
      });
      const body=await res.text();
      if(!res.ok) throw new Error("storage upload failed "+res.status+" "+path+": "+body);
    }

    const bundlePath="model-runs/final-v1-round1/"+sha+"/bundle.zip";
    await upload(bundlePath,bytes,"application/zip");

    const artifactFiles=[
      "round1_summary.json","metrics.csv","raw_domain_metrics.csv","predictions.csv.gz",
      "model_manifest.json","SHA256SUMS.json",
      "models/history_reality_v1.joblib","models/raw_birth_calendar_v1.joblib",
      "models/bazi_objective_only_v1.joblib","models/history_plus_bazi_v1.joblib",
      "models/bazi_decade_shuffle_placebo_v1.joblib"
    ];
    const stored={};
    for(const rel of artifactFiles){
      stored[rel]=bundlePath+"#round1-results/"+rel;
    }

    await q(
      "insert into research.artifact_registry(artifact_key,provider,provider_artifact_id,artifact_name,artifact_kind,sha256,size_bytes,source_workflow_run_id,source_git_sha,storage_bucket,storage_path,status,metadata,archived_at,imported_at) "+
      "values($1,'github-actions',$2,'minggui-final-v1-round1','model-benchmark-round1',$3,$4,$5,$6,'research-artifacts',$7,'archived',$8::jsonb,now(),now()) "+
      "on conflict(artifact_key) do update set storage_bucket=excluded.storage_bucket,storage_path=excluded.storage_path,size_bytes=excluded.size_bytes,status='archived',metadata=research.artifact_registry.metadata||excluded.metadata,archived_at=coalesce(research.artifact_registry.archived_at,now()),imported_at=now()",
      ["github-actions:"+ARTIFACT_ID+":"+sha,ARTIFACT_ID,sha,bytes.length,WORKFLOW_RUN,CODE_COMMIT,bundlePath,JSON.stringify({dataset_id:DATASET,scenario:"person_hash_v1",round:"final-v1-round1"})]
    );

    const variants=[
      ["majority_prior","none"],
      ["multinomial_logistic","history_reality_v1"],
      ["multinomial_logistic","raw_birth_calendar_v1"],
      ["multinomial_logistic","bazi_objective_only_v1"],
      ["multinomial_logistic","history_plus_bazi_v1"],
      ["multinomial_logistic","bazi_decade_shuffle_placebo_v1"]
    ];
    const runIds={};
    for(const pair of variants){
      const family=pair[0], variant=pair[1];
      const key=runKey(family,variant);
      const config={
        benchmark_round:"final-v1-round1",
        protocol_key:"next-canonical-domain-benchmark-v1",
        target:"target_class_4",
        split_scenario:"person_hash_v1",
        dataset_fingerprint:summary.dataset_fingerprint,
        placebo_mapping_fingerprint:summary.placebo_mapping_fingerprint,
        model_family:family,
        feature_variant:variant,
        seed:SEED,
        no_hyperparameter_search:true,
        class_weight:family==="multinomial_logistic"?"balanced_from_train_only":null,
        logistic:family==="multinomial_logistic"?{solver:"lbfgs",C:1.0,max_iter:5000}:null
      };
      const rows=await q(
        "insert into research.model_runs(training_dataset_id,run_key,model_family,feature_variant,split_scenario_key,code_commit,random_seed,config,environment,status,notes,started_at,finished_at) "+
        "values($1::uuid,$2,$3,$4,'person_hash_v1',$5,$6,$7::jsonb,$8::jsonb,'completed',$9,$10::timestamptz,$11::timestamptz) "+
        "on conflict(run_key) do update set config=excluded.config,environment=excluded.environment,status='completed',code_commit=excluded.code_commit,random_seed=excluded.random_seed,notes=excluded.notes,started_at=excluded.started_at,finished_at=excluded.finished_at returning id",
        [DATASET,key,family,variant,CODE_COMMIT,SEED,JSON.stringify(config),JSON.stringify(summary.environment),
         "Final v1 round1 preregistered person-hash benchmark; test evaluated once after protocol freeze.",
         "2026-10-06T04:06:00Z","2026-10-06T04:08:18Z"]
      );
      runIds[family+"|"+variant]=String(rows[0].id);
    }

    const metrics=parseCsv(await textOf("round1-results/metrics.csv"));
    for(const row of metrics){
      const rid=runIds[row.model_family+"|"+row.feature_variant];
      const details=JSON.parse(row.details||"{}");
      for(const key of ["n","accuracy","balanced_accuracy","macro_f1","log_loss","brier_multiclass","ece_10bin"]){
        await q(
          "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) values($1::uuid,$2,$3,$4,$5::jsonb) "+
          "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value,details=excluded.details",
          [rid,row.split_name,key,Number(row[key]),JSON.stringify(key==="n"?{}:details)]
        );
      }
    }

    const rawMetrics=parseCsv(await textOf("round1-results/raw_domain_metrics.csv"));
    for(const row of rawMetrics){
      const rid=runIds["multinomial_logistic|"+row.feature_variant];
      await q(
        "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) values($1::uuid,$2,'raw_domain_macro_f1',$3,$4::jsonb) "+
        "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value,details=excluded.details",
        [rid,row.split_name,Number(row.macro_f1),JSON.stringify({n:Number(row.n),support:JSON.parse(row.support||"{}"),train_classes:JSON.parse(row.train_classes||"[]")})]
      );
    }

    const cmp=summary.paired_cluster_bootstrap;
    const comparisons=[
      ["history_plus_bazi_minus_history","multinomial_logistic|history_plus_bazi_v1","delta_macro_f1_vs_history_reality"],
      ["bazi_minus_raw_calendar","multinomial_logistic|bazi_objective_only_v1","delta_macro_f1_vs_raw_birth_calendar"],
      ["bazi_minus_placebo","multinomial_logistic|bazi_objective_only_v1","delta_macro_f1_vs_placebo"]
    ];
    for(const item of comparisons){
      const d=cmp[item[0]];
      await q(
        "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) values($1::uuid,'test',$2,$3,$4::jsonb) "+
        "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value,details=excluded.details",
        [runIds[item[1]],item[2],Number(d.delta_macro_f1),JSON.stringify(d)]
      );
    }

    const predictions=parseCsv(await gunzip(await bytesOf("round1-results/predictions.csv.gz")));
    const batchSize=400;
    for(let start=0;start<predictions.length;start+=batchSize){
      const batch=predictions.slice(start,start+batchSize);
      const params=[];
      const values=[];
      let n=1;
      for(const r of batch){
        const rid=runIds[r.model_family+"|"+r.feature_variant];
        values.push("($"+(n++)+"::uuid,$"+(n++)+"::bigint,$"+(n++)+",$"+(n++)+",$"+(n++)+",$"+(n++)+"::jsonb,$"+(n++)+"::jsonb)");
        params.push(
          rid,Number(r.training_example_id),r.split_name,r.y_true,r.y_pred,
          JSON.stringify({career:Number(r.p_career),recognition:Number(r.p_recognition),relationship:Number(r.p_relationship),other:Number(r.p_other)}),
          JSON.stringify({round:"final-v1-round1",person_id:Number(r.person_id)})
        );
      }
      await q(
        "insert into research.model_predictions(run_id,training_example_id,split_name,y_true,y_pred,probabilities,metadata) values "+values.join(",")+
        " on conflict(run_id,training_example_id) do update set split_name=excluded.split_name,y_true=excluded.y_true,y_pred=excluded.y_pred,probabilities=excluded.probabilities,metadata=excluded.metadata",
        params
      );
    }

    for(const pair of variants){
      const family=pair[0], variant=pair[1];
      const rid=runIds[family+"|"+variant];
      await q(
        "insert into research.model_artifacts(run_id,artifact_type,uri,sha256,metadata) values($1::uuid,'benchmark_bundle_zip',$2,$3,$4::jsonb) "+
        "on conflict(run_id,artifact_type,sha256) do update set uri=excluded.uri,metadata=excluded.metadata",
        [rid,"storage://research-artifacts/"+bundlePath,sha,JSON.stringify({github_artifact_id:ARTIFACT_ID,workflow_run_id:WORKFLOW_RUN})]
      );
      await q(
        "insert into research.model_artifacts(run_id,artifact_type,uri,sha256,metadata) values($1::uuid,'round1_summary_json',$2,$3,$4::jsonb) "+
        "on conflict(run_id,artifact_type,sha256) do update set uri=excluded.uri,metadata=excluded.metadata",
        [rid,"storage://research-artifacts/"+stored["round1_summary.json"],checksums["round1_summary.json"],JSON.stringify({round:"final-v1-round1"})]
      );
      if(family==="multinomial_logistic"){
        const rel="models/"+variant+".joblib";
        await q(
          "insert into research.model_artifacts(run_id,artifact_type,uri,sha256,metadata) values($1::uuid,'model_joblib',$2,$3,$4::jsonb) "+
          "on conflict(run_id,artifact_type,sha256) do update set uri=excluded.uri,metadata=excluded.metadata",
          [rid,"storage://research-artifacts/"+stored[rel],checksums[rel],JSON.stringify({feature_variant:variant,environment:summary.environment})]
        );
      }
    }

    // Normalize JSONB values defensively. postgres-js unsafe parameters can otherwise
    // preserve JSON.stringify payloads as JSON strings rather than JSON objects.
    await q(
      "with r as (select id from research.model_runs where run_key like 'final-v1-r1-person-hash%') "+
      "update research.model_runs set config=(config #>> '{}')::jsonb where id in (select id from r) and jsonb_typeof(config)='string'"
    );
    await q(
      "with r as (select id from research.model_runs where run_key like 'final-v1-r1-person-hash%') "+
      "update research.model_runs set environment=(environment #>> '{}')::jsonb where id in (select id from r) and jsonb_typeof(environment)='string'"
    );
    await q(
      "with r as (select id from research.model_runs where run_key like 'final-v1-r1-person-hash%') "+
      "update research.model_metrics set details=(details #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(details)='string'"
    );
    await q(
      "with r as (select id from research.model_runs where run_key like 'final-v1-r1-person-hash%') "+
      "update research.model_predictions set probabilities=(probabilities #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(probabilities)='string'"
    );
    await q(
      "with r as (select id from research.model_runs where run_key like 'final-v1-r1-person-hash%') "+
      "update research.model_predictions set metadata=(metadata #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(metadata)='string'"
    );
    await q(
      "with r as (select id from research.model_runs where run_key like 'final-v1-r1-person-hash%') "+
      "update research.model_artifacts set metadata=(metadata #>> '{}')::jsonb where run_id in (select id from r) and jsonb_typeof(metadata)='string'"
    );
    await q(
      "update research.artifact_registry set metadata=(metadata #>> '{}')::jsonb where provider_artifact_id=$1 and jsonb_typeof(metadata)='string'",
      [ARTIFACT_ID]
    );

    await sql.end({timeout:5});
    return Response.json({
      ok:true,sha256:sha,artifact_id:ARTIFACT_ID,workflow_run_id:WORKFLOW_RUN,
      predictions:predictions.length,metrics_rows:metrics.length,raw_metric_rows:rawMetrics.length,
      run_ids:runIds,storage_path:bundlePath
    });
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e && e.stack ? e.stack : e)},{status:500});
  }
});
