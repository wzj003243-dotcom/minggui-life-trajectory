import postgres from "npm:postgres@3.4.5";
import JSZip from "npm:jszip@3.10.1";

const ARTIFACT_ID="11536022737";
const ARTIFACT_SHA="7df20c54887b76094f4d3428b227b623d779aea35644a3d4925aa1296749f00a";
const SOURCE_RUN="37747038831";
const SOURCE_COMMIT="95977ced16a2d3878ab1fb1ee5b6fef578297fc0";
const DATASET="36486fe4-a961-4f84-b3ee-11bdf978ea1b";
const DATA_FINGERPRINT="fb8f6be67a5dba22a3bc3fdbf2f799f946c5755a2b08d44528138fd88b8e6443";
const SOURCE_SNAPSHOT="7fce3b79-ebfc-40b2-a5f0-e91b28db6a02";
const SNAPSHOT_SHA="2af1167d562c83789c0eaa0c0f7b793706ce2e17e9273c8c22450f80791dc5cf";
const BUCKET="research-artifacts";
const PATH="model-runs/v11-round5/"+ARTIFACT_SHA+"/bundle.zip";
const BASE="v11-round5-results/";

async function sha(bytes:Uint8Array){
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256",bytes))]
    .map(v=>v.toString(16).padStart(2,"0")).join("");
}
async function githubAuth(req:Request){
  const token=req.headers.get("Authorization")||"";
  if(!/^Bearer [a-zA-Z0-9_.-]+$/.test(token))return false;
  try{
    const response=await fetch("https://api.github.com/repos/wzj003243-dotcom/minggui-life-trajectory/actions/runs/"+SOURCE_RUN,{
      headers:{"Authorization":token,"Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28","User-Agent":"MingGui-v11-round5-archive"},
      signal:AbortSignal.timeout(8000)
    });
    if(!response.ok)return false;
    const r=await response.json();
    return String(r.id)===SOURCE_RUN&&r.conclusion==="success"
      &&r.head_sha===SOURCE_COMMIT;
  }catch{return false;}
}
function string(v:unknown){return JSON.stringify(v);}
function parseCsv(text:string){
  // Escaped details JSON is the final CSV column. Only the first 14 scalar
  // columns are needed for the horizon metrics.
  const lines=text.trim().split(/\r?\n/);
  const columns=lines.shift()!.split(",");
  const out:any[]=[];
  for(const line of lines){
    const fields=line.split(",");
    const row:any={};
    for(let i=0;i<columns.length-1;i++)row[columns[i]]=fields[i];
    out.push(row);
  }
  return out;
}
function num(n:unknown){const f=Number(n);return Number.isFinite(f)?f:null;}
function detailsVal(obj:any){
  return {protocol:"v11-round5-matched-history-lift-v1",...obj};
}
async function storageKey(){
  let key=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const raw=Deno.env.get("SUPABASE_SECRET_KEYS");
  if(raw){try{key=JSON.parse(raw)?.default||key}catch{}}
  if(!key)throw Error("missing Supabase Storage service key");
  return key;
}

Deno.serve(async(req)=>{
  if(req.method!=="POST")return new Response("POST only",{status:405});
  if(!(await githubAuth(req)))return new Response("authorized Github workflow token required",{status:403});
  if(new URL(req.url).searchParams.get("artifact_id")!==ARTIFACT_ID)
    return new Response("wrong artifact ID",{status:400});
  const db=Deno.env.get("SUPABASE_DB_URL");
  if(!db)return new Response("missing DB URL",{status:500});
  const sql=postgres(db,{prepare:false,max:1});
  try{
    const bytes=new Uint8Array(await req.arrayBuffer());
    if(await sha(bytes)!==ARTIFACT_SHA)throw Error("archive SHA mismatch");
    const zip=await JSZip.loadAsync(bytes);
    async function jsonEntry(name:string){
      const entry=zip.file(BASE+name);
      if(!entry)throw Error("archive missing "+name);
      return JSON.parse(await entry.async("string"));
    }
    const summary=await jsonEntry("round5_summary.json");
    const checksums=await jsonEntry("SHA256SUMS.json");
    const modelManifest=await jsonEntry("model_manifest.json");
    const horizonContent=await zip.file(BASE+"horizon_metrics.csv")?.async("string");
    if(!horizonContent)throw Error("missing horizon CSV");
    const horizons=parseCsv(horizonContent);
    if(summary.protocol!=="v11-round5-matched-history-lift-v1"||
       summary.source_snapshot_id!==SOURCE_SNAPSHOT||
       summary.source_canonical_sha256!==SNAPSHOT_SHA)
      throw Error("wrong model summary or frozen source");
    if(summary.data_audit?.cutoffs!==13064 ||summary.data_audit?.periods!==49909 ||
       summary.data_audit?.checks!=="passed")
      throw Error("data audit mismatch");
    if(summary.test_metrics?.length!==3||summary.validation_metrics?.length!==3)
      throw Error("model metric arms missing");
    if(horizons.length!==30)throw Error("expected 30 horizon metric rows");
    for(const arm of ["old_history","v11_history"]){
      const rel=modelManifest?.[arm]?.model_file;
      if(rel!==("models/hgb__"+arm+".joblib"))throw Error("unexpected joblib "+arm);
      const blob=await zip.file(BASE+rel)?.async("uint8array");
      if(!blob||await sha(blob)!==checksums[rel])throw Error("model joblib SHA failed "+arm);
    }
    const ds=await sql.unsafe(
      "select status,fingerprint_sha256,source_snapshot_id::text source_snapshot_id "+
      "from research.training_dataset_versions where id=$1::uuid",[DATASET]);
    if(ds.length!==1||ds[0].status!=="frozen"||
       ds[0].fingerprint_sha256!==DATA_FINGERPRINT||
       ds[0].source_snapshot_id!==SOURCE_SNAPSHOT)throw Error("dataset not frozen or wrong fingerprint");
    const snap=await sql.unsafe("select status,canonical_event_sha256 from research.dataset_snapshots where id=$1::uuid",[SOURCE_SNAPSHOT]);
    if(snap[0]?.status!=="frozen"||snap[0]?.canonical_event_sha256!==SNAPSHOT_SHA)
      throw Error("frozen snapshot altered");

    // Archive exact GitHub Actions ZIP before SQL writes.
    const service=await storageKey();
    const storageUrl=Deno.env.get("SUPABASE_URL");
    const uploaded=await fetch(storageUrl+"/storage/v1/object/"+BUCKET+"/"+PATH,{
      method:"POST",headers:{
        Authorization:"Bearer "+service,
        apikey:service,
        "Content-Type":"application/zip",
        "x-upsert":"true"
      },body:bytes
    });
    if(!uploaded.ok)throw Error("storage upload "+uploaded.status+" "+await uploaded.text());

    const names=["interval_prior","old_history","v11_history"];
    const runs:any={};
    await sql.begin(async tx=>{
      for(const arm of names){
        const config={hgb_config:summary.hgb_capacity,model_manifest:modelManifest[arm]||null,
          protocol:summary.protocol,cutoff_rows:13064,period_rows:49909,
          training_dataset_fingerprint:DATA_FINGERPRINT};
        const rows=await tx.unsafe(
          "insert into research.model_runs(training_dataset_id,run_key,model_family,feature_variant,"+
          "split_scenario_key,code_commit,random_seed,config,environment,status,notes,started_at,finished_at) "+
          "values($1::uuid,$2,$3,$4,'person_hash_v1',$5,$6,"+
          "($7::jsonb #>> '{}')::jsonb,($8::jsonb #>> '{}')::jsonb,'completed',$9,now(),now()) "+
          "on conflict(run_key) do update set status='completed',finished_at=now() "+
          "returning id::text id",
          [
            DATASET,"v11-r5-"+ARTIFACT_SHA.slice(0,16)+"-"+arm,
            arm==="interval_prior"?"interval_prior":"hist_gradient_boosting",arm,
            SOURCE_COMMIT,20261006,
            string(config),string(summary.environment),
            "Same frozen v1.1 labels; matched old-history vs v1.1-history, not cross-dataset metric comparison."
          ]
        );
        runs[arm]=rows[0].id;
      }
      for(const m of [...summary.validation_metrics,...summary.test_metrics]){
        const rid=runs[m.arm],sp=m.arm,split=m.arm&&m.arm.length? (summary.test_metrics.includes(m)?"test":"validation"):"";
        for(const [key,val] of Object.entries(m)){
          if(!["n","log_loss","brier_multiclass","ece_10bin","event_vs_no_event_brier",
                "macro_f1","conditional_domain_log_loss","conditional_domain_macro_f1"].includes(key))continue;
          const metricValue=num(val);
          await tx.unsafe(
            "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) "+
            "values($1::uuid,$2,$3,$4,'{}'::jsonb) "+
            "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value",
            [rid,split,"interval_"+key,metricValue]
          );
        }
      }
      for(const h of horizons){
        const rid=runs[h.feature_variant];
        if(!rid)throw Error("unexpected horizon arm "+h.feature_variant);
        const y=parseInt(h.horizon_years,10);
        if(![1,3,5,10,20].includes(y)||!["test","validation"].includes(h.split_name))
          throw Error("invalid horizon row");
        for(const key of ["log_loss","brier_multiclass","event_vs_no_event_brier","macro_f1"]){
          await tx.unsafe(
            "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) "+
            "values($1::uuid,$2,$3,$4,'{}'::jsonb) "+
            "on conflict(run_id,split_name,metric_key) do update set metric_value=excluded.metric_value",
            [rid,h.split_name,"horizon_"+y+"y_"+key,num(h[key])]
          );
        }
      }
      const boot=summary.person_cluster_bootstrap_v11_minus_v10_history;
      for(const key of ["delta_log_loss","delta_brier"]){
        await tx.unsafe(
          "insert into research.model_metrics(run_id,split_name,metric_key,metric_value,details) "+
          "values($1::uuid,'test',$2,$3,($4::jsonb #>> '{}')::jsonb) "+
          "on conflict(run_id,split_name,metric_key) do update set "+
          "metric_value=excluded.metric_value,details=excluded.details",
          [runs.v11_history,"paired_v11_minus_old_"+key,num(boot[key]),string(detailsVal(boot))]
        );
      }
      for(const arm of names){
        const refs=[
          ["model_run_summary",BASE+"round5_summary.json",checksums["round5_summary.json"]],
          ["interval_predictions",BASE+"interval_predictions.csv.gz",checksums["interval_predictions.csv.gz"]],
          ["horizon_predictions",BASE+"horizon_predictions.csv.gz",checksums["horizon_predictions.csv.gz"]],
        ];
        if(arm!=="interval_prior")refs.push([
          "model_joblib",BASE+"models/hgb__"+arm+".joblib",checksums["models/hgb__"+arm+".joblib"]
        ]);
        for(const [type,inner,digest] of refs){
          if(!digest)throw Error("missing inner checksum "+inner);
          const uri="storage://"+BUCKET+"/"+PATH+"#"+inner;
          await tx.unsafe(
            "insert into research.model_artifacts(run_id,artifact_type,uri,sha256,metadata) "+
            "select $1::uuid,$2,$3,$4,($5::jsonb #>> '{}')::jsonb "+
            "where not exists(select 1 from research.model_artifacts where run_id=$1::uuid and artifact_type=$2 and uri=$3)",
            [runs[arm],type,uri,digest,string({bundle_sha256:ARTIFACT_SHA,github_artifact_id:ARTIFACT_ID,inner_path:inner})]
          );
        }
      }
      await tx.unsafe(
        "insert into research.artifact_registry(artifact_key,provider,provider_artifact_id,artifact_name,artifact_kind,"+
        "sha256,size_bytes,source_workflow_run_id,source_git_sha,storage_bucket,storage_path,status,metadata,archived_at,imported_at) "+
        "values($1,'github-actions',$2,$3,'model-run-v11-round5',$4,$5,$6,$7,$8,$9,'imported',"+
        "($10::jsonb #>> '{}')::jsonb,now(),now()) "+
        "on conflict(artifact_key) do update set status='imported',metadata=excluded.metadata,imported_at=now()",
        [
          "github-actions:"+ARTIFACT_ID+":"+ARTIFACT_SHA,ARTIFACT_ID,
          "minggui-v11-round5-matched-history",ARTIFACT_SHA,bytes.length,SOURCE_RUN,SOURCE_COMMIT,
          BUCKET,PATH,string({source_snapshot_id:SOURCE_SNAPSHOT,training_dataset_id:DATASET,
            source_fingerprint:DATA_FINGERPRINT,protocol:summary.protocol,model_run_ids:runs})
        ]
      );
    });
    await sql.end({timeout:5});
    return Response.json({ok:true,artifact_id:ARTIFACT_ID,sha256:ARTIFACT_SHA,
      storage_path:PATH,models:runs,interval_metrics:summary.test_metrics.length,horizon_metric_rows:horizons.length});
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e?.stack||e)},{status:500});
  }
});