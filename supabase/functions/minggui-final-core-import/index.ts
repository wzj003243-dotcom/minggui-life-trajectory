
import JSZip from "npm:jszip@3.10.1";
import Papa from "npm:papaparse@5.4.1";
import postgres from "npm:postgres@3.4.5";

const EXPECTED_SHA="c39faf8249a723e0528cb91acbfc812fcc00373df63a8c7be6e90df4363153ef";
const SNAPSHOT_ID="42628250-3a51-4b92-b4bd-12c7dec846a8";
const nil=(v)=>v===undefined||v===null||v===""||v==="nan"||v==="NaN"?null:v;
const num=(v)=>{const x=nil(v);if(x===null)return null;const n=Number(x);return Number.isFinite(n)?n:null};
const intv=(v)=>{const n=num(v);return n===null?null:Math.trunc(n)};
const boolv=(v)=>{const x=nil(v);if(x===null)return null;const s=String(x).toLowerCase();if(["true","1","yes"].includes(s))return true;if(["false","0","no"].includes(s))return false;return null};
const parseCell=(v)=>{const x=nil(v);if(x===null)return null;const s=String(x);if(/^(true|false)$/i.test(s))return s.toLowerCase()==="true";if(/^-?\d+(?:\.\d+)?(?:e[+-]?\d+)?$/i.test(s)){const n=Number(s);if(Number.isFinite(n))return n}return x};
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
  return p.data;
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
    const existing=await sql.unsafe("select count(*)::int n from research.dataset_membership where dataset_snapshot_id=$1::uuid",[SNAPSHOT_ID]);
    if(Number(existing[0]?.n||0)===3398){
      await sql.end({timeout:2});
      return Response.json({ok:true,already_imported:true,people:3398});
    }
    const body=new Uint8Array(await req.arrayBuffer());
    const actual=hex(await crypto.subtle.digest("SHA-256",body));
    if(actual!==EXPECTED_SHA){
      await sql.end({timeout:2});
      return Response.json({ok:false,error:"sha mismatch",actual},{status:400});
    }
    const zip=await JSZip.loadAsync(body);
    const core=await findCsv(zip,"timed_linked_cohort.csv.gz");
    if(core.length!==3398) throw new Error("unexpected core size "+core.length);

    const people=core.map(r=>({
      wikidata_id:r.wikidata_id,canonical_name:r.name,gender:nil(r.gender),
      death_date:nil(r.death_date_normalized),death_year:intv(r.death_year),
      metadata:{adb_id:intv(r.adb_id),rodden_rating:nil(r.rodden_rating),feature_version:nil(r.feature_version),wikipedia_url:nil(r.wikipedia_url),adb_url:nil(r.adb_url)}
    }));
    await execBatches(sql,
      "insert into research.people(wikidata_id,canonical_name,gender,death_date,death_year,metadata) "+
      "select x.wikidata_id,x.canonical_name,x.gender,nullif(x.death_date,'')::date,x.death_year,x.metadata "+
      "from jsonb_to_recordset($1::jsonb) as x(wikidata_id text,canonical_name text,gender text,death_date text,death_year integer,metadata jsonb) "+
      "on conflict(wikidata_id) do update set canonical_name=excluded.canonical_name,gender=excluded.gender,death_date=excluded.death_date,death_year=excluded.death_year,metadata=excluded.metadata,updated_at=now()",
      people,500);

    const pRows=await sql.unsafe("select id,wikidata_id from research.people where wikidata_id is not null");
    const pid=new Map(pRows.map(x=>[x.wikidata_id,Number(x.id)]));

    const births=core.map(r=>({person_id:pid.get(r.wikidata_id),source_family:"astro-databank-timed",source_person_id:String(r.adb_id),
      birth_date:r.birth_date_normalized,birth_time:nil(r.birth_time_local),birth_time_known:boolv(r["bazi__birth_time_known"])??true,
      date_precision:"day",time_precision:nil(r.birth_time_local)?"minute":null,birth_place:nil(r.birth_place),birth_country:nil(r.birth_country),
      latitude:num(r.birth_latitude),longitude:num(r.birth_longitude),source_calendar:nil(r.source_calendar),calendar_kind:nil(r.calendar_kind),
      calendar_conversion:nil(r.calendar_conversion),reliability:nil(r.rodden_rating),is_canonical:true,
      metadata:{birth_date_source:nil(r.birth_date_source),adb_url:nil(r.adb_url)}}));
    await execBatches(sql,
      "insert into research.birth_records(person_id,source_family,source_person_id,birth_date,birth_time,birth_time_known,date_precision,time_precision,birth_place,birth_country,latitude,longitude,source_calendar,calendar_kind,calendar_conversion,reliability,is_canonical,metadata) "+
      "select x.person_id,x.source_family,x.source_person_id,nullif(x.birth_date,'')::date,nullif(x.birth_time,'')::time,x.birth_time_known,x.date_precision,x.time_precision,x.birth_place,x.birth_country,x.latitude,x.longitude,x.source_calendar,x.calendar_kind,x.calendar_conversion,x.reliability,x.is_canonical,x.metadata "+
      "from jsonb_to_recordset($1::jsonb) as x(person_id bigint,source_family text,source_person_id text,birth_date text,birth_time text,birth_time_known boolean,date_precision text,time_precision text,birth_place text,birth_country text,latitude double precision,longitude double precision,source_calendar text,calendar_kind text,calendar_conversion text,reliability text,is_canonical boolean,metadata jsonb) "+
      "on conflict(person_id,source_family,source_person_id) do update set birth_date=excluded.birth_date,birth_time=excluded.birth_time,birth_time_known=excluded.birth_time_known,birth_place=excluded.birth_place,birth_country=excluded.birth_country,latitude=excluded.latitude,longitude=excluded.longitude,reliability=excluded.reliability,is_canonical=excluded.is_canonical,metadata=excluded.metadata",
      births,500);

    const flags=["bazi__birth_time_known","bazi__calendar_uncertain_historical","bazi__year_month_boundary_ambiguous","bazi__date_only_day_boundary_uncertainty","bazi__primary_feature_eligible"];
    const pillars=["bazi__year_pillar","bazi__month_pillar","bazi__day_pillar","bazi__hour_pillar","bazi__year_gan","bazi__year_zhi","bazi__month_gan","bazi__month_zhi","bazi__day_gan","bazi__day_zhi","bazi__hour_gan","bazi__hour_zhi","bazi__day_master","bazi__year_nayin","bazi__month_nayin","bazi__day_nayin","bazi__hour_nayin","bazi__year_dishi","bazi__month_dishi","bazi__day_dishi","bazi__hour_dishi","bazi__year_xunkong","bazi__month_xunkong","bazi__day_xunkong","bazi__hour_xunkong"];
    const bazis=core.map(r=>{
      const four={},quality={},features={};
      for(const k of pillars) four[k.replace("bazi__","")]=parseCell(r[k]);
      for(const k of flags) quality[k.replace("bazi__","")]=parseCell(r[k]);
      for(const [k,v] of Object.entries(r)) if(k.startsWith("bazi__")&&!pillars.includes(k)&&!flags.includes(k)) features[k.replace("bazi__","")]=parseCell(v);
      return {person_id:pid.get(r.wikidata_id),feature_version:r.feature_version||"bazi-objective-v0.1",mode:"timed",four_pillars:four,objective_features:features,quality_flags:quality,source_snapshot_id:SNAPSHOT_ID};
    });
    await execBatches(sql,
      "insert into research.bazi_feature_sets(person_id,feature_version,mode,four_pillars,objective_features,quality_flags,source_snapshot_id) "+
      "select x.person_id,x.feature_version,x.mode,x.four_pillars,x.objective_features,x.quality_flags,x.source_snapshot_id::uuid "+
      "from jsonb_to_recordset($1::jsonb) as x(person_id bigint,feature_version text,mode text,four_pillars jsonb,objective_features jsonb,quality_flags jsonb,source_snapshot_id text) "+
      "on conflict(person_id,feature_version,mode,source_snapshot_id) do nothing",
      bazis,250);

    const members=core.map(r=>({dataset_snapshot_id:SNAPSHOT_ID,person_id:pid.get(r.wikidata_id),cohort_role:"verified_timed_core_final",metadata:{rodden_rating:r.rodden_rating}}));
    await execBatches(sql,
      "insert into research.dataset_membership(dataset_snapshot_id,person_id,cohort_role,metadata) "+
      "select x.dataset_snapshot_id::uuid,x.person_id,x.cohort_role,x.metadata from jsonb_to_recordset($1::jsonb) as x(dataset_snapshot_id text,person_id bigint,cohort_role text,metadata jsonb) "+
      "on conflict(dataset_snapshot_id,person_id) do update set cohort_role=excluded.cohort_role,metadata=excluded.metadata",
      members,500);

    await sql.unsafe("update research.dataset_snapshots set status='identity-final-core-loaded',person_count=3398 where id=$1::uuid",[SNAPSHOT_ID]);
    const counts=await sql.unsafe("select (select count(*)::int from research.people) people,(select count(*)::int from research.dataset_membership where dataset_snapshot_id=$1::uuid) final_members",[SNAPSHOT_ID]);
    await sql.end({timeout:5});
    return Response.json({ok:true,sha256:actual,counts:counts[0]});
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e?.stack||e)},{status:500});
  }
});
