
import JSZip from "npm:jszip@3.10.1";
import Papa from "npm:papaparse@5.4.1";
import postgres from "npm:postgres@3.4.5";

const SNAPSHOT_ID="42628250-3a51-4b92-b4bd-12c7dec846a8";
const CONFIGS={
  "2557ed46d67642b006b6f94de4522cd20504f58c3d5559d40adbddc63d3d7f79":{
    artifactId:"11330336326",runId:"37274161457",name:"minggui-timed-core-family-degree",
    kind:"wikidata-family-degree-enrichment",expectedRows:13724,
    files:["life_events_structured_degree_v2.csv.gz","life_events_family_child_birth.csv.gz"]
  },
  "899477b5cadb53c5f2def382683a2b3ef8f566809f981a9f8777eced61318103":{
    artifactId:"11329995687",runId:"37274738937",name:"minggui-timed-core-founding",
    kind:"wikidata-founding-enrichment",expectedRows:423,
    files:["life_events_founding.csv.gz"]
  },
  "8e555e92b826a2b778dff2fad73cc1bbf64661dcc02089743ef10464681f39a0":{
    artifactId:"11329902983",runId:"37274241572",name:"minggui-timed-core-notable-work",
    kind:"wikidata-notable-work-enrichment",expectedRows:1163,
    files:["life_events_notable_work.csv.gz"]
  }
};

const nil=(v)=>v===undefined||v===null||v===""||v==="nan"||v==="NaN"?null:v;
const chunks=(a,n)=>Array.from({length:Math.ceil(a.length/n)},(_,i)=>a.slice(i*n,(i+1)*n));
const hex=(buf)=>Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,"0")).join("");
const num=(v)=>{const x=Number(v);return Number.isFinite(x)?x:null;};

async function gunzipText(bytes){
  const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return await new Response(stream).text();
}
async function findCsv(zip,suffix){
  const path=Object.keys(zip.files).find(p=>p.endsWith(suffix));
  if(!path) throw new Error("missing "+suffix);
  const text=await gunzipText(await zip.file(path).async("uint8array"));
  const p=Papa.parse(text,{header:true,skipEmptyLines:true});
  if(p.errors?.length) throw new Error("csv parse errors "+suffix+": "+JSON.stringify(p.errors.slice(0,3)));
  return p.data;
}
async function archiveArtifactToStorage(bytes,artifactId,sha256){
  const url=Deno.env.get("SUPABASE_URL");
  const legacy=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const secretJson=Deno.env.get("SUPABASE_SECRET_KEYS");
  let secret=legacy;
  if(secretJson){try{secret=JSON.parse(secretJson)?.default||secret;}catch{}}
  if(!url||!secret) throw new Error("missing Supabase server-side storage credentials");
  const path=`github-actions/${artifactId}-${sha256}.zip`;
  const res=await fetch(`${url}/storage/v1/object/research-artifacts/${path}`,{
    method:"POST",
    headers:{
      "Authorization":`Bearer ${secret}`,"apikey":secret,
      "Content-Type":"application/zip","x-upsert":"true"
    },
    body:bytes
  });
  const bodyText=await res.text();
  if(!res.ok) throw new Error(`artifact archive failed ${res.status}: ${bodyText}`);
  return path;
}
async function execBatches(sql,query,rows,size=300){
  for(const batch of chunks(rows,size)){
    const payload=JSON.stringify(batch).replaceAll("'","''");
    await sql.unsafe(query.replace("$1::jsonb","'"+payload+"'::jsonb"));
  }
}
function parseAttrs(r,file){
  let a={};
  try{a=r.attributes_json?JSON.parse(r.attributes_json):{};}catch{a={raw_attributes_json:r.attributes_json};}
  for(const k of ["calendar_kind","source_time_raw","statement_rank","qualifier_kind"]){
    if(nil(r[k])!==null)a[k]=r[k];
  }
  a.artifact_file=file;
  return a;
}

Deno.serve(async(req)=>{
  if(req.method!=="POST")return new Response("POST only",{status:405});
  const db=Deno.env.get("SUPABASE_DB_URL");
  if(!db)return new Response("missing SUPABASE_DB_URL",{status:500});
  const sql=postgres(db,{prepare:false,max:1});
  try{
    const bytes=new Uint8Array(await req.arrayBuffer());
    const sha=hex(await crypto.subtle.digest("SHA-256",bytes));
    const cfg=CONFIGS[sha];
    if(!cfg){
      await sql.end({timeout:2});
      return Response.json({ok:false,error:"unapproved artifact sha",sha256:sha},{status:400});
    }
    const storagePath=await archiveArtifactToStorage(bytes,cfg.artifactId,sha);
    const zip=await JSZip.loadAsync(bytes);
    const rawRows=[];
    for(const file of cfg.files){
      const rows=await findCsv(zip,file);
      for(const r of rows)rawRows.push({...r,__artifact_file:file});
    }
    if(rawRows.length!==cfg.expectedRows)throw new Error(`unexpected row count ${rawRows.length}, expected ${cfg.expectedRows}`);

    const people=await sql.unsafe(
      "select psf.person_id,p.wikidata_id,psf.birth_date::text from research.person_snapshot_facts psf "+
      "join research.people p on p.id=psf.person_id where psf.dataset_snapshot_id=$1::uuid",[SNAPSHOT_ID]);
    const pmap=new Map(people.map(x=>[x.wikidata_id,{id:Number(x.person_id),birth:x.birth_date}]));

    const eventMap=new Map();
    let unmatchedPeople=0,negativeAge=0,invalidTime=0;
    for(const r of rawRows){
      const q=String(r.person_id||"").trim();
      const person=pmap.get(q);
      if(!person){unmatchedPeople++;continue;}
      const key=String(r.event_id||"").trim();
      if(!key)continue;
      const amin=num(r.age_min),amax=num(r.age_max),amid=num(r.age_mid);
      const d0=nil(r.event_date_min),d1=nil(r.event_date_max),obs=nil(r.observable_from);
      const prebirth=amax!==null&&amax<0;
      if(prebirth)negativeAge++;
      const timeOk=Boolean(d0&&d1&&obs);
      if(!timeOk)invalidTime++;
      const attrs=parseAttrs(r,r.__artifact_file);
      if(nil(r.subject_id)!==null)attrs.subject_id=r.subject_id;
      attrs.artifact_id=cfg.artifactId;
      const evt={
        event_key:key,person_id:person.id,domain:String(r.domain||"other"),event_type:String(r.event_type||"other"),
        event_date_min:d0,event_date_max:d1,temporal_precision:nil(r.temporal_precision)||"unknown",
        calendar_kind:nil(r.calendar_kind),age_min:amin,age_max:amax,age_mid:amid,
        observable_from:obs,subject_external_id:nil(r.subject_id),source_family:"wikidata",
        extraction_method:nil(r.extraction_method)||"structured",
        confidence:num(r.confidence),source_rank:nil(r.statement_rank)||"structured",
        reference_count:num(r.reference_count)===null?1:Math.trunc(num(r.reference_count)),
        qualifier_kind:nil(r.qualifier_kind),attributes:attrs,source_snapshot_id:SNAPSHOT_ID,
        source_url:nil(r.source_url),model_eligible:timeOk&&!prebirth,
        quality_flags:prebirth?{prebirth_interval:true}:(!timeOk?{invalid_source_time:true}:{})
      };
      if(!eventMap.has(key))eventMap.set(key,evt);
      else{
        const old=eventMap.get(key);
        old.attributes={...old.attributes,duplicate_artifact_files:[old.attributes.artifact_file,r.__artifact_file]};
      }
    }
    const events=[...eventMap.values()];
    const sourceKey=`github-actions:${cfg.artifactId}:structured-events`;

    await sql.begin(async tx=>{
      await tx.unsafe(
        "insert into research.source_records(source_key,source_type,source_family,publisher,title,dataset_version,license_bucket,license_url,independence_group,metadata) "+
        "values($1,'dataset-artifact','wikidata','Wikidata / Wikimedia',$2,$3,'CC0','https://creativecommons.org/publicdomain/zero/1.0/','wikimedia',jsonb_build_object('artifact_id',$4::text,'workflow_run_id',$5::text,'files',$6::jsonb,'sha256',$7::text,'storage_path',$8::text)) "+
        "on conflict(source_key) do update set dataset_version=excluded.dataset_version,metadata=research.source_records.metadata||excluded.metadata",
        [sourceKey,cfg.name,"github-actions-artifact:"+cfg.artifactId,cfg.artifactId,cfg.runId,JSON.stringify(cfg.files),sha,storagePath]
      );
      const sr=await tx.unsafe("select id from research.source_records where source_key=$1",[sourceKey]);
      const sourceRecordId=Number(sr[0].id);

      await execBatches(tx,
        "insert into research.life_events(event_key,person_id,domain,event_type,event_date_min,event_date_max,temporal_precision,calendar_kind,age_min,age_max,age_mid,observable_from,subject_external_id,source_family,extraction_method,confidence,source_rank,reference_count,qualifier_kind,attributes,source_snapshot_id,source_url,model_eligible,quality_flags) "+
        "select x.event_key,x.person_id,x.domain,x.event_type,x.event_date_min::date,x.event_date_max::date,x.temporal_precision,x.calendar_kind,x.age_min,x.age_max,x.age_mid,x.observable_from::date,x.subject_external_id,x.source_family,x.extraction_method,x.confidence,x.source_rank,x.reference_count,x.qualifier_kind,x.attributes,x.source_snapshot_id::uuid,x.source_url,x.model_eligible,x.quality_flags "+
        "from jsonb_to_recordset($1::jsonb) as x(event_key text,person_id bigint,domain text,event_type text,event_date_min text,event_date_max text,temporal_precision text,calendar_kind text,age_min double precision,age_max double precision,age_mid double precision,observable_from text,subject_external_id text,source_family text,extraction_method text,confidence double precision,source_rank text,reference_count integer,qualifier_kind text,attributes jsonb,source_snapshot_id text,source_url text,model_eligible boolean,quality_flags jsonb) "+
        "on conflict(event_key) do update set attributes=research.life_events.attributes||excluded.attributes,confidence=greatest(research.life_events.confidence,excluded.confidence),source_url=coalesce(research.life_events.source_url,excluded.source_url)",
        events,250);

      const ids=await tx.unsafe(
        "select id,event_key,model_eligible from research.life_events where event_key=any($1::text[])",
        [events.map(e=>e.event_key)]
      );
      const idMap=new Map(ids.map(x=>[x.event_key,{id:Number(x.id),eligible:Boolean(x.model_eligible)}]));
      const evidence=[],members=[];
      for(const e of events){
        const got=idMap.get(e.event_key);if(!got)continue;
        evidence.push({
          event_id:got.id,source_record_id:sourceRecordId,evidence_locator:e.event_key,
          confidence:e.confidence,metadata:{artifact_id:cfg.artifactId,subject_external_id:e.subject_external_id,source_url:e.source_url,artifact_file:e.attributes.artifact_file}
        });
        members.push({
          dataset_snapshot_id:SNAPSHOT_ID,event_id:got.id,inclusion_role:"direct-enrichment",
          snapshot_model_eligible:got.eligible,
          exclusion_reason:got.eligible?null:"intrinsic_model_ineligible",
          metadata:{artifact_id:cfg.artifactId,artifact_kind:cfg.kind,source_family:"wikidata"}
        });
      }
      await execBatches(tx,
        "insert into research.event_evidence(event_id,source_record_id,evidence_locator,confidence,metadata) "+
        "select x.event_id,x.source_record_id,x.evidence_locator,x.confidence,x.metadata "+
        "from jsonb_to_recordset($1::jsonb) as x(event_id bigint,source_record_id bigint,evidence_locator text,confidence double precision,metadata jsonb) "+
        "on conflict(event_id,source_record_id,evidence_locator) do update set confidence=greatest(research.event_evidence.confidence,excluded.confidence),metadata=research.event_evidence.metadata||excluded.metadata",
        evidence,300);
      await execBatches(tx,
        "insert into research.dataset_event_membership(dataset_snapshot_id,event_id,inclusion_role,snapshot_model_eligible,exclusion_reason,metadata) "+
        "select x.dataset_snapshot_id::uuid,x.event_id,x.inclusion_role,x.snapshot_model_eligible,x.exclusion_reason,x.metadata "+
        "from jsonb_to_recordset($1::jsonb) as x(dataset_snapshot_id text,event_id bigint,inclusion_role text,snapshot_model_eligible boolean,exclusion_reason text,metadata jsonb) "+
        "on conflict(dataset_snapshot_id,event_id) do update set metadata=research.dataset_event_membership.metadata||excluded.metadata",
        members,350);

      await tx.unsafe(
        "update research.dataset_snapshots set event_count=(select count(*) from research.dataset_event_membership where dataset_snapshot_id=$1::uuid),status='identity-final-events-enriching',metadata=metadata||jsonb_build_object($2::text,jsonb_build_object('artifact_id',$3::text,'sha256',$4::text,'storage_path',$5::text,'input_rows',$6::int,'unique_event_keys',$7::int)) where id=$1::uuid",
        [SNAPSHOT_ID,cfg.kind,cfg.artifactId,"sha256:"+sha,storagePath,rawRows.length,events.length]
      );
      await tx.unsafe(
        "insert into research.artifact_registry(artifact_key,provider,provider_artifact_id,artifact_name,artifact_kind,sha256,source_workflow_run_id,storage_bucket,storage_path,status,metadata,archived_at,imported_at) "+
        "values($1,'github-actions',$2,$3,$4,$5,$6,'research-artifacts',$7,'imported',jsonb_build_object('input_rows',$8::int,'unique_event_keys',$9::int,'unmatched_people',$10::int,'negative_age_rows',$11::int,'invalid_time_rows',$12::int,'files',$13::jsonb),now(),now()) "+
        "on conflict(artifact_key) do update set storage_bucket=excluded.storage_bucket,storage_path=excluded.storage_path,status='imported',archived_at=coalesce(research.artifact_registry.archived_at,now()),imported_at=now(),metadata=excluded.metadata",
        ["github-actions:"+cfg.artifactId+":"+sha,cfg.artifactId,cfg.name,cfg.kind,sha,cfg.runId,storagePath,rawRows.length,events.length,unmatchedPeople,negativeAge,invalidTime,JSON.stringify(cfg.files)]
      );
    });

    const summary=await sql.unsafe(
      "select (select count(*)::int from research.dataset_event_membership where dataset_snapshot_id=$1::uuid) snapshot_events,"+
      "(select count(distinct e.person_id)::int from research.dataset_event_membership dem join research.life_events e on e.id=dem.event_id where dem.dataset_snapshot_id=$1::uuid) snapshot_people_with_events",
      [SNAPSHOT_ID]
    );
    await sql.end({timeout:5});
    return Response.json({ok:true,artifact_id:cfg.artifactId,kind:cfg.kind,sha256:sha,storage_path:storagePath,input_rows:rawRows.length,unique_event_keys:events.length,unmatched_people:unmatchedPeople,negative_age_rows:negativeAge,invalid_time_rows:invalidTime,summary:summary[0]});
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e?.stack||e)},{status:500});
  }
});
