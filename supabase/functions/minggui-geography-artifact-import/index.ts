
import JSZip from "npm:jszip@3.10.1";
import Papa from "npm:papaparse@5.4.1";
import postgres from "npm:postgres@3.4.5";

const SNAPSHOT_ID="42628250-3a51-4b92-b4bd-12c7dec846a8";
const ARTIFACT_ID="11332916920";
const RUN_ID="37280764744";
const ARTIFACT_NAME="minggui-timed-core-geography";
const EXPECTED_SHA="2f7e8aed9dcd79b59da8450db9dcb626599205719737eb807519280b67db7210";
const FEATURE_VERSION="present-day-wikidata-geo-v1";

const nil=(v)=>v===undefined||v===null||v===""||v==="nan"||v==="NaN"?null:v;
const num=(v)=>{const x=Number(v);return Number.isFinite(x)?x:null;};
const bool=(v)=>String(v||"").toLowerCase()==="true";
const split=(v)=>String(v||"").split("|").map(x=>x.trim()).filter(Boolean);
const hex=(buf)=>Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,"0")).join("");
const chunks=(a,n)=>Array.from({length:Math.ceil(a.length/n)},(_,i)=>a.slice(i*n,(i+1)*n));

async function gunzipText(bytes){
  const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return await new Response(stream).text();
}
async function findCsv(zip,suffix){
  const path=Object.keys(zip.files).find(p=>p.endsWith(suffix));
  if(!path)throw new Error("missing "+suffix);
  const text=await gunzipText(await zip.file(path).async("uint8array"));
  const p=Papa.parse(text,{header:true,skipEmptyLines:true});
  if(p.errors?.length)throw new Error("csv parse errors: "+JSON.stringify(p.errors.slice(0,3)));
  return p.data;
}
async function archive(bytes,sha){
  const url=Deno.env.get("SUPABASE_URL");
  const legacy=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const secretJson=Deno.env.get("SUPABASE_SECRET_KEYS");
  let secret=legacy;
  if(secretJson){try{secret=JSON.parse(secretJson)?.default||secret;}catch{}}
  if(!url||!secret)throw new Error("missing Supabase server-side storage credentials");
  const path=`github-actions/${ARTIFACT_ID}-${sha}.zip`;
  const res=await fetch(`${url}/storage/v1/object/research-artifacts/${path}`,{
    method:"POST",
    headers:{
      "Authorization":`Bearer ${secret}`,"apikey":secret,
      "Content-Type":"application/zip","x-upsert":"true"
    },
    body:bytes
  });
  const text=await res.text();
  if(!res.ok)throw new Error(`artifact archive failed ${res.status}: ${text}`);
  return path;
}
async function execBatches(sql,query,rows,size=300){
  for(const batch of chunks(rows,size)){
    const payload=JSON.stringify(batch).replaceAll("'","''");
    await sql.unsafe(query.replace("$1::jsonb","'"+payload+"'::jsonb"));
  }
}

Deno.serve(async(req)=>{
  if(req.method!=="POST")return new Response("POST only",{status:405});
  const db=Deno.env.get("SUPABASE_DB_URL");
  if(!db)return new Response("missing SUPABASE_DB_URL",{status:500});
  const sql=postgres(db,{prepare:false,max:1});
  try{
    const bytes=new Uint8Array(await req.arrayBuffer());
    const sha=hex(await crypto.subtle.digest("SHA-256",bytes));
    if(sha!==EXPECTED_SHA){
      await sql.end({timeout:2});
      return Response.json({ok:false,error:"sha mismatch",sha256:sha},{status:400});
    }
    const storagePath=await archive(bytes,sha);
    const zip=await JSZip.loadAsync(bytes);
    const raw=await findCsv(zip,"timed_core_geography.csv.gz");
    if(raw.length!==3093)throw new Error("unexpected geography row count "+raw.length);

    const people=await sql.unsafe(
      "select p.id,p.wikidata_id from research.dataset_membership dm "+
      "join research.people p on p.id=dm.person_id where dm.dataset_snapshot_id=$1::uuid",
      [SNAPSHOT_ID]
    );
    const pmap=new Map(people.map(x=>[x.wikidata_id,Number(x.id)]));
    const rows=[];let unmatched=0;
    for(const r of raw){
      const q=String(r.person_id||"").trim();
      const personId=pmap.get(q);
      if(!personId){unmatched++;continue;}
      rows.push({
        dataset_snapshot_id:SNAPSHOT_ID,person_id:personId,feature_version:FEATURE_VERSION,
        birthplace_qid:nil(r.birthplace_qid),birthplace_label_en:nil(r.birthplace_label_en),
        p19_rank:nil(r.p19_rank),p19_candidate_count:num(r.p19_candidate_count),
        wikidata_latitude:num(r.wikidata_latitude),wikidata_longitude:num(r.wikidata_longitude),
        present_day_country_qid:nil(r.present_day_country_qid),
        present_day_country_label_en:nil(r.present_day_country_label_en),
        country_resolution:nil(r.country_resolution),
        admin_parent_qids:split(r.admin_parent_qids),timezone_qids:split(r.timezone_qids),
        astro_place:nil(r.astro_place),astro_country_raw:nil(r.astro_country_raw),
        astro_latitude:num(r.astro_latitude),astro_longitude:num(r.astro_longitude),
        coordinate_delta_km:num(r.coordinate_delta_km),
        geo_primary_eligible:bool(r.geo_primary_eligible),
        country_semantics:nil(r.country_semantics),source_artifact_id:ARTIFACT_ID,
        raw_features:r
      });
    }

    await sql.begin(async tx=>{
      await execBatches(tx,
        "insert into research.geography_feature_sets(dataset_snapshot_id,person_id,feature_version,birthplace_qid,birthplace_label_en,p19_rank,p19_candidate_count,wikidata_latitude,wikidata_longitude,present_day_country_qid,present_day_country_label_en,country_resolution,admin_parent_qids,timezone_qids,astro_place,astro_country_raw,astro_latitude,astro_longitude,coordinate_delta_km,geo_primary_eligible,country_semantics,source_artifact_id,raw_features) "+
        "select x.dataset_snapshot_id::uuid,x.person_id,x.feature_version,x.birthplace_qid,x.birthplace_label_en,x.p19_rank,x.p19_candidate_count,x.wikidata_latitude,x.wikidata_longitude,x.present_day_country_qid,x.present_day_country_label_en,x.country_resolution,x.admin_parent_qids,x.timezone_qids,x.astro_place,x.astro_country_raw,x.astro_latitude,x.astro_longitude,x.coordinate_delta_km,x.geo_primary_eligible,x.country_semantics,x.source_artifact_id,x.raw_features "+
        "from jsonb_to_recordset($1::jsonb) as x(dataset_snapshot_id text,person_id bigint,feature_version text,birthplace_qid text,birthplace_label_en text,p19_rank text,p19_candidate_count integer,wikidata_latitude double precision,wikidata_longitude double precision,present_day_country_qid text,present_day_country_label_en text,country_resolution text,admin_parent_qids text[],timezone_qids text[],astro_place text,astro_country_raw text,astro_latitude double precision,astro_longitude double precision,coordinate_delta_km double precision,geo_primary_eligible boolean,country_semantics text,source_artifact_id text,raw_features jsonb) "+
        "on conflict(dataset_snapshot_id,person_id,feature_version) do update set birthplace_qid=excluded.birthplace_qid,birthplace_label_en=excluded.birthplace_label_en,p19_rank=excluded.p19_rank,p19_candidate_count=excluded.p19_candidate_count,wikidata_latitude=excluded.wikidata_latitude,wikidata_longitude=excluded.wikidata_longitude,present_day_country_qid=excluded.present_day_country_qid,present_day_country_label_en=excluded.present_day_country_label_en,country_resolution=excluded.country_resolution,admin_parent_qids=excluded.admin_parent_qids,timezone_qids=excluded.timezone_qids,astro_place=excluded.astro_place,astro_country_raw=excluded.astro_country_raw,astro_latitude=excluded.astro_latitude,astro_longitude=excluded.astro_longitude,coordinate_delta_km=excluded.coordinate_delta_km,geo_primary_eligible=excluded.geo_primary_eligible,country_semantics=excluded.country_semantics,source_artifact_id=excluded.source_artifact_id,raw_features=excluded.raw_features",
        rows,300
      );

      await tx.unsafe(
        "insert into research.artifact_registry(artifact_key,provider,provider_artifact_id,artifact_name,artifact_kind,sha256,source_workflow_run_id,storage_bucket,storage_path,status,metadata,archived_at,imported_at) "+
        "values($1,'github-actions',$2,$3,'geography-features',$4,$5,'research-artifacts',$6,'imported',jsonb_build_object('input_rows',$7::int,'imported_rows',$8::int,'unmatched_people',$9::int,'feature_version',$10::text),now(),now()) "+
        "on conflict(artifact_key) do update set storage_bucket=excluded.storage_bucket,storage_path=excluded.storage_path,status='imported',archived_at=coalesce(research.artifact_registry.archived_at,now()),imported_at=now(),metadata=excluded.metadata",
        ["github-actions:"+ARTIFACT_ID+":"+sha,ARTIFACT_ID,ARTIFACT_NAME,sha,RUN_ID,storagePath,raw.length,rows.length,unmatched,FEATURE_VERSION]
      );
      await tx.unsafe(
        "update research.dataset_snapshots set metadata=metadata||jsonb_build_object('geography_features',jsonb_build_object('artifact_id',$2::text,'sha256',$3::text,'storage_path',$4::text,'feature_version',$5::text,'rows',$6::int)) where id=$1::uuid",
        [SNAPSHOT_ID,ARTIFACT_ID,"sha256:"+sha,storagePath,FEATURE_VERSION,rows.length]
      );
    });

    const coverage=await sql.unsafe(
      "select cohort_people,geography_rows,geo_primary_eligible,country_resolved,missing_geography_rows from research.snapshot_geography_coverage_v1 where dataset_snapshot_id=$1::uuid",
      [SNAPSHOT_ID]
    );
    await sql.end({timeout:5});
    return Response.json({ok:true,sha256:sha,storage_path:storagePath,input_rows:raw.length,imported_rows:rows.length,unmatched_people:unmatched,coverage:coverage[0]});
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e?.stack||e)},{status:500});
  }
});
