
import JSZip from "npm:jszip@3.10.1";
import Papa from "npm:papaparse@5.4.1";
import postgres from "npm:postgres@3.4.5";

const EXPECTED_SHA="0b2718c8feff8303eb74a289c25c93548ea7efd6db8e7aaad102682f01697e47";
const SNAPSHOT_ID="42628250-3a51-4b92-b4bd-12c7dec846a8";
const ARTIFACT_ID="11342247791";
const nil=(v)=>v===undefined||v===null||v===""||v==="nan"||v==="NaN"?null:v;
const chunks=(a,n)=>Array.from({length:Math.ceil(a.length/n)},(_,i)=>a.slice(i*n,(i+1)*n));
const hex=(buf)=>Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,"0")).join("");

async function gunzipText(bytes){
  const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return await new Response(stream).text();
}
async function findCsv(zip,suffix){
  const path=Object.keys(zip.files).find(p=>p.endsWith(suffix));
  if(!path) throw new Error("missing "+suffix);
  const text=await gunzipText(await zip.file(path).async("uint8array"));
  const p=Papa.parse(text,{header:true,skipEmptyLines:true});
  if(p.errors?.length) throw new Error("csv parse errors: "+JSON.stringify(p.errors.slice(0,3)));
  return p.data;
}
function dateRange(raw){
  const s=String(raw||"").trim();
  let m=s.match(/^(\d{4})$/);
  if(m){const y=Number(m[1]);return {min:m[1]+"-01-01",max:m[1]+"-12-31",precision:"year"};}
  m=s.match(/^(\d{4})-(\d{2})$/);
  if(m){
    const y=Number(m[1]),mo=Number(m[2]);
    const last=new Date(Date.UTC(y,mo,0)).getUTCDate();
    return {min:s+"-01",max:s+"-"+String(last).padStart(2,"0"),precision:"month"};
  }
  m=s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if(m){const d=m[1]+"-"+m[2]+"-"+m[3];return {min:d,max:d,precision:"day"};}
  return null;
}
function ageYears(birth,d){
  if(!birth||!d)return null;
  const a=Date.parse(String(birth).slice(0,10)+"T00:00:00Z"), b=Date.parse(d+"T00:00:00Z");
  if(!Number.isFinite(a)||!Number.isFinite(b))return null;
  return Math.round(((b-a)/86400000/365.2425)*10000)/10000;
}
async function execBatches(sql,query,rows,size=400){
  let done=0;
  for(const batch of chunks(rows,size)){
    const payload=JSON.stringify(batch).replaceAll("'","''");
    await sql.unsafe(query.replace("$1::jsonb","'"+payload+"'::jsonb"));
    done+=batch.length;
  }
  return done;
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
    const zip=await JSZip.loadAsync(body);
    const raw=await findCsv(zip,"music_events.csv.gz");
    if(raw.length!==11476) throw new Error("unexpected music row count "+raw.length);

    const people=await sql.unsafe(
      "select p.id,p.wikidata_id,b.birth_date::text from research.dataset_membership dm "+
      "join research.people p on p.id=dm.person_id "+
      "left join research.birth_records b on b.person_id=p.id and b.is_canonical "+
      "where dm.dataset_snapshot_id=$1::uuid",[SNAPSHOT_ID]);
    const pmap=new Map(people.map(x=>[x.wikidata_id,{id:Number(x.id),birth:x.birth_date}]));

    let missingPeople=0,invalidDates=0;
    const sources=[],events=[];
    for(const r of raw){
      const person=pmap.get(String(r.person_id||"").trim());
      if(!person){missingPeople++;continue;}
      const dr=dateRange(r.event_date);
      if(!dr){invalidDates++;continue;}
      const amin=ageYears(person.birth,dr.min),amax=ageYears(person.birth,dr.max);
      const amid=amin===null||amax===null?null:Math.round(((amin+amax)/2)*10000)/10000;
      const eventKey=String(r.event_id);
      const sourceKey="musicbrainz:"+eventKey;
      const prebirth=amax!==null&&amax<0;
      sources.push({
        source_key:sourceKey,source_type:"structured-event",source_family:"musicbrainz",
        publisher:"MusicBrainz",title:nil(r.title),url:nil(r.source_url),
        dataset_version:"github-actions-artifact:"+ARTIFACT_ID,
        independence_group:"musicbrainz",
        metadata:{musicbrainz_id:nil(r.musicbrainz_id),subtype:nil(r.subtype),identity_method:nil(r.identity_method)}
      });
      const et=String(r.event_type||"other");
      events.push({
        event_key:eventKey,person_id:person.id,domain:et.includes(".")?et.split(".",1)[0]:"other",
        event_type:et,event_date_min:dr.min,event_date_max:dr.max,temporal_precision:dr.precision,
        age_min:amin,age_max:amax,age_mid:amid,observable_from:dr.max,
        subject_external_id:nil(r.musicbrainz_id),source_family:"musicbrainz",
        extraction_method:nil(r.identity_method)||"wikidata_p434_exact_mbid",
        confidence:0.95,source_rank:"structured-external",reference_count:1,
        attributes:{title:nil(r.title),subtype:nil(r.subtype),musicbrainz_id:nil(r.musicbrainz_id),source_event_id:eventKey},
        source_snapshot_id:SNAPSHOT_ID,source_url:nil(r.source_url),
        model_eligible:!prebirth,quality_flags:prebirth?{prebirth_interval:true}:{}
      });
    }

    await sql.begin(async tx=>{
      await execBatches(tx,
        "insert into research.source_records(source_key,source_type,source_family,publisher,title,url,dataset_version,independence_group,metadata) "+
        "select x.source_key,x.source_type,x.source_family,x.publisher,x.title,x.url,x.dataset_version,x.independence_group,x.metadata "+
        "from jsonb_to_recordset($1::jsonb) as x(source_key text,source_type text,source_family text,publisher text,title text,url text,dataset_version text,independence_group text,metadata jsonb) "+
        "on conflict(source_key) do update set title=excluded.title,url=excluded.url,dataset_version=excluded.dataset_version,metadata=excluded.metadata",
        sources,350);

      await execBatches(tx,
        "insert into research.life_events(event_key,person_id,domain,event_type,event_date_min,event_date_max,temporal_precision,age_min,age_max,age_mid,observable_from,subject_external_id,source_family,extraction_method,confidence,source_rank,reference_count,attributes,source_snapshot_id,source_url,model_eligible,quality_flags) "+
        "select x.event_key,x.person_id,x.domain,x.event_type,x.event_date_min::date,x.event_date_max::date,x.temporal_precision,x.age_min,x.age_max,x.age_mid,x.observable_from::date,x.subject_external_id,x.source_family,x.extraction_method,x.confidence,x.source_rank,x.reference_count,x.attributes,x.source_snapshot_id::uuid,x.source_url,x.model_eligible,x.quality_flags "+
        "from jsonb_to_recordset($1::jsonb) as x(event_key text,person_id bigint,domain text,event_type text,event_date_min text,event_date_max text,temporal_precision text,age_min double precision,age_max double precision,age_mid double precision,observable_from text,subject_external_id text,source_family text,extraction_method text,confidence double precision,source_rank text,reference_count integer,attributes jsonb,source_snapshot_id text,source_url text,model_eligible boolean,quality_flags jsonb) "+
        "on conflict(event_key) do nothing",
        events,300);

      const eventRows=await tx.unsafe("select id,event_key from research.life_events where source_family='musicbrainz'");
      const eventMap=new Map(eventRows.map(x=>[x.event_key,Number(x.id)]));
      const sourceRows=await tx.unsafe("select id,source_key from research.source_records where source_family='musicbrainz'");
      const sourceMap=new Map(sourceRows.map(x=>[x.source_key,Number(x.id)]));

      const evidence=[],members=[];
      for(const e of events){
        const eid=eventMap.get(e.event_key),sid=sourceMap.get("musicbrainz:"+e.event_key);
        if(!eid||!sid) continue;
        evidence.push({event_id:eid,source_record_id:sid,evidence_locator:e.source_url||e.event_key,confidence:e.confidence,metadata:{artifact_id:ARTIFACT_ID}});
        members.push({dataset_snapshot_id:SNAPSHOT_ID,event_id:eid,inclusion_role:"direct-enrichment",metadata:{artifact_id:ARTIFACT_ID,source_family:"musicbrainz"}});
      }
      await execBatches(tx,
        "insert into research.event_evidence(event_id,source_record_id,evidence_locator,confidence,metadata) "+
        "select x.event_id,x.source_record_id,x.evidence_locator,x.confidence,x.metadata from jsonb_to_recordset($1::jsonb) as x(event_id bigint,source_record_id bigint,evidence_locator text,confidence double precision,metadata jsonb) "+
        "on conflict(event_id,source_record_id,evidence_locator) do nothing",
        evidence,350);
      await execBatches(tx,
        "insert into research.dataset_event_membership(dataset_snapshot_id,event_id,inclusion_role,metadata) "+
        "select x.dataset_snapshot_id::uuid,x.event_id,x.inclusion_role,x.metadata from jsonb_to_recordset($1::jsonb) as x(dataset_snapshot_id text,event_id bigint,inclusion_role text,metadata jsonb) "+
        "on conflict(dataset_snapshot_id,event_id) do update set inclusion_role=excluded.inclusion_role,metadata=excluded.metadata",
        members,400);
      await tx.unsafe(
        "update research.dataset_snapshots set event_count=(select count(*) from research.dataset_event_membership where dataset_snapshot_id=$1::uuid), "+
        "metadata=metadata||jsonb_build_object('musicbrainz_artifact_id',$2::text,'musicbrainz_artifact_sha256',$3::text) where id=$1::uuid",
        [SNAPSHOT_ID,ARTIFACT_ID,"sha256:"+EXPECTED_SHA]);
    });

    const counts=await sql.unsafe(
      "select (select count(*)::int from research.life_events where source_family='musicbrainz') music_events,"+
      "(select count(*)::int from research.dataset_event_membership where dataset_snapshot_id=$1::uuid) snapshot_events,"+
      "(select count(distinct e.person_id)::int from research.dataset_event_membership dem join research.life_events e on e.id=dem.event_id where dem.dataset_snapshot_id=$1::uuid) snapshot_people_with_events",
      [SNAPSHOT_ID]);
    await sql.end({timeout:5});
    return Response.json({ok:true,sha256:actual,input_rows:raw.length,accepted_events:events.length,missing_people:missingPeople,invalid_dates:invalidDates,counts:counts[0]});
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e?.stack||e)},{status:500});
  }
});
