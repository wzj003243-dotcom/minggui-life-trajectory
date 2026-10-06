
import postgres from "npm:postgres@3.4.5";
import JSZip from "npm:jszip@3.10.1";
import Papa from "npm:papaparse@5.4.1";

const SHA="750dd5f4613cebe599cde9964cb1a3ca46ee42d7fea4f474b6e8aa3bcf20290f";
const ARTIFACT_ID="11395666323";
const WORKFLOW_RUN="37426861843";
const CODE_COMMIT="00986c4bcb007adccb7dfc1aaec14a59dea63c18";
const TRAJ="731fa601-9c18-4ce8-9a8a-557ded47395d";
const TRAJ_FP="9e2de5961856ad79ae260cb87fea1028f38b278c74eb3ff7669d94a35cf9f7c3";
const SOURCE_DATASET="8261f970-adc3-4f9a-8043-9e0f6cb90be8";
const PROTOCOL="discrete-hazard-trajectory-round4-v1";
const BUNDLE_PATH="model-runs/final-v1-round4/"+SHA+"/bundle.zip";
const SEED=20261006;

const VARIANTS=[
  "history_reality_v1",
  "raw_birth_calendar_v1",
  "bazi_objective_only_v1",
  "history_plus_bazi_v1",
  "bazi_decade_shuffle_placebo_v1"
];

const hex=(buf)=>Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,"0")).join("");
const esc=(s)=>String(s).replaceAll("'","''");

async function secret(){
  let v=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const j=Deno.env.get("SUPABASE_SECRET_KEYS");
  if(j){try{v=JSON.parse(j)?.default||v}catch{}}
  return v;
}
function runKey(family,variant){
  if(family==="interval_prior") return "final-v1-r4-person-hash-interval-prior";
  const short=family==="multinomial_logistic"?"logistic":"hgb";
  return "final-v1-r4-person-hash-"+short+"-"+variant;
}
async function storageUpload(bytes){
  const url=Deno.env.get("SUPABASE_URL"), key=await secret();
  const r=await fetch(url+"/storage/v1/object/research-artifacts/"+BUNDLE_PATH,{
    method:"POST",
    headers:{Authorization:"Bearer "+key,apikey:key,"Content-Type":"application/zip","x-upsert":"true"},
    body:bytes
  });
  const t=await r.text();
  if(!r.ok) throw new Error("storage upload "+r.status+": "+t);
}
async function storageDownload(){
  const url=Deno.env.get("SUPABASE_URL"), key=await secret();
  const r=await fetch(url+"/storage/v1/object/authenticated/research-artifacts/"+BUNDLE_PATH,{
    headers:{Authorization:"Bearer "+key,apikey:key}
  });
  if(!r.ok) throw new Error("storage download "+r.status+": "+await r.text());
  return new Uint8Array(await r.arrayBuffer());
}
function parseCsv(text){
  const r=Papa.parse(text,{header:true,skipEmptyLines:true,dynamicTyping:true});
  if(r.errors?.length) throw new Error("CSV parse: "+JSON.stringify(r.errors.slice(0,3)));
  return r.data;
}
async function zipText(zip,path){
  const f=zip.file(path); if(!f) throw new Error("missing "+path);
  return await f.async("text");
}
async function zipBytes(zip,path){
  const f=zip.file(path); if(!f) throw new Error("missing "+path);
  return new Uint8Array(await f.async("uint8array"));
}
async function gunzipText(bytes){
  const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return await new Response(stream).text();
}
async function* gzipLines(bytes){
  const stream=new Blob([bytes]).stream()
    .pipeThrough(new DecompressionStream("gzip"))
    .pipeThrough(new TextDecoderStream());
  const reader=stream.getReader();
  let buf="";
  try{
    while(true){
      const {value,done}=await reader.read();
      if(done) break;
      buf+=value;
      let i;
      while((i=buf.indexOf("\n"))>=0){
        let line=buf.slice(0,i); buf=buf.slice(i+1);
        if(line.endsWith("\r")) line=line.slice(0,-1);
        yield line;
      }
    }
    if(buf){ if(buf.endsWith("\r")) buf=buf.slice(0,-1); yield buf; }
  }finally{reader.releaseLock()}
}
async function insertJsonBatch(sql,query,rows){
  if(!rows.length)return;
  const payload=esc(JSON.stringify(rows));
  await sql.unsafe(query.replace("$JSON","'"+payload+"'::jsonb"));
}
async function getRunIds(sql){
  const rows=await sql.unsafe("select id::text,model_family,feature_variant from research.model_runs where run_key like 'final-v1-r4-person-hash-%'");
  const m=new Map();
  for(const r of rows)m.set(r.model_family+"|"+r.feature_variant,r.id);
  return m;
}
function parseSimple(line){
  // Prediction CSV fields contain no embedded commas/quotes.
  return line.split(",");
}

Deno.serve(async(req)=>{
  if(req.method!=="POST") return new Response("POST only",{status:405});
  const u=new URL(req.url);
  const mode=u.searchParams.get("mode")||"";
  const start=Math.max(0,Number(u.searchParams.get("start")||"0"));
  const end=Math.max(start,Number(u.searchParams.get("end")||"999999999"));
  const db=Deno.env.get("SUPABASE_DB_URL");
  if(!db)return new Response("missing db",{status:500});
  const sql=postgres(db,{prepare:false,max:1});
  try{
    if(mode==="meta"){
      const body=new Uint8Array(await req.arrayBuffer());
      const actual=hex(await crypto.subtle.digest("SHA-256",body));
      if(actual!==SHA) throw new Error("sha mismatch "+actual);
      await storageUpload(body);
      const zip=await JSZip.loadAsync(body);
      const summary=JSON.parse(await zipText(zip,"round4-results/round4_summary.json"));
      const checksums=JSON.parse(await zipText(zip,"round4-results/SHA256SUMS.json"));
      if(summary.trajectory_dataset_id!==TRAJ||summary.trajectory_fingerprint!==TRAJ_FP||summary.protocol_key!==PROTOCOL) throw new Error("summary contract mismatch");
      if(summary.person_period_rows!==52427||summary.cutoff_rows!==13064)throw new Error("count mismatch");

      await sql.unsafe(
        "insert into research.artifact_registry(artifact_key,provider,provider_artifact_id,artifact_name,artifact_kind,sha256,size_bytes,source_workflow_run_id,source_git_sha,storage_bucket,storage_path,status,metadata,archived_at,imported_at) "+
        "values($1,'github-actions',$2,'minggui-final-v1-round4','trajectory-benchmark-round4',$3,$4,$5,$6,'research-artifacts',$7,'archived',$8::jsonb,now(),now()) "+
        "on conflict(artifact_key) do update set storage_path=excluded.storage_path,status='archived',metadata=excluded.metadata,archived_at=coalesce(research.artifact_registry.archived_at,now()),imported_at=now()",
        ["github-actions:"+ARTIFACT_ID+":"+SHA,ARTIFACT_ID,SHA,body.length,WORKFLOW_RUN,CODE_COMMIT,BUNDLE_PATH,JSON.stringify({dataset_id:TRAJ,protocol_key:PROTOCOL,trajectory_fingerprint:TRAJ_FP})]
      );

      const specs=[["interval_prior","interval_time_only_prior_v1"]];
      for(const v of VARIANTS){specs.push(["multinomial_logistic",v]);specs.push(["hist_gradient_boosting",v]);}
      const runIds={};
      for(const [family,variant] of specs){
        const config={
          round:"final-v1-round4",protocol_key:PROTOCOL,trajectory_fingerprint:TRAJ_FP,
          source_training_dataset_id:SOURCE_DATASET,split_scenario:"person_hash_v1",
          model_family:family,feature_variant:variant,seed:SEED,class_weight:null,
          intervals_years:[[0,1],[1,3],[3,5],[5,10],[10,20]],
          hgb:family==="hist_gradient_boosting"?{learning_rate:0.05,max_iter:250,max_leaf_nodes:15,min_samples_leaf:30,l2_regularization:2,early_stopping:false}:null,
          logistic:family==="multinomial_logistic"?{C:1,solver:"lbfgs",max_iter:5000}:null
        };
        const rows=await sql.unsafe(
          "insert into research.model_runs(training_dataset_id,run_key,model_family,feature_variant,split_scenario_key,code_commit,random_seed,config,environment,status,notes,started_at,finished_at) "+
          "values($1::uuid,$2,$3,$4,'person_hash_v1',$5,$6,$7::jsonb,$8::jsonb,'completed',$9,$10::timestamptz,$11::timestamptz) "+
          "on conflict(run_key) do update set config=excluded.config,environment=excluded.environment,status='completed',code_commit=excluded.code_commit,random_seed=excluded.random_seed,notes=excluded.notes,started_at=excluded.started_at,finished_at=excluded.finished_at returning id::text",
          [TRAJ,runKey(family,variant),family,variant,CODE_COMMIT,SEED,JSON.stringify(config),JSON.stringify(summary.environment),
           "Final v1 Round 4 censor-aware discrete-hazard trajectory benchmark; no Round4 hyperparameter selection or class balancing.",
           "2026-10-06T07:01:19Z","2026-10-06T07:08:12Z"]
        );
        runIds[family+"|"+variant]=rows[0].id;
      }

      const im=parseCsv(await zipText(zip,"round4-results/interval_metrics.csv"));
      const metricKeys=["n","accuracy","balanced_accuracy","macro_f1","log_loss","brier_multiclass","ece_10bin","event_vs_no_event_brier","n_event","conditional_domain_log_loss","conditional_domain_macro_f1"];
      for(const r of im){
        const rid=runIds[r.model_family+"|"+r.feature_variant];
        const det=JSON.parse(r.details||"{}");
        for(const k of metricKeys){
          if(r[k]===null||r[k]===undefined||r[k]==="")continue;
          await sql.unsafe(
            "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) values($1::uuid,$2,$3,$4,$5::jsonb) "+
            "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value,details=excluded.details",
            [rid,r.split_name,k,Number(r[k]),JSON.stringify(k==="n"||k==="n_event"?{}:det)]
          );
        }
      }
      const hm=parseCsv(await zipText(zip,"round4-results/horizon_metrics.csv"));
      const hKeys=["n","accuracy","balanced_accuracy","macro_f1","log_loss","brier_multiclass","ece_10bin","event_vs_no_event_brier","n_event","conditional_domain_log_loss","conditional_domain_macro_f1"];
      for(const r of hm){
        const rid=runIds[r.model_family+"|"+r.feature_variant];
        const det=JSON.parse(r.details||"{}");
        for(const k of hKeys){
          if(r[k]===null||r[k]===undefined||r[k]==="")continue;
          const mk="horizon_"+Number(r.horizon_years)+"y__"+k;
          await sql.unsafe(
            "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) values($1::uuid,$2,$3,$4,$5::jsonb) "+
            "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value,details=excluded.details",
            [rid,r.split_name,mk,Number(r[k]),JSON.stringify({horizon_years:Number(r.horizon_years),per_class:k==="n"||k==="n_event"?{}:det})]
          );
        }
      }

      const cmp=summary.paired_person_bootstrap_test;
      const comps=[
        ["history_plus_bazi_minus_history","history_plus_bazi_v1","history_reality_v1"],
        ["bazi_minus_raw_calendar","bazi_objective_only_v1","raw_birth_calendar_v1"],
        ["bazi_minus_placebo","bazi_objective_only_v1","bazi_decade_shuffle_placebo_v1"]
      ];
      for(const family of ["multinomial_logistic","hist_gradient_boosting"]){
        for(const [ck,first,second] of comps){
          const d=cmp[family][ck];
          const rid=runIds[family+"|"+first];
          for(const key of ["delta_log_loss","delta_brier"]){
            await sql.unsafe(
              "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) values($1::uuid,'test',$2,$3,$4::jsonb) "+
              "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value,details=excluded.details",
              [rid,"paired_"+ck+"__"+key,Number(d[key]),JSON.stringify({...d,first_variant:first,second_variant:second})]
            );
          }
        }
      }

      for(const [family,variant] of specs){
        const rid=runIds[family+"|"+variant];
        const common=[
          ["benchmark_bundle_zip","storage://research-artifacts/"+BUNDLE_PATH,SHA,{artifact_id:ARTIFACT_ID,workflow_run:WORKFLOW_RUN}],
          ["round4_summary_json","storage://research-artifacts/"+BUNDLE_PATH+"#round4-results/round4_summary.json",checksums["round4_summary.json"],{round:"final-v1-round4"}]
        ];
        if(family==="interval_prior"){
          common.push(["interval_prior_json","storage://research-artifacts/"+BUNDLE_PATH+"#round4-results/interval_prior.json",checksums["interval_prior.json"],{}]);
        }else{
          const rel="models/"+family+"__"+variant+".joblib";
          common.push(["model_joblib","storage://research-artifacts/"+BUNDLE_PATH+"#round4-results/"+rel,checksums[rel],{family,variant}]);
        }
        for(const a of common){
          await sql.unsafe(
            "insert into research.model_artifacts(run_id,artifact_type,uri,sha256,metadata) values($1::uuid,$2,$3,$4,$5::jsonb) "+
            "on conflict(run_id,artifact_type,sha256) do update set uri=excluded.uri,metadata=excluded.metadata",
            [rid,a[0],a[1],a[2],JSON.stringify(a[3])]
          );
        }
      }

      await sql.unsafe("update research.model_runs set config=(config #>> '{}')::jsonb where run_key like 'final-v1-r4-person-hash-%' and jsonb_typeof(config)='string'");
      await sql.unsafe("update research.model_runs set environment=(environment #>> '{}')::jsonb where run_key like 'final-v1-r4-person-hash-%' and jsonb_typeof(environment)='string'");
      await sql.unsafe("update research.model_metrics mm set details=(details #>> '{}')::jsonb from research.model_runs mr where mm.run_id=mr.id and mr.run_key like 'final-v1-r4-person-hash-%' and jsonb_typeof(mm.details)='string'");
      await sql.unsafe("update research.model_artifacts ma set metadata=(metadata #>> '{}')::jsonb from research.model_runs mr where ma.run_id=mr.id and mr.run_key like 'final-v1-r4-person-hash-%' and jsonb_typeof(ma.metadata)='string'");
      await sql.unsafe("update research.artifact_registry set metadata=(metadata #>> '{}')::jsonb where provider_artifact_id=$1 and jsonb_typeof(metadata)='string'",[ARTIFACT_ID]);

      await sql.end({timeout:5});
      return Response.json({ok:true,mode,sha256:actual,run_ids:runIds,storage_path:BUNDLE_PATH});
    }

    if(mode==="interval"||mode==="horizon"){
      const bytes=await storageDownload();
      const actual=hex(await crypto.subtle.digest("SHA-256",bytes));
      if(actual!==SHA)throw new Error("stored sha mismatch");
      const zip=await JSZip.loadAsync(bytes);
      const path=mode==="interval"?"round4-results/interval_predictions.csv.gz":"round4-results/horizon_predictions.csv.gz";
      const gz=await zipBytes(zip,path);
      const runIds=await getRunIds(sql);
      let header=null,rowIndex=0,inserted=0,batch=[];
      for await (const line of gzipLines(gz)){
        if(!line)continue;
        if(!header){header=parseSimple(line);continue;}
        if(rowIndex>=end)break;
        if(rowIndex++<start)continue;
        const a=parseSimple(line);
        const r={}; for(let i=0;i<header.length;i++)r[header[i]]=a[i]??"";
        const rid=runIds.get(r.model_family+"|"+r.feature_variant);
        if(!rid)throw new Error("missing run id "+r.model_family+" "+r.feature_variant);
        const probs={
          career:Number(r.p_career),no_event:Number(r.p_no_event),other:Number(r.p_other),
          recognition:Number(r.p_recognition),relationship:Number(r.p_relationship)
        };
        if(mode==="interval"){
          batch.push({
            run_id:rid,person_period_id:Number(r.person_period_id),
            source_training_example_id:Number(r.source_training_example_id),
            split_name:r.split_name,interval_index:Number(r.interval_index),
            outcome_true:r.y_true,outcome_pred:r.y_pred,probabilities:probs,
            event_probability:1-Number(r.p_no_event),
            metadata:{round:"final-v1-round4",person_id:Number(r.person_id)}
          });
          if(batch.length>=2500){
            await insertJsonBatch(sql,
              "insert into research.trajectory_model_predictions(run_id,person_period_id,source_training_example_id,split_name,interval_index,outcome_true,outcome_pred,probabilities,event_probability,metadata) "+
              "select x.run_id::uuid,x.person_period_id,x.source_training_example_id,x.split_name,x.interval_index,x.outcome_true,x.outcome_pred,x.probabilities,x.event_probability,x.metadata "+
              "from jsonb_to_recordset($JSON) as x(run_id text,person_period_id bigint,source_training_example_id bigint,split_name text,interval_index int,outcome_true text,outcome_pred text,probabilities jsonb,event_probability double precision,metadata jsonb) "+
              "on conflict(run_id,person_period_id) do update set outcome_pred=excluded.outcome_pred,probabilities=excluded.probabilities,event_probability=excluded.event_probability,metadata=excluded.metadata",
              batch);
            inserted+=batch.length;batch=[];
          }
        }else{
          batch.push({
            run_id:rid,source_training_example_id:Number(r.source_training_example_id),
            person_id:Number(r.person_id),split_name:r.split_name,horizon_years:Number(r.horizon_years),
            evaluable:String(r.evaluable).toLowerCase()==="true",
            y_true:r.y_true||null,probabilities:probs,
            survival_probability:Number(r.survival_probability),
            metadata:{round:"final-v1-round4"}
          });
          if(batch.length>=2500){
            await insertJsonBatch(sql,
              "insert into research.trajectory_horizon_predictions(run_id,source_training_example_id,person_id,split_name,horizon_years,evaluable,y_true,probabilities,survival_probability,metadata) "+
              "select x.run_id::uuid,x.source_training_example_id,x.person_id,x.split_name,x.horizon_years,x.evaluable,x.y_true,x.probabilities,x.survival_probability,x.metadata "+
              "from jsonb_to_recordset($JSON) as x(run_id text,source_training_example_id bigint,person_id bigint,split_name text,horizon_years int,evaluable boolean,y_true text,probabilities jsonb,survival_probability double precision,metadata jsonb) "+
              "on conflict(run_id,source_training_example_id,horizon_years) do update set evaluable=excluded.evaluable,y_true=excluded.y_true,probabilities=excluded.probabilities,survival_probability=excluded.survival_probability,metadata=excluded.metadata",
              batch);
            inserted+=batch.length;batch=[];
          }
        }
      }
      if(batch.length){
        if(mode==="interval"){
          await insertJsonBatch(sql,
            "insert into research.trajectory_model_predictions(run_id,person_period_id,source_training_example_id,split_name,interval_index,outcome_true,outcome_pred,probabilities,event_probability,metadata) "+
            "select x.run_id::uuid,x.person_period_id,x.source_training_example_id,x.split_name,x.interval_index,x.outcome_true,x.outcome_pred,x.probabilities,x.event_probability,x.metadata "+
            "from jsonb_to_recordset($JSON) as x(run_id text,person_period_id bigint,source_training_example_id bigint,split_name text,interval_index int,outcome_true text,outcome_pred text,probabilities jsonb,event_probability double precision,metadata jsonb) "+
            "on conflict(run_id,person_period_id) do update set outcome_pred=excluded.outcome_pred,probabilities=excluded.probabilities,event_probability=excluded.event_probability,metadata=excluded.metadata",
            batch);
        }else{
          await insertJsonBatch(sql,
            "insert into research.trajectory_horizon_predictions(run_id,source_training_example_id,person_id,split_name,horizon_years,evaluable,y_true,probabilities,survival_probability,metadata) "+
            "select x.run_id::uuid,x.source_training_example_id,x.person_id,x.split_name,x.horizon_years,x.evaluable,x.y_true,x.probabilities,x.survival_probability,x.metadata "+
            "from jsonb_to_recordset($JSON) as x(run_id text,source_training_example_id bigint,person_id bigint,split_name text,horizon_years int,evaluable boolean,y_true text,probabilities jsonb,survival_probability double precision,metadata jsonb) "+
            "on conflict(run_id,source_training_example_id,horizon_years) do update set evaluable=excluded.evaluable,y_true=excluded.y_true,probabilities=excluded.probabilities,survival_probability=excluded.survival_probability,metadata=excluded.metadata",
            batch);
        }
        inserted+=batch.length;
      }
      await sql.end({timeout:5});
      return Response.json({ok:true,mode,start,end,inserted});
    }

    if(mode==="verify"){
      const rows=await sql.unsafe(
        "select "+
        "(select count(*)::int from research.model_runs where run_key like 'final-v1-r4-person-hash-%') runs,"+
        "(select count(*)::int from research.trajectory_model_predictions p join research.model_runs r on r.id=p.run_id where r.run_key like 'final-v1-r4-person-hash-%') interval_predictions,"+
        "(select count(*)::int from research.trajectory_horizon_predictions p join research.model_runs r on r.id=p.run_id where r.run_key like 'final-v1-r4-person-hash-%') horizon_predictions,"+
        "(select count(*)::int from research.model_metrics m join research.model_runs r on r.id=m.run_id where r.run_key like 'final-v1-r4-person-hash-%') metrics,"+
        "(select count(*)::int from research.model_artifacts a join research.model_runs r on r.id=a.run_id where r.run_key like 'final-v1-r4-person-hash-%') artifacts"
      );
      await sql.end({timeout:5});
      return Response.json({ok:true,mode,...rows[0]});
    }

    throw new Error("invalid mode");
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e?.stack||e)},{status:500});
  }
});
