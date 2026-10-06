import postgres from "npm:postgres@3.4.5";

const IMPORTER_KEY="v11-biography-shard-v1";
const PROVIDER="github-actions";
const TARGET="7fce3b79-ebfc-40b2-a5f0-e91b28db6a02";

const nil=(v)=>v===undefined||v===null||v===""||v==="nan"||v==="NaN"?null:v;
const hex=(buf)=>Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,"0")).join("");
const esc=(s)=>String(s).replaceAll("'","''");

async function serviceKey(){
  let v=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const j=Deno.env.get("SUPABASE_SECRET_KEYS");
  if(j){try{v=JSON.parse(j)?.default||v}catch{}}
  return v;
}
async function archive(bytes,artifactId,sha){
  const url=Deno.env.get("SUPABASE_URL"),key=await serviceKey();
  if(!url||!key)throw new Error("missing storage credentials");
  const path="v11/biography/"+artifactId+"-"+sha+".zip";
  const r=await fetch(url+"/storage/v1/object/research-artifacts/"+path,{
    method:"POST",
    headers:{Authorization:"Bearer "+key,apikey:key,"Content-Type":"application/zip","x-upsert":"true"},
    body:bytes
  });
  const t=await r.text();
  if(!r.ok)throw new Error("storage upload "+r.status+": "+t);
  return path;
}
function ageYears(birth,d){
  if(!birth||!d)return null;
  const a=Date.parse(String(birth).slice(0,10)+"T00:00:00Z");
  const b=Date.parse(String(d).slice(0,10)+"T00:00:00Z");
  if(!Number.isFinite(a)||!Number.isFinite(b))return null;
  return Math.round(((b-a)/86400000/365.2425)*10000)/10000;
}
function parseYearOnly(raw){
  const years=[...new Set(String(raw||"").split("|").map(x=>x.trim()).filter(x=>/^\d{4}$/.test(x)))];
  if(years.length!==1)return {years,min:null,max:null,precision:"ambiguous"};
  return {years,min:years[0]+"-01-01",max:years[0]+"-12-31",precision:"year"};
}
async function insertJson(sql,query,rows){
  if(!rows.length)return;
  const payload=esc(JSON.stringify(rows));
  await sql.unsafe(query.replace("$JSON","'"+payload+"'::jsonb"));
}
async function peopleMap(sql,qids){
  const uniq=[...new Set(qids.filter(Boolean))];
  if(!uniq.length)return new Map();
  const vals=uniq.map((_,i)=>"$"+(i+1)).join(",");
  const rows=await sql.unsafe(
    "select p.wikidata_id,psf.person_id,psf.birth_date::text "+
    "from research.person_snapshot_facts psf join research.people p on p.id=psf.person_id "+
    "where psf.dataset_snapshot_id='"+TARGET+"'::uuid and p.wikidata_id in ("+vals+")",
    uniq
  );
  return new Map(rows.map(r=>[r.wikidata_id,{id:Number(r.person_id),birth:r.birth_date}]));
}
async function sourceMap(sql,keys){
  const uniq=[...new Set(keys.filter(Boolean))];
  if(!uniq.length)return new Map();
  const vals=uniq.map((_,i)=>"$"+(i+1)).join(",");
  const rows=await sql.unsafe(
    "select id,source_key from research.source_records where source_key in ("+vals+")",uniq
  );
  return new Map(rows.map(r=>[r.source_key,Number(r.id)]));
}
async function authorization(sql,artifactId){
  const rows=await sql.unsafe(
    "select sha256,target_snapshot_id::text,status,metadata "+
    "from research.artifact_import_authorizations "+
    "where importer_key=$1 and provider=$2 and provider_artifact_id=$3",
    [IMPORTER_KEY,PROVIDER,artifactId]
  );
  if(rows.length!==1)throw new Error("artifact authorization missing");
  if(rows[0].target_snapshot_id!==TARGET)throw new Error("wrong target snapshot");
  if(!["approved","imported"].includes(rows[0].status))throw new Error("authorization status "+rows[0].status);
  return rows[0];
}
async function snapshot(sql){
  const rows=await sql.unsafe(
    "select version,status,observation_cutoff_date::text observation_cutoff_date "+
    "from research.dataset_snapshots where id=$1::uuid",[TARGET]
  );
  if(rows.length!==1||rows[0].version!=="v1.1-working"||rows[0].status!=="draft")
    throw new Error("v1.1 target must be draft");
  const cutoff=String(rows[0].observation_cutoff_date||"").slice(0,10);
  if(!cutoff)throw new Error("v1.1 target missing observation cutoff");
  return cutoff;
}
async function recordChunk(sql,artifactId,chunkName,sha,phase,rowCount,metadata={}){
  await sql.unsafe(
    "insert into research.artifact_import_chunks(importer_key,provider,provider_artifact_id,chunk_name,sha256,phase,row_count,status,metadata,imported_at) "+
    "values($1,$2,$3,$4,$5,$6,$7,'imported',$8::jsonb,now()) "+
    "on conflict(importer_key,provider,provider_artifact_id,chunk_name) do update set "+
    "sha256=excluded.sha256,phase=excluded.phase,row_count=excluded.row_count,status='imported',metadata=research.artifact_import_chunks.metadata||excluded.metadata,imported_at=now()",
    [IMPORTER_KEY,PROVIDER,artifactId,chunkName,sha,phase,rowCount,JSON.stringify(metadata)]
  );
}
function expectedChunkSha(auth,chunkName){
  const chunks=auth.metadata?.import_chunks||{};
  return String(chunks[chunkName]||"");
}

Deno.serve(async(req)=>{
  if(req.method!=="POST")return new Response("POST only",{status:405});
  const u=new URL(req.url);
  const mode=u.searchParams.get("mode")||"chunk";
  const artifactId=u.searchParams.get("artifact_id")||"";
  const chunkName=u.searchParams.get("chunk_name")||"";
  if(!/^\d+$/.test(artifactId))return new Response("invalid artifact_id",{status:400});

  const db=Deno.env.get("SUPABASE_DB_URL");
  if(!db)return new Response("missing db",{status:500});
  const sql=postgres(db,{prepare:false,max:1});

  try{
    const auth=await authorization(sql,artifactId);

    if(mode==="archive"){
      const bytes=new Uint8Array(await req.arrayBuffer());
      const sha=hex(await crypto.subtle.digest("SHA-256",bytes));
      if(sha!==String(auth.sha256))throw new Error("source artifact sha mismatch");
      const path=await archive(bytes,artifactId,sha);
      await sql.unsafe(
        "update research.artifact_import_authorizations set metadata=metadata||jsonb_build_object("+
        "'storage_path',$4::text,'archived_sha256',$3::text,'archived_at',now()::text) "+
        "where importer_key=$1 and provider=$2 and provider_artifact_id=$5",
        [IMPORTER_KEY,PROVIDER,sha,path,artifactId]
      );
      await sql.end({timeout:5});
      return Response.json({ok:true,mode,artifact_id:artifactId,sha256:sha,storage_path:path});
    }

    if(!chunkName)throw new Error("chunk_name required");
    const body=new Uint8Array(await req.arrayBuffer());
    const sha=hex(await crypto.subtle.digest("SHA-256",body));
    const expected=expectedChunkSha(auth,chunkName);
    if(!expected||sha!==expected)throw new Error("chunk not authorized or sha mismatch");
    const payload=JSON.parse(new TextDecoder().decode(body));
    if(String(payload.source_artifact_id)!==artifactId)throw new Error("payload artifact mismatch");
    if(String(payload.source_artifact_sha256)!==String(auth.sha256))throw new Error("payload source sha mismatch");
    if(String(payload.target_snapshot_id)!==TARGET)throw new Error("payload target mismatch");
    const phase=String(payload.phase||"");
    const shard=String(payload.shard);
    const cutoff=await snapshot(sql);

    if(phase==="prepare"){
      const bios=Array.isArray(payload.biographies)?payload.biographies:[];
      const pmap=await peopleMap(sql,bios.map(b=>String(b.person_id||"").trim()));
      if(pmap.size!==bios.length){
        const missing=bios.filter(b=>!pmap.has(String(b.person_id||"").trim())).map(b=>b.person_id);
        throw new Error("prepare has unmatched people: "+JSON.stringify(missing.slice(0,10)));
      }
      const sources=bios.map(b=>{
        const q=String(b.person_id||"").trim(),site=String(b.site||"enwiki"),rev=String(b.revision_id||"");
        const pageid=String(b.pageid||"");
        return {
          source_key:"wikipedia:"+site+":revision:"+rev,
          source_type:"revision-wikitext",
          source_family:"wikipedia",
          publisher:"Wikipedia / Wikimedia",
          title:String(b.title||("Wikipedia revision "+rev)),
          url:nil(b.source_url),
          dataset_version:"v1.1-shard-artifact:"+artifactId,
          revision_id:rev,
          revision_timestamp:nil(b.revision_timestamp),
          license_bucket:nil(b.license)||"CC BY-SA",
          license_url:null,
          independence_group:"wikipedia:"+site+":page:"+pageid,
          metadata:{
            qid:q,site,pageid,revision_sha1:nil(b.revision_sha1),
            content_chars:Number(b.content_chars||0)||null,
            v11_artifact_id:artifactId,v11_shard:shard,
            raw_content_location:String(auth.metadata?.storage_path||"")
          }
        };
      });
      await sql.begin(async tx=>{
        await insertJson(tx,
          "insert into research.source_records(source_key,source_type,source_family,publisher,title,url,dataset_version,revision_id,revision_timestamp,license_bucket,license_url,independence_group,metadata) "+
          "select x.source_key,x.source_type,x.source_family,x.publisher,x.title,x.url,x.dataset_version,x.revision_id,x.revision_timestamp::timestamptz,x.license_bucket,x.license_url,x.independence_group,x.metadata "+
          "from jsonb_to_recordset($JSON) as x(source_key text,source_type text,source_family text,publisher text,title text,url text,dataset_version text,revision_id text,revision_timestamp text,license_bucket text,license_url text,independence_group text,metadata jsonb) "+
          "on conflict(source_key) do update set url=coalesce(excluded.url,research.source_records.url),revision_timestamp=coalesce(excluded.revision_timestamp,research.source_records.revision_timestamp),metadata=research.source_records.metadata||excluded.metadata",
          sources
        );

        const revisions=[...pmap.entries()].map(([qid,p])=>{
          const b=bios.find(x=>String(x.person_id||"").trim()===qid);
          return {person_id:p.id,current_revision:String(b?.revision_id||"")};
        });
        await insertJson(tx,
          "with x as (select * from jsonb_to_recordset($JSON) as q(person_id bigint,current_revision text)) "+
          "update research.dataset_event_membership dem set "+
          "snapshot_model_eligible=false,exclusion_reason='superseded_by_v11_biography_revision',"+
          "metadata=coalesce(dem.metadata,'{}'::jsonb)||jsonb_build_object("+
            "'superseded_by_v11_artifact','"+esc(artifactId)+"','superseded_by_revision',x.current_revision,'superseded_at',now()::text) "+
          "from research.life_events e,x "+
          "where dem.dataset_snapshot_id='"+TARGET+"'::uuid and dem.event_id=e.id and e.person_id=x.person_id "+
          "and e.source_family='wikipedia' and coalesce(e.extraction_method,'')='rule-from-revision-text' "+
          "and coalesce(e.attributes->>'revision_id','')<>x.current_revision",
          revisions
        );
        await recordChunk(tx,artifactId,chunkName,sha,phase,bios.length,{shard});
      });
      await sql.end({timeout:5});
      return Response.json({ok:true,phase,artifact_id:artifactId,chunk_name:chunkName,rows:bios.length});
    }

    if(phase==="candidates"){
      const rows=Array.isArray(payload.rows)?payload.rows:[];
      const pmap=await peopleMap(sql,rows.map(r=>String(r.person_id||"").trim()));
      const keys=rows.map(r=>"wikipedia:"+String(r.site||"enwiki")+":revision:"+String(r.revision_id||""));
      const smap=await sourceMap(sql,keys);
      const inserts=[];
      for(const r of rows){
        const q=String(r.person_id||"").trim(),person=pmap.get(q);
        if(!person)throw new Error("candidate unmatched person "+q);
        const site=String(r.site||"enwiki"),rev=String(r.revision_id||"");
        const sourceKey="wikipedia:"+site+":revision:"+rev;
        const sid=smap.get(sourceKey);
        if(!sid)throw new Error("candidate source missing "+sourceKey);
        const parsed=parseYearOnly(r.years);
        const domains=[...new Set(String(r.candidate_domains||"").split("|").map(x=>x.trim()).filter(Boolean))];
        const cid=String(r.candidate_id||"");
        inserts.push({
          candidate_key:"wikipedia:"+cid,person_id:person.id,source_record_id:sid,
          proposed_domain:domains.length===1?domains[0]:null,proposed_event_type:null,
          date_text:nil(r.years),event_date_min:parsed.min,event_date_max:parsed.max,
          temporal_precision:parsed.precision,evidence_text:String(r.text||""),
          extraction_method:"timeline-candidate-from-revision-text",
          extractor_version:"wikipedia-biography-candidate-v1",
          extractor_confidence:null,status:"candidate",
          metadata:{
            candidate_id:cid,site,pageid:nil(r.pageid),revision_id:rev,
            revision_timestamp:nil(r.revision_timestamp),source_url:nil(r.source_url),
            years:parsed.years,ages:nil(r.ages),candidate_domains:domains,
            text_length:Number(r.text_length||0)||null,license:nil(r.license)||"CC BY-SA",
            v11_artifact_id:artifactId,v11_shard:shard
          }
        });
      }
      await sql.begin(async tx=>{
        await insertJson(tx,
          "insert into research.event_candidates(candidate_key,person_id,source_record_id,proposed_domain,proposed_event_type,date_text,event_date_min,event_date_max,temporal_precision,evidence_text,extraction_method,extractor_version,extractor_confidence,status,metadata) "+
          "select x.candidate_key,x.person_id,x.source_record_id,x.proposed_domain,x.proposed_event_type,x.date_text,x.event_date_min::date,x.event_date_max::date,x.temporal_precision,x.evidence_text,x.extraction_method,x.extractor_version,x.extractor_confidence,x.status,x.metadata "+
          "from jsonb_to_recordset($JSON) as x(candidate_key text,person_id bigint,source_record_id bigint,proposed_domain text,proposed_event_type text,date_text text,event_date_min text,event_date_max text,temporal_precision text,evidence_text text,extraction_method text,extractor_version text,extractor_confidence double precision,status text,metadata jsonb) "+
          "on conflict(candidate_key) do update set source_record_id=excluded.source_record_id,evidence_text=excluded.evidence_text,metadata=research.event_candidates.metadata||excluded.metadata",
          inserts
        );
        await recordChunk(tx,artifactId,chunkName,sha,phase,rows.length,{shard});
      });
      await sql.end({timeout:5});
      return Response.json({ok:true,phase,artifact_id:artifactId,chunk_name:chunkName,rows:rows.length});
    }

    if(phase==="events"){
      const rows=Array.isArray(payload.rows)?payload.rows:[];
      const pmap=await peopleMap(sql,rows.map(r=>String(r.person_id||"").trim()));
      const sourceKeys=rows.map(r=>"wikipedia:"+String(r.site||"enwiki")+":revision:"+String(r.revision_id||""));
      const smap=await sourceMap(sql,sourceKeys);
      const events=[],candidateKeys=[];
      const membershipByKey=new Map();
      for(const r of rows){
        const q=String(r.person_id||"").trim(),person=pmap.get(q);
        if(!person)throw new Error("event unmatched person "+q);
        const site=String(r.site||"enwiki"),rev=String(r.revision_id||"");
        const sourceKey="wikipedia:"+site+":revision:"+rev;
        const sid=smap.get(sourceKey);
        if(!sid)throw new Error("event source missing "+sourceKey);
        const d0=nil(r.event_date_min),d1=nil(r.event_date_max),obs=nil(r.observable_from);
        const amin=ageYears(person.birth,d0),amax=ageYears(person.birth,d1);
        const amid=nil(r.age_mid)!==null?Number(r.age_mid):(amin!==null&&amax!==null?Math.round(((amin+amax)/2)*10000)/10000:null);
        const prebirth=amax!==null&&amax<0;
        const afterCutoff=Boolean(obs&&String(obs).slice(0,10)>cutoff);
        const intrinsicEligible=Boolean(d0&&d1&&obs)&&!prebirth;
        const snapshotEligible=intrinsicEligible&&!afterCutoff;
        const eventKey=String(r.event_id||"");
        const candidateKey="wikipedia:"+String(r.candidate_id||"");
        candidateKeys.push(candidateKey);
        events.push({
          event_key:eventKey,person_id:person.id,domain:String(r.domain||"other"),
          event_type:String(r.event_type||"other"),event_date_min:d0,event_date_max:d1,
          temporal_precision:nil(r.temporal_precision)||"year",age_min:amin,age_max:amax,age_mid:amid,
          observable_from:obs,subject_external_id:null,source_family:"wikipedia",
          extraction_method:nil(r.extraction_method)||"rule-from-revision-text",
          confidence:Number(r.confidence||0.82),source_rank:"revision-pinned-narrative-rule",reference_count:1,
          attributes:{
            candidate_id:nil(r.candidate_id),revision_id:rev,pageid:nil(r.pageid),
            revision_timestamp:nil(r.revision_timestamp),
            evidence_text_length:String(r.evidence_text||"").length,
            v11_artifact_id:artifactId,v11_shard:shard
          },
          source_snapshot_id:TARGET,source_url:nil(r.source_url),
          model_eligible:intrinsicEligible,
          quality_flags:{
            ...(prebirth?{prebirth_interval:true}:{}),
            ...(afterCutoff?{after_snapshot_cutoff:true,snapshot_cutoff:cutoff}:{})
          },
          source_record_id:sid,evidence_text:String(r.evidence_text||""),
          evidence_locator:String(r.candidate_id||r.event_id),
          snapshot_model_eligible:snapshotEligible,
          exclusion_reason:snapshotEligible?null:(prebirth?"prebirth_interval":afterCutoff?"after_snapshot_cutoff":"intrinsic_model_ineligible")
        });
        membershipByKey.set(eventKey,{snapshotEligible,exclusionReason:snapshotEligible?null:(prebirth?"prebirth_interval":afterCutoff?"after_snapshot_cutoff":"intrinsic_model_ineligible")});
      }

      await sql.begin(async tx=>{
        await insertJson(tx,
          "insert into research.life_events(event_key,person_id,domain,event_type,event_date_min,event_date_max,temporal_precision,age_min,age_max,age_mid,observable_from,subject_external_id,source_family,extraction_method,confidence,source_rank,reference_count,attributes,source_snapshot_id,source_url,model_eligible,quality_flags) "+
          "select x.event_key,x.person_id,x.domain,x.event_type,x.event_date_min::date,x.event_date_max::date,x.temporal_precision,x.age_min,x.age_max,x.age_mid,x.observable_from::date,x.subject_external_id,x.source_family,x.extraction_method,x.confidence,x.source_rank,x.reference_count,x.attributes,x.source_snapshot_id::uuid,x.source_url,x.model_eligible,x.quality_flags "+
          "from jsonb_to_recordset($JSON) as x(event_key text,person_id bigint,domain text,event_type text,event_date_min text,event_date_max text,temporal_precision text,age_min double precision,age_max double precision,age_mid double precision,observable_from text,subject_external_id text,source_family text,extraction_method text,confidence double precision,source_rank text,reference_count integer,attributes jsonb,source_snapshot_id text,source_url text,model_eligible boolean,quality_flags jsonb) "+
          "on conflict(event_key) do update set confidence=greatest(research.life_events.confidence,excluded.confidence),source_url=coalesce(excluded.source_url,research.life_events.source_url),attributes=research.life_events.attributes||excluded.attributes,quality_flags=research.life_events.quality_flags||excluded.quality_flags,model_eligible=research.life_events.model_eligible or excluded.model_eligible",
          events
        );

        const keys=events.map(e=>e.event_key);
        const vals=keys.map((_,i)=>"$"+(i+1)).join(",");
        const erows=keys.length?await tx.unsafe("select id,event_key from research.life_events where event_key in ("+vals+")",keys):[];
        const emap=new Map(erows.map(e=>[e.event_key,Number(e.id)]));
        const evidence=[],members=[];
        for(const e of events){
          const id=emap.get(e.event_key);if(!id)throw new Error("inserted event missing "+e.event_key);
          evidence.push({
            event_id:id,source_record_id:e.source_record_id,evidence_text:e.evidence_text,
            evidence_locator:e.evidence_locator,extractor_version:"rule-from-revision-text",
            confidence:e.confidence,
            metadata:{v11_artifact_id:artifactId,v11_shard:shard,candidate_id:e.attributes.candidate_id,license:"CC BY-SA"}
          });
          members.push({
            dataset_snapshot_id:TARGET,event_id:id,inclusion_role:"v1.1-biography-enrichment",
            snapshot_model_eligible:e.snapshot_model_eligible,exclusion_reason:e.exclusion_reason,
            metadata:{v11_biography_artifact_id:artifactId,v11_shard:shard,source_family:"wikipedia",revision_id:e.attributes.revision_id}
          });
        }
        await insertJson(tx,
          "insert into research.event_evidence(event_id,source_record_id,evidence_text,evidence_locator,extractor_version,confidence,metadata) "+
          "select x.event_id,x.source_record_id,x.evidence_text,x.evidence_locator,x.extractor_version,x.confidence,x.metadata "+
          "from jsonb_to_recordset($JSON) as x(event_id bigint,source_record_id bigint,evidence_text text,evidence_locator text,extractor_version text,confidence double precision,metadata jsonb) "+
          "on conflict(event_id,source_record_id,evidence_locator) do update set evidence_text=excluded.evidence_text,confidence=greatest(research.event_evidence.confidence,excluded.confidence),metadata=research.event_evidence.metadata||excluded.metadata",
          evidence
        );
        await insertJson(tx,
          "insert into research.dataset_event_membership(dataset_snapshot_id,event_id,inclusion_role,snapshot_model_eligible,exclusion_reason,metadata) "+
          "select x.dataset_snapshot_id::uuid,x.event_id,x.inclusion_role,x.snapshot_model_eligible,x.exclusion_reason,x.metadata "+
          "from jsonb_to_recordset($JSON) as x(dataset_snapshot_id text,event_id bigint,inclusion_role text,snapshot_model_eligible boolean,exclusion_reason text,metadata jsonb) "+
          "on conflict(dataset_snapshot_id,event_id) do update set inclusion_role=excluded.inclusion_role,snapshot_model_eligible=excluded.snapshot_model_eligible,exclusion_reason=excluded.exclusion_reason,metadata=research.dataset_event_membership.metadata||excluded.metadata",
          members
        );
        if(candidateKeys.length){
          const vals=candidateKeys.map((_,i)=>"$"+(i+1)).join(",");
          await tx.unsafe(
            "update research.event_candidates set status='rule-accepted' where candidate_key in ("+vals+")",
            candidateKeys
          );
        }
        await recordChunk(tx,artifactId,chunkName,sha,phase,rows.length,{shard});
      });
      await sql.end({timeout:5});
      return Response.json({ok:true,phase,artifact_id:artifactId,chunk_name:chunkName,rows:rows.length});
    }

    if(phase==="finalize"){
      const expected=auth.metadata?.import_chunks||{};
      const expectedNames=Object.keys(expected);
      if(!expectedNames.length)throw new Error("authorization missing import_chunks manifest");
      const importedRows=await sql.unsafe(
        "select chunk_name from research.artifact_import_chunks where importer_key=$1 and provider=$2 and provider_artifact_id=$3 and status='imported'",
        [IMPORTER_KEY,PROVIDER,artifactId]
      );
      const imported=new Set(importedRows.map(r=>r.chunk_name));
      imported.add(chunkName);
      const missing=expectedNames.filter(n=>!imported.has(n));
      if(missing.length)throw new Error("cannot finalize; missing chunks "+JSON.stringify(missing.slice(0,20)));
      if(!auth.metadata?.storage_path)throw new Error("cannot finalize; exact source ZIP not archived");

      await sql.begin(async tx=>{
        await recordChunk(tx,artifactId,chunkName,sha,phase,0,{shard});
        await tx.unsafe(
          "update research.dataset_snapshots set "+
          "event_count=(select count(*) from research.dataset_event_membership where dataset_snapshot_id=$1::uuid),"+
          "model_event_count=(select count(*) from research.dataset_event_membership where dataset_snapshot_id=$1::uuid and snapshot_model_eligible),"+
          "metadata=metadata||jsonb_build_object('v11_biography_last_artifact',$2::text,'v11_biography_last_shard',$3::text,'v11_biography_updated_at',now()::text) "+
          "where id=$1::uuid",
          [TARGET,artifactId,shard]
        );
        const sums=await tx.unsafe(
          "select phase,count(*)::int chunks,sum(row_count)::int rows "+
          "from research.artifact_import_chunks "+
          "where importer_key=$1 and provider=$2 and provider_artifact_id=$3 and status='imported' "+
          "group by phase",[IMPORTER_KEY,PROVIDER,artifactId]
        );
        await tx.unsafe(
          "insert into research.artifact_registry(artifact_key,provider,provider_artifact_id,artifact_name,artifact_kind,sha256,size_bytes,source_workflow_run_id,source_git_sha,storage_bucket,storage_path,status,metadata,archived_at,imported_at) "+
          "values($1,$2,$3,$4,'wikipedia-biography-v11-shard',$5,$6,$7,$8,'research-artifacts',$9,'imported',$10::jsonb,now(),now()) "+
          "on conflict(artifact_key) do update set storage_path=excluded.storage_path,status='imported',metadata=research.artifact_registry.metadata||excluded.metadata,archived_at=coalesce(research.artifact_registry.archived_at,now()),imported_at=now()",
          [
            PROVIDER+":"+artifactId+":"+auth.sha256,PROVIDER,artifactId,
            "minggui-v11-biography-shard-"+shard,String(auth.sha256),
            Number(auth.metadata?.source_artifact_size_bytes||0)||null,
            String(auth.metadata?.source_workflow_run_id||""),String(auth.metadata?.source_git_sha||""),
            String(auth.metadata.storage_path),
            JSON.stringify({shard,import_chunks:expectedNames.length,phase_summaries:sums,target_snapshot_id:TARGET})
          ]
        );
        await tx.unsafe(
          "update research.artifact_import_authorizations set status='imported',imported_at=now(),metadata=metadata||jsonb_build_object('finalized_at',now()::text) "+
          "where importer_key=$1 and provider=$2 and provider_artifact_id=$3",
          [IMPORTER_KEY,PROVIDER,artifactId]
        );
      });
      await sql.end({timeout:5});
      return Response.json({ok:true,phase,artifact_id:artifactId,chunk_name:chunkName,complete:true});
    }

    throw new Error("unsupported phase "+phase);
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e?.stack||e)},{status:500});
  }
});
