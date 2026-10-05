
import JSZip from "npm:jszip@3.10.1";
import Papa from "npm:papaparse@5.4.1";
import postgres from "npm:postgres@3.4.5";

const EXPECTED_SHA="a27cc246669b08dca85d61ff40f73551d24ab1424275537b69214c52c7c49c33";
const SNAPSHOT_ID="42628250-3a51-4b92-b4bd-12c7dec846a8";
const ARTIFACT_ID="11332298618";
const WORKFLOW_RUN_ID="37278695698";
const ARTIFACT_NAME="minggui-timed-core-biography-enrichment";

const nil=(v)=>v===undefined||v===null||v===""||v==="nan"||v==="NaN"?null:v;
const chunks=(a,n)=>Array.from({length:Math.ceil(a.length/n)},(_,i)=>a.slice(i*n,(i+1)*n));
const hex=(buf)=>Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,"0")).join("");
const uniq=(xs)=>[...new Set(xs.filter(Boolean))];

async function gunzipText(bytes){
  const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return await new Response(stream).text();
}
async function findText(zip,suffix){
  const path=Object.keys(zip.files).find(p=>p.endsWith(suffix));
  if(!path) throw new Error("missing "+suffix);
  return await gunzipText(await zip.file(path).async("uint8array"));
}
async function findCsv(zip,suffix){
  const text=await findText(zip,suffix);
  const p=Papa.parse(text,{header:true,skipEmptyLines:true});
  if(p.errors?.length) throw new Error("csv parse errors "+suffix+": "+JSON.stringify(p.errors.slice(0,3)));
  return p.data;
}
function parseYearOnly(raw){
  const years=uniq(String(raw||"").split("|").map(x=>x.trim()).filter(x=>/^\d{4}$/.test(x)));
  if(years.length!==1)return {years,min:null,max:null,precision:"ambiguous"};
  return {years,min:years[0]+"-01-01",max:years[0]+"-12-31",precision:"year"};
}
function ageYears(birth,d){
  if(!birth||!d)return null;
  const a=Date.parse(String(birth).slice(0,10)+"T00:00:00Z");
  const b=Date.parse(String(d).slice(0,10)+"T00:00:00Z");
  if(!Number.isFinite(a)||!Number.isFinite(b))return null;
  return Math.round(((b-a)/86400000/365.2425)*10000)/10000;
}
async function execBatches(sql,query,rows,size=300){
  let done=0;
  for(const batch of chunks(rows,size)){
    const payload=JSON.stringify(batch).replaceAll("'","''");
    await sql.unsafe(query.replace("$1::jsonb","'"+payload+"'::jsonb"));
    done+=batch.length;
  }
  return done;
}
async function archiveArtifactToStorage(bytes,artifactId,sha256){
  const url=Deno.env.get("SUPABASE_URL");
  const legacy=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const secretJson=Deno.env.get("SUPABASE_SECRET_KEYS");
  let secret=legacy;
  if(secretJson){
    try{secret=JSON.parse(secretJson)?.default||secret;}catch{}
  }
  if(!url||!secret) throw new Error("missing Supabase server-side storage credentials");
  const path=`github-actions/${artifactId}-${sha256}.zip`;
  const res=await fetch(`${url}/storage/v1/object/research-artifacts/${path}`,{
    method:"POST",
    headers:{
      "Authorization":`Bearer ${secret}`,
      "apikey":secret,
      "Content-Type":"application/zip",
      "x-upsert":"true"
    },
    body:bytes
  });
  const text=await res.text();
  if(!res.ok) throw new Error(`artifact archive failed ${res.status}: ${text}`);
  return path;
}

Deno.serve(async(req)=>{
  if(req.method!=="POST") return new Response("POST only",{status:405});
  const db=Deno.env.get("SUPABASE_DB_URL");
  if(!db) return new Response("missing SUPABASE_DB_URL",{status:500});
  const sql=postgres(db,{prepare:false,max:1});
  try{
    const body=new Uint8Array(await req.arrayBuffer());
    const actual=hex(await crypto.subtle.digest("SHA-256",body));
    if(actual!==EXPECTED_SHA){
      await sql.end({timeout:2});
      return Response.json({ok:false,error:"sha mismatch",actual},{status:400});
    }
    const storagePath=await archiveArtifactToStorage(body,ARTIFACT_ID,actual);
    const zip=await JSZip.loadAsync(body);
    const candidatesRaw=await findCsv(zip,"biography_candidates_300.csv.gz");
    const rulesRaw=await findCsv(zip,"life_events_wikipedia_rule.csv.gz");
    if(candidatesRaw.length!==6919) throw new Error("unexpected candidate count "+candidatesRaw.length);
    if(rulesRaw.length!==2341) throw new Error("unexpected rule event count "+rulesRaw.length);

    const people=await sql.unsafe(
      "select psf.person_id,p.wikidata_id,psf.birth_date::text "+
      "from research.person_snapshot_facts psf join research.people p on p.id=psf.person_id "+
      "where psf.dataset_snapshot_id=$1::uuid",[SNAPSHOT_ID]);
    const pmap=new Map(people.map(x=>[x.wikidata_id,{id:Number(x.person_id),birth:x.birth_date}]));

    const ruleByCandidate=new Map(rulesRaw.map(r=>[String(r.candidate_id),String(r.event_id)]));
    const revisionMap=new Map();
    let unmatchedCandidatePeople=0;
    for(const r of candidatesRaw){
      const person=pmap.get(String(r.person_id||"").trim());
      if(!person){unmatchedCandidatePeople++;continue;}
      const site=String(r.site||"enwiki").trim()||"enwiki";
      const revision=String(r.revision_id||"").trim();
      const pageid=String(r.pageid||"").trim();
      if(!revision)continue;
      const sourceKey=`wikipedia:${site}:revision:${revision}`;
      if(!revisionMap.has(sourceKey)){
        revisionMap.set(sourceKey,{
          source_key:sourceKey,source_type:"revision-wikitext",source_family:"wikipedia",
          publisher:"Wikipedia / Wikimedia",title:`Wikipedia revision ${revision}`,
          url:nil(r.source_url),dataset_version:"github-actions-artifact:"+ARTIFACT_ID,
          revision_id:revision,revision_timestamp:nil(r.revision_timestamp),
          license_bucket:nil(r.license)||"CC BY-SA",license_url:null,
          independence_group:`wikipedia:${site}:page:${pageid}`,
          metadata:{site,pageid,artifact_id:ARTIFACT_ID,content_mode:"revision main-slot wikitext"}
        });
      }
    }
    const sources=[...revisionMap.values()];

    await sql.begin(async tx=>{
      await execBatches(tx,
        "insert into research.source_records(source_key,source_type,source_family,publisher,title,url,dataset_version,revision_id,revision_timestamp,license_bucket,license_url,independence_group,metadata) "+
        "select x.source_key,x.source_type,x.source_family,x.publisher,x.title,x.url,x.dataset_version,x.revision_id,x.revision_timestamp::timestamptz,x.license_bucket,x.license_url,x.independence_group,x.metadata "+
        "from jsonb_to_recordset($1::jsonb) as x(source_key text,source_type text,source_family text,publisher text,title text,url text,dataset_version text,revision_id text,revision_timestamp text,license_bucket text,license_url text,independence_group text,metadata jsonb) "+
        "on conflict(source_key) do update set url=excluded.url,dataset_version=excluded.dataset_version,revision_timestamp=excluded.revision_timestamp,license_bucket=excluded.license_bucket,independence_group=excluded.independence_group,metadata=research.source_records.metadata||excluded.metadata",
        sources,250);

      const sourceRows=await tx.unsafe("select id,source_key from research.source_records where source_family='wikipedia'");
      const sourceMap=new Map(sourceRows.map(x=>[x.source_key,Number(x.id)]));

      const candidates=[];
      for(const r of candidatesRaw){
        const q=String(r.person_id||"").trim();
        const person=pmap.get(q);
        if(!person)continue;
        const site=String(r.site||"enwiki").trim()||"enwiki";
        const revision=String(r.revision_id||"").trim();
        const sourceKey=`wikipedia:${site}:revision:${revision}`;
        const parsed=parseYearOnly(r.years);
        const domains=uniq(String(r.candidate_domains||"").split("|").map(x=>x.trim()));
        const candidateId=String(r.candidate_id);
        const acceptedEvent=ruleByCandidate.get(candidateId)||null;
        candidates.push({
          candidate_key:"wikipedia:"+candidateId,person_id:person.id,
          source_record_id:sourceMap.get(sourceKey)||null,
          proposed_domain:domains.length===1?domains[0]:null,
          proposed_event_type:null,date_text:nil(r.years),
          event_date_min:parsed.min,event_date_max:parsed.max,
          temporal_precision:parsed.precision,
          evidence_text:String(r.text||""),
          extraction_method:"timeline-candidate-from-revision-text",
          extractor_version:"wikipedia-biography-candidate-v1",
          extractor_confidence:null,
          status:acceptedEvent?"rule-accepted":"candidate",
          metadata:{
            candidate_id:candidateId,site,pageid:nil(r.pageid),revision_id:revision,
            revision_timestamp:nil(r.revision_timestamp),source_url:nil(r.source_url),
            years:parsed.years,ages:nil(r.ages),
            candidate_domains:domains,text_length:Number(r.text_length||0)||null,
            license:nil(r.license)||"CC BY-SA",artifact_id:ARTIFACT_ID,
            accepted_event_key:acceptedEvent
          }
        });
      }
      await execBatches(tx,
        "insert into research.event_candidates(candidate_key,person_id,source_record_id,proposed_domain,proposed_event_type,date_text,event_date_min,event_date_max,temporal_precision,evidence_text,extraction_method,extractor_version,extractor_confidence,status,metadata) "+
        "select x.candidate_key,x.person_id,x.source_record_id,x.proposed_domain,x.proposed_event_type,x.date_text,x.event_date_min::date,x.event_date_max::date,x.temporal_precision,x.evidence_text,x.extraction_method,x.extractor_version,x.extractor_confidence,x.status,x.metadata "+
        "from jsonb_to_recordset($1::jsonb) as x(candidate_key text,person_id bigint,source_record_id bigint,proposed_domain text,proposed_event_type text,date_text text,event_date_min text,event_date_max text,temporal_precision text,evidence_text text,extraction_method text,extractor_version text,extractor_confidence double precision,status text,metadata jsonb) "+
        "on conflict(candidate_key) do update set source_record_id=excluded.source_record_id,status=excluded.status,metadata=research.event_candidates.metadata||excluded.metadata",
        candidates,250);

      const events=[];
      let unmatchedRulePeople=0,prebirth=0;
      for(const r of rulesRaw){
        const q=String(r.person_id||"").trim();
        const person=pmap.get(q);
        if(!person){unmatchedRulePeople++;continue;}
        const d0=nil(r.event_date_min),d1=nil(r.event_date_max),obs=nil(r.observable_from);
        const amin=ageYears(person.birth,d0),amax=ageYears(person.birth,d1);
        const amid=nil(r.age_mid)!==null?Number(r.age_mid):(amin!==null&&amax!==null?Math.round(((amin+amax)/2)*10000)/10000:null);
        const isPrebirth=amax!==null&&amax<0;
        if(isPrebirth)prebirth++;
        events.push({
          event_key:String(r.event_id),person_id:person.id,domain:String(r.domain||"other"),
          event_type:String(r.event_type||"other"),event_date_min:d0,event_date_max:d1,
          temporal_precision:nil(r.temporal_precision)||"year",age_min:amin,age_max:amax,age_mid:amid,
          observable_from:obs,subject_external_id:null,source_family:"wikipedia",
          extraction_method:nil(r.extraction_method)||"rule-from-revision-text",
          confidence:Number(r.confidence||0.82),source_rank:"revision-pinned-narrative-rule",reference_count:1,
          attributes:{
            candidate_id:nil(r.candidate_id),revision_id:nil(r.revision_id),
            evidence_text_length:String(r.evidence_text||"").length,
            artifact_id:ARTIFACT_ID
          },
          source_snapshot_id:SNAPSHOT_ID,source_url:nil(r.source_url),
          model_eligible:Boolean(d0&&d1&&obs)&&!isPrebirth,
          quality_flags:isPrebirth?{prebirth_interval:true}:{}
        });
      }
      await execBatches(tx,
        "insert into research.life_events(event_key,person_id,domain,event_type,event_date_min,event_date_max,temporal_precision,age_min,age_max,age_mid,observable_from,subject_external_id,source_family,extraction_method,confidence,source_rank,reference_count,attributes,source_snapshot_id,source_url,model_eligible,quality_flags) "+
        "select x.event_key,x.person_id,x.domain,x.event_type,x.event_date_min::date,x.event_date_max::date,x.temporal_precision,x.age_min,x.age_max,x.age_mid,x.observable_from::date,x.subject_external_id,x.source_family,x.extraction_method,x.confidence,x.source_rank,x.reference_count,x.attributes,x.source_snapshot_id::uuid,x.source_url,x.model_eligible,x.quality_flags "+
        "from jsonb_to_recordset($1::jsonb) as x(event_key text,person_id bigint,domain text,event_type text,event_date_min text,event_date_max text,temporal_precision text,age_min double precision,age_max double precision,age_mid double precision,observable_from text,subject_external_id text,source_family text,extraction_method text,confidence double precision,source_rank text,reference_count integer,attributes jsonb,source_snapshot_id text,source_url text,model_eligible boolean,quality_flags jsonb) "+
        "on conflict(event_key) do update set confidence=greatest(research.life_events.confidence,excluded.confidence),source_url=coalesce(research.life_events.source_url,excluded.source_url),attributes=research.life_events.attributes||excluded.attributes",
        events,250);

      const eventRows=await tx.unsafe("select id,event_key,model_eligible from research.life_events where source_family='wikipedia'");
      const eventMap=new Map(eventRows.map(x=>[x.event_key,{id:Number(x.id),eligible:Boolean(x.model_eligible)}]));
      const evidence=[],members=[];
      for(const r of rulesRaw){
        const event=eventMap.get(String(r.event_id));
        if(!event)continue;
        const site=(String(r.source_id||"wikipedia:enwiki").split(":")[1]||"enwiki");
        const sourceKey=`wikipedia:${site}:revision:${String(r.revision_id||"")}`;
        const sid=sourceMap.get(sourceKey);
        if(!sid)continue;
        evidence.push({
          event_id:event.id,source_record_id:sid,
          evidence_text:String(r.evidence_text||""),
          evidence_locator:String(r.candidate_id||r.event_id),
          extractor_version:"rule-from-revision-text",
          confidence:Number(r.confidence||0.82),
          metadata:{artifact_id:ARTIFACT_ID,candidate_id:nil(r.candidate_id),license:"CC BY-SA"}
        });
        members.push({
          dataset_snapshot_id:SNAPSHOT_ID,event_id:event.id,inclusion_role:"direct-enrichment",
          snapshot_model_eligible:event.eligible,
          exclusion_reason:event.eligible?null:"intrinsic_model_ineligible",
          metadata:{artifact_id:ARTIFACT_ID,source_family:"wikipedia"}
        });
      }
      await execBatches(tx,
        "insert into research.event_evidence(event_id,source_record_id,evidence_text,evidence_locator,extractor_version,confidence,metadata) "+
        "select x.event_id,x.source_record_id,x.evidence_text,x.evidence_locator,x.extractor_version,x.confidence,x.metadata "+
        "from jsonb_to_recordset($1::jsonb) as x(event_id bigint,source_record_id bigint,evidence_text text,evidence_locator text,extractor_version text,confidence double precision,metadata jsonb) "+
        "on conflict(event_id,source_record_id,evidence_locator) do update set evidence_text=excluded.evidence_text,confidence=greatest(research.event_evidence.confidence,excluded.confidence),metadata=research.event_evidence.metadata||excluded.metadata",
        evidence,250);
      await execBatches(tx,
        "insert into research.dataset_event_membership(dataset_snapshot_id,event_id,inclusion_role,snapshot_model_eligible,exclusion_reason,metadata) "+
        "select x.dataset_snapshot_id::uuid,x.event_id,x.inclusion_role,x.snapshot_model_eligible,x.exclusion_reason,x.metadata "+
        "from jsonb_to_recordset($1::jsonb) as x(dataset_snapshot_id text,event_id bigint,inclusion_role text,snapshot_model_eligible boolean,exclusion_reason text,metadata jsonb) "+
        "on conflict(dataset_snapshot_id,event_id) do update set inclusion_role=excluded.inclusion_role,snapshot_model_eligible=excluded.snapshot_model_eligible,exclusion_reason=excluded.exclusion_reason,metadata=research.dataset_event_membership.metadata||excluded.metadata",
        members,300);

      await tx.unsafe(
        "update research.dataset_snapshots set "+
        "event_count=(select count(*) from research.dataset_event_membership where dataset_snapshot_id=$1::uuid), "+
        "status='identity-final-events-enriching', "+
        "metadata=metadata||jsonb_build_object('wikipedia_biography_artifact_id',$2::text,'wikipedia_biography_artifact_sha256',$3::text,'wikipedia_rule_event_count',$4::int,'wikipedia_candidate_count',$5::int,'wikipedia_artifact_storage_path',$6::text) "+
        "where id=$1::uuid",
        [SNAPSHOT_ID,ARTIFACT_ID,"sha256:"+EXPECTED_SHA,events.length,candidates.length,storagePath]
      );

      await tx.unsafe(
        "insert into research.artifact_registry(artifact_key,provider,provider_artifact_id,artifact_name,artifact_kind,sha256,source_workflow_run_id,storage_bucket,storage_path,status,metadata,archived_at,imported_at) "+
        "values($1,'github-actions',$2,$3,'wikipedia-biography-enrichment',$4,$5,'research-artifacts',$6,'imported',$7::jsonb,now(),now()) "+
        "on conflict(artifact_key) do update set storage_bucket=excluded.storage_bucket,storage_path=excluded.storage_path,status='imported',archived_at=coalesce(research.artifact_registry.archived_at,now()),imported_at=now(),metadata=research.artifact_registry.metadata||excluded.metadata",
        [
          "github-actions:"+ARTIFACT_ID+":"+actual,
          ARTIFACT_ID,ARTIFACT_NAME,actual,WORKFLOW_RUN_ID,storagePath,
          JSON.stringify({
            candidate_rows:candidatesRaw.length,imported_candidates:candidates.length,
            rule_event_rows:rulesRaw.length,imported_rule_events:events.length,
            source_revisions:sources.length,unmatched_candidate_people:unmatchedCandidatePeople,
            unmatched_rule_people:unmatchedRulePeople,prebirth_rule_events:prebirth
          })
        ]
      );
    });

    const counts=await sql.unsafe(
      "select "+
      "(select count(*)::int from research.event_candidates where metadata->>'artifact_id'=$1) as artifact_candidates,"+
      "(select count(*)::int from research.life_events where source_family='wikipedia' and attributes->>'artifact_id'=$1) as artifact_events,"+
      "(select count(*)::int from research.dataset_event_membership where dataset_snapshot_id=$2::uuid) as snapshot_events,"+
      "(select count(distinct e.person_id)::int from research.dataset_event_membership dem join research.life_events e on e.id=dem.event_id where dem.dataset_snapshot_id=$2::uuid) as snapshot_people_with_events",
      [ARTIFACT_ID,SNAPSHOT_ID]
    );
    await sql.end({timeout:5});
    return Response.json({
      ok:true,sha256:actual,storage_path:storagePath,
      candidate_rows:candidatesRaw.length,rule_event_rows:rulesRaw.length,
      source_revisions:sources.length,unmatched_candidate_people:unmatchedCandidatePeople,
      counts:counts[0]
    });
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e?.stack||e)},{status:500});
  }
});
