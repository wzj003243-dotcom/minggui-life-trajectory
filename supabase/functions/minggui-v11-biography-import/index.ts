import JSZip from "npm:jszip@3.10.1";
import Papa from "npm:papaparse@5.4.1";
import postgres from "npm:postgres@3.4.5";

const IMPORTER_KEY="v11-biography-shard-v1";
const EXPECTED_TARGET="7fce3b79-ebfc-40b2-a5f0-e91b28db6a02";

const nil=(v)=>v===undefined||v===null||v===""||v==="nan"||v==="NaN"?null:v;
const chunks=(a,n)=>Array.from({length:Math.ceil(a.length/n)},(_,i)=>a.slice(i*n,(i+1)*n));
const hex=(buf)=>Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,"0")).join("");
const uniq=(xs)=>[...new Set(xs.filter(Boolean))];
const esc=(s)=>String(s).replaceAll("'","''");

async function gunzipText(bytes){
  const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return await new Response(stream).text();
}
async function findGzipCsv(zip,pattern){
  const path=Object.keys(zip.files).find(p=>pattern.test(p));
  if(!path)throw new Error("missing "+pattern);
  const text=await gunzipText(await zip.file(path).async("uint8array"));
  const parsed=Papa.parse(text,{header:true,skipEmptyLines:true});
  if(parsed.errors?.length)throw new Error("csv parse "+JSON.stringify(parsed.errors.slice(0,3)));
  return {path,rows:parsed.data};
}
async function findJson(zip,pattern){
  const path=Object.keys(zip.files).find(p=>pattern.test(p));
  if(!path)return {path:null,value:null};
  return {path,value:JSON.parse(await zip.file(path).async("text"))};
}
async function findGzipJsonl(zip,pattern){
  const path=Object.keys(zip.files).find(p=>pattern.test(p));
  if(!path)throw new Error("missing "+pattern);
  const text=await gunzipText(await zip.file(path).async("uint8array"));
  const rows=text.split(/\r?\n/).filter(Boolean).map(line=>JSON.parse(line));
  return {path,rows};
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
async function execBatches(sql,query,rows,size=750){
  let done=0;
  for(const batch of chunks(rows,size)){
    const payload=esc(JSON.stringify(batch));
    await sql.unsafe(query.replace("$JSON","'"+payload+"'::jsonb"));
    done+=batch.length;
  }
  return done;
}
async function serverSecret(){
  let secret=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const j=Deno.env.get("SUPABASE_SECRET_KEYS");
  if(j){try{secret=JSON.parse(j)?.default||secret}catch{}}
  return secret;
}
async function archive(bytes,artifactId,sha){
  const url=Deno.env.get("SUPABASE_URL"),key=await serverSecret();
  const path="v11/biography/"+artifactId+"-"+sha+".zip";
  const r=await fetch(url+"/storage/v1/object/research-artifacts/"+path,{
    method:"POST",
    headers:{Authorization:"Bearer "+key,apikey:key,"Content-Type":"application/zip","x-upsert":"true"},
    body:bytes
  });
  const text=await r.text();
  if(!r.ok)throw new Error("storage upload "+r.status+": "+text);
  return path;
}

Deno.serve(async(req)=>{
  if(req.method!=="POST")return new Response("POST only",{status:405});
  const artifactId=new URL(req.url).searchParams.get("artifact_id")||"";
  if(!/^\d+$/.test(artifactId))return new Response("invalid artifact_id",{status:400});
  const db=Deno.env.get("SUPABASE_DB_URL");
  if(!db)return new Response("missing db",{status:500});
  const sql=postgres(db,{prepare:false,max:1});
  try{
    const body=new Uint8Array(await req.arrayBuffer());
    const sha=hex(await crypto.subtle.digest("SHA-256",body));
    const auth=await sql.unsafe(
      "select target_snapshot_id::text,status,metadata from research.artifact_import_authorizations "+
      "where importer_key=$1 and provider='github-actions' and provider_artifact_id=$2 and sha256=$3",
      [IMPORTER_KEY,artifactId,sha]
    );
    if(auth.length!==1)throw new Error("artifact not authorized");
    if(auth[0].target_snapshot_id!==EXPECTED_TARGET)throw new Error("wrong target snapshot");
    if(!["approved","imported"].includes(auth[0].status))throw new Error("authorization status "+auth[0].status);

    const snap=await sql.unsafe("select version,status from research.dataset_snapshots where id=$1::uuid",[EXPECTED_TARGET]);
    if(snap.length!==1||snap[0].version!=="v1.1-working"||snap[0].status!=="draft")throw new Error("v1.1 target not draft");

    const storagePath=await archive(body,artifactId,sha);
    const zip=await JSZip.loadAsync(body);
    const biographiesFile=await findGzipJsonl(zip,/biographies-shard-\d+\.jsonl\.gz$/);
    const candidatesFile=await findGzipCsv(zip,/candidates-shard-\d+\.csv\.gz$/);
    const rulesFile=await findGzipCsv(zip,/rule-events-shard-\d+\.csv\.gz$/);
    const reportFile=await findJson(zip,/(^|\/)shard-\d+\.report\.json$/);
    const biographiesRaw=biographiesFile.rows,candidatesRaw=candidatesFile.rows,rulesRaw=rulesFile.rows,report=reportFile.value||{};
    const shard=String(report.shard??auth[0].metadata?.shard??"unknown");

    if(report.candidate_rows!==undefined&&Number(report.candidate_rows)!==candidatesRaw.length)throw new Error("candidate report mismatch");
    if(report.rule_event_rows!==undefined&&Number(report.rule_event_rows)!==rulesRaw.length)throw new Error("rule report mismatch");

    const people=await sql.unsafe(
      "select psf.person_id,p.wikidata_id,psf.birth_date::text "+
      "from research.person_snapshot_facts psf join research.people p on p.id=psf.person_id "+
      "where psf.dataset_snapshot_id=$1::uuid",[EXPECTED_TARGET]
    );
    const pmap=new Map(people.map(x=>[x.wikidata_id,{id:Number(x.person_id),birth:x.birth_date}]));
    const ruleByCandidate=new Map(rulesRaw.map(r=>[String(r.candidate_id),String(r.event_id)]));
    const candidateById=new Map(candidatesRaw.map(r=>[String(r.candidate_id),r]));
    const currentRevisionByPerson=new Map();
    for(const b of biographiesRaw){
      const person=pmap.get(String(b.person_id||"").trim());
      const revision=String(b.revision_id||"").trim();
      if(person&&revision)currentRevisionByPerson.set(person.id,revision);
    }

    const revisionMap=new Map();let unmatchedCandidatePeople=0;
    for(const r of candidatesRaw){
      const person=pmap.get(String(r.person_id||"").trim());
      if(!person){unmatchedCandidatePeople++;continue;}
      const site=String(r.site||"enwiki").trim()||"enwiki";
      const revision=String(r.revision_id||"").trim(),pageid=String(r.pageid||"").trim();
      if(!revision)continue;
      const sourceKey="wikipedia:"+site+":revision:"+revision;
      if(!revisionMap.has(sourceKey))revisionMap.set(sourceKey,{
        source_key:sourceKey,source_type:"revision-wikitext",source_family:"wikipedia",
        publisher:"Wikipedia / Wikimedia",title:"Wikipedia revision "+revision,
        url:nil(r.source_url),dataset_version:"v1.1-shard-artifact:"+artifactId,
        revision_id:revision,revision_timestamp:nil(r.revision_timestamp),
        license_bucket:nil(r.license)||"CC BY-SA",license_url:null,
        independence_group:"wikipedia:"+site+":page:"+pageid,
        metadata:{site,pageid,v11_artifact_id:artifactId,v11_shard:shard,content_mode:"revision main-slot wikitext"}
      });
    }
    const sources=[...revisionMap.values()];
    let importedCandidates=0,importedEvents=0,prebirth=0,unmatchedRulePeople=0;

    await sql.begin(async tx=>{
      await execBatches(tx,
        "insert into research.source_records(source_key,source_type,source_family,publisher,title,url,dataset_version,revision_id,revision_timestamp,license_bucket,license_url,independence_group,metadata) "+
        "select x.source_key,x.source_type,x.source_family,x.publisher,x.title,x.url,x.dataset_version,x.revision_id,x.revision_timestamp::timestamptz,x.license_bucket,x.license_url,x.independence_group,x.metadata "+
        "from jsonb_to_recordset($JSON) as x(source_key text,source_type text,source_family text,publisher text,title text,url text,dataset_version text,revision_id text,revision_timestamp text,license_bucket text,license_url text,independence_group text,metadata jsonb) "+
        "on conflict(source_key) do update set url=coalesce(research.source_records.url,excluded.url),revision_timestamp=coalesce(research.source_records.revision_timestamp,excluded.revision_timestamp),metadata=research.source_records.metadata||excluded.metadata",
        sources,500);

      const sourceRows=await tx.unsafe("select id,source_key from research.source_records where source_family='wikipedia'");
      const sourceMap=new Map(sourceRows.map(x=>[x.source_key,Number(x.id)]));

      const candidates=[];
      for(const r of candidatesRaw){
        const person=pmap.get(String(r.person_id||"").trim());if(!person)continue;
        const site=String(r.site||"enwiki").trim()||"enwiki",revision=String(r.revision_id||"").trim();
        const parsed=parseYearOnly(r.years),domains=uniq(String(r.candidate_domains||"").split("|").map(x=>x.trim()));
        const cid=String(r.candidate_id),accepted=ruleByCandidate.get(cid)||null;
        candidates.push({
          candidate_key:"wikipedia:"+cid,person_id:person.id,source_record_id:sourceMap.get("wikipedia:"+site+":revision:"+revision)||null,
          proposed_domain:domains.length===1?domains[0]:null,proposed_event_type:null,date_text:nil(r.years),
          event_date_min:parsed.min,event_date_max:parsed.max,temporal_precision:parsed.precision,
          evidence_text:String(r.text||""),extraction_method:"timeline-candidate-from-revision-text",
          extractor_version:"wikipedia-biography-candidate-v1",extractor_confidence:null,status:accepted?"rule-accepted":"candidate",
          metadata:{candidate_id:cid,site,pageid:nil(r.pageid),revision_id:revision,revision_timestamp:nil(r.revision_timestamp),source_url:nil(r.source_url),years:parsed.years,ages:nil(r.ages),candidate_domains:domains,text_length:Number(r.text_length||0)||null,license:nil(r.license)||"CC BY-SA",v11_artifact_id:artifactId,v11_shard:shard,accepted_event_key:accepted}
        });
      }
      importedCandidates=candidates.length;
      await execBatches(tx,
        "insert into research.event_candidates(candidate_key,person_id,source_record_id,proposed_domain,proposed_event_type,date_text,event_date_min,event_date_max,temporal_precision,evidence_text,extraction_method,extractor_version,extractor_confidence,status,metadata) "+
        "select x.candidate_key,x.person_id,x.source_record_id,x.proposed_domain,x.proposed_event_type,x.date_text,x.event_date_min::date,x.event_date_max::date,x.temporal_precision,x.evidence_text,x.extraction_method,x.extractor_version,x.extractor_confidence,x.status,x.metadata "+
        "from jsonb_to_recordset($JSON) as x(candidate_key text,person_id bigint,source_record_id bigint,proposed_domain text,proposed_event_type text,date_text text,event_date_min text,event_date_max text,temporal_precision text,evidence_text text,extraction_method text,extractor_version text,extractor_confidence double precision,status text,metadata jsonb) "+
        "on conflict(candidate_key) do update set source_record_id=coalesce(research.event_candidates.source_record_id,excluded.source_record_id),status=case when excluded.status='rule-accepted' then 'rule-accepted' else research.event_candidates.status end,metadata=research.event_candidates.metadata||excluded.metadata",
        candidates,500);

      const events=[];
      for(const r of rulesRaw){
        const person=pmap.get(String(r.person_id||"").trim());
        if(!person){unmatchedRulePeople++;continue;}
        const d0=nil(r.event_date_min),d1=nil(r.event_date_max),obs=nil(r.observable_from);
        const amin=ageYears(person.birth,d0),amax=ageYears(person.birth,d1);
        const amid=nil(r.age_mid)!==null?Number(r.age_mid):(amin!==null&&amax!==null?Math.round(((amin+amax)/2)*10000)/10000:null);
        const isPrebirth=amax!==null&&amax<0;if(isPrebirth)prebirth++;
        events.push({
          event_key:String(r.event_id),person_id:person.id,domain:String(r.domain||"other"),event_type:String(r.event_type||"other"),
          event_date_min:d0,event_date_max:d1,temporal_precision:nil(r.temporal_precision)||"year",
          age_min:amin,age_max:amax,age_mid:amid,observable_from:obs,subject_external_id:null,source_family:"wikipedia",
          extraction_method:nil(r.extraction_method)||"rule-from-revision-text",confidence:Number(r.confidence||0.82),
          source_rank:"revision-pinned-narrative-rule",reference_count:1,
          attributes:{candidate_id:nil(r.candidate_id),revision_id:nil(r.revision_id),evidence_text_length:String(r.evidence_text||"").length,v11_artifact_id:artifactId,v11_shard:shard},
          source_snapshot_id:EXPECTED_TARGET,source_url:nil(r.source_url),model_eligible:Boolean(d0&&d1&&obs)&&!isPrebirth,
          quality_flags:isPrebirth?{prebirth_interval:true}:{}
        });
      }
      importedEvents=events.length;

      // Snapshot-local revision replacement:
      // preserve all historical/raw Wikipedia events and evidence, but do not let
      // multiple revisions for the same person simultaneously contribute labels.
      for(const [personId,currentRevision] of currentRevisionByPerson.entries()){
        await tx.unsafe(
          "update research.dataset_event_membership dem set "+
          "snapshot_model_eligible=false, "+
          "exclusion_reason='superseded_by_v11_biography_revision', "+
          "metadata=coalesce(dem.metadata,'{}'::jsonb)||jsonb_build_object("+
            "'superseded_by_v11_artifact',$3::text,'superseded_by_revision',$4::text,'superseded_at',now()::text) "+
          "from research.life_events e "+
          "where dem.dataset_snapshot_id=$1::uuid and dem.event_id=e.id and e.person_id=$2 "+
          "and e.source_family='wikipedia' "+
          "and coalesce(e.extraction_method,'')='rule-from-revision-text' "+
          "and coalesce(e.attributes->>'revision_id','')<>$4",
          [EXPECTED_TARGET,personId,artifactId,currentRevision]
        );
      }

      await execBatches(tx,
        "insert into research.life_events(event_key,person_id,domain,event_type,event_date_min,event_date_max,temporal_precision,age_min,age_max,age_mid,observable_from,subject_external_id,source_family,extraction_method,confidence,source_rank,reference_count,attributes,source_snapshot_id,source_url,model_eligible,quality_flags) "+
        "select x.event_key,x.person_id,x.domain,x.event_type,x.event_date_min::date,x.event_date_max::date,x.temporal_precision,x.age_min,x.age_max,x.age_mid,x.observable_from::date,x.subject_external_id,x.source_family,x.extraction_method,x.confidence,x.source_rank,x.reference_count,x.attributes,x.source_snapshot_id::uuid,x.source_url,x.model_eligible,x.quality_flags "+
        "from jsonb_to_recordset($JSON) as x(event_key text,person_id bigint,domain text,event_type text,event_date_min text,event_date_max text,temporal_precision text,age_min double precision,age_max double precision,age_mid double precision,observable_from text,subject_external_id text,source_family text,extraction_method text,confidence double precision,source_rank text,reference_count integer,attributes jsonb,source_snapshot_id text,source_url text,model_eligible boolean,quality_flags jsonb) "+
        "on conflict(event_key) do update set confidence=greatest(research.life_events.confidence,excluded.confidence),source_url=coalesce(research.life_events.source_url,excluded.source_url),attributes=research.life_events.attributes||excluded.attributes",
        events,500);

      const eventRows=[];
      for(const batch of chunks(events.map(x=>x.event_key),1000)){
        const vals=batch.map((_,i)=>"$"+(i+1)).join(",");
        eventRows.push(...await tx.unsafe("select id,event_key,model_eligible from research.life_events where event_key in ("+vals+")",batch));
      }
      const eventMap=new Map(eventRows.map(x=>[x.event_key,{id:Number(x.id),eligible:Boolean(x.model_eligible)}]));
      const evidence=[],members=[];
      for(const r of rulesRaw){
        const ev=eventMap.get(String(r.event_id));if(!ev)continue;
        const candidateId=String(r.candidate_id||""),cand=candidateById.get(candidateId);
        const site=String(cand?.site||String(r.source_id||"wikipedia:enwiki").split(":")[1]||"enwiki");
        const rev=String(r.revision_id||cand?.revision_id||"");
        const sid=sourceMap.get("wikipedia:"+site+":revision:"+rev);if(!sid)continue;
        evidence.push({event_id:ev.id,source_record_id:sid,evidence_text:String(r.evidence_text||""),evidence_locator:candidateId||String(r.event_id),extractor_version:"rule-from-revision-text",confidence:Number(r.confidence||0.82),metadata:{v11_artifact_id:artifactId,v11_shard:shard,candidate_id:nil(r.candidate_id),license:"CC BY-SA"}});
        members.push({dataset_snapshot_id:EXPECTED_TARGET,event_id:ev.id,inclusion_role:"v1.1-biography-enrichment",snapshot_model_eligible:ev.eligible,exclusion_reason:ev.eligible?null:"intrinsic_model_ineligible",metadata:{v11_biography_artifact_id:artifactId,v11_shard:shard,source_family:"wikipedia"}});
      }
      await execBatches(tx,
        "insert into research.event_evidence(event_id,source_record_id,evidence_text,evidence_locator,extractor_version,confidence,metadata) "+
        "select x.event_id,x.source_record_id,x.evidence_text,x.evidence_locator,x.extractor_version,x.confidence,x.metadata from jsonb_to_recordset($JSON) as x(event_id bigint,source_record_id bigint,evidence_text text,evidence_locator text,extractor_version text,confidence double precision,metadata jsonb) "+
        "on conflict(event_id,source_record_id,evidence_locator) do update set evidence_text=excluded.evidence_text,confidence=greatest(research.event_evidence.confidence,excluded.confidence),metadata=research.event_evidence.metadata||excluded.metadata",
        evidence,500);
      await execBatches(tx,
        "insert into research.dataset_event_membership(dataset_snapshot_id,event_id,inclusion_role,snapshot_model_eligible,exclusion_reason,metadata) "+
        "select x.dataset_snapshot_id::uuid,x.event_id,x.inclusion_role,x.snapshot_model_eligible,x.exclusion_reason,x.metadata from jsonb_to_recordset($JSON) as x(dataset_snapshot_id text,event_id bigint,inclusion_role text,snapshot_model_eligible boolean,exclusion_reason text,metadata jsonb) "+
        "on conflict(dataset_snapshot_id,event_id) do update set snapshot_model_eligible=research.dataset_event_membership.snapshot_model_eligible or excluded.snapshot_model_eligible,exclusion_reason=case when research.dataset_event_membership.snapshot_model_eligible or excluded.snapshot_model_eligible then null else coalesce(research.dataset_event_membership.exclusion_reason,excluded.exclusion_reason) end,metadata=research.dataset_event_membership.metadata||excluded.metadata",
        members,750);

      await tx.unsafe(
        "update research.dataset_snapshots set event_count=(select count(*) from research.dataset_event_membership where dataset_snapshot_id=$1::uuid),model_event_count=(select count(*) from research.dataset_event_membership where dataset_snapshot_id=$1::uuid and snapshot_model_eligible),metadata=metadata||jsonb_build_object('v11_biography_last_artifact',$2::text,'v11_biography_last_shard',$3::text,'v11_biography_updated_at',now()::text) where id=$1::uuid",
        [EXPECTED_TARGET,artifactId,shard]);
      await tx.unsafe(
        "insert into research.artifact_registry(artifact_key,provider,provider_artifact_id,artifact_name,artifact_kind,sha256,size_bytes,storage_bucket,storage_path,status,metadata,archived_at,imported_at) values($1,'github-actions',$2,$3,'wikipedia-biography-v11-shard',$4,$5,'research-artifacts',$6,'imported',$7::jsonb,now(),now()) on conflict(artifact_key) do update set storage_path=excluded.storage_path,status='imported',metadata=research.artifact_registry.metadata||excluded.metadata,archived_at=coalesce(research.artifact_registry.archived_at,now()),imported_at=now()",
        ["github-actions:"+artifactId+":"+sha,artifactId,"minggui-v11-biography-shard-"+shard,sha,body.length,storagePath,JSON.stringify({shard,report,candidate_rows:candidatesRaw.length,rule_event_rows:rulesRaw.length,imported_candidates:importedCandidates,imported_events:importedEvents,source_revisions:sources.length,biographies_fetched:biographiesRaw.length,current_revision_people:currentRevisionByPerson.size,unmatched_candidate_people:unmatchedCandidatePeople,unmatched_rule_people:unmatchedRulePeople,prebirth_rule_events:prebirth,target_snapshot_id:EXPECTED_TARGET})]);
      await tx.unsafe(
        "update research.artifact_import_authorizations set status='imported',imported_at=now(),metadata=metadata||jsonb_build_object('storage_path',$4::text,'shard',$5::text,'candidate_rows',$6::int,'rule_event_rows',$7::int) where importer_key=$1 and provider='github-actions' and provider_artifact_id=$2 and sha256=$3",
        [IMPORTER_KEY,artifactId,sha,storagePath,shard,candidatesRaw.length,rulesRaw.length]);
    });

    const counts=await sql.unsafe(
      "select (select count(*)::int from research.dataset_event_membership where dataset_snapshot_id=$1::uuid) raw_event_memberships,(select count(*)::int from research.dataset_event_membership where dataset_snapshot_id=$1::uuid and snapshot_model_eligible) model_eligible_memberships,(select count(*)::int from research.event_candidates where metadata->>'v11_artifact_id'=$2) artifact_candidates,(select count(*)::int from research.life_events where attributes->>'v11_artifact_id'=$2) artifact_events",
      [EXPECTED_TARGET,artifactId]);
    await sql.end({timeout:5});
    return Response.json({ok:true,artifact_id:artifactId,sha256:sha,shard,storage_path:storagePath,report,candidate_rows:candidatesRaw.length,rule_event_rows:rulesRaw.length,imported_candidates:importedCandidates,imported_events:importedEvents,source_revisions:sources.length,biographies_fetched:biographiesRaw.length,current_revision_people:currentRevisionByPerson.size,unmatched_candidate_people:unmatchedCandidatePeople,unmatched_rule_people:unmatchedRulePeople,prebirth_rule_events:prebirth,counts:counts[0]});
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e?.stack||e)},{status:500});
  }
});
