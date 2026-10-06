
import postgres from "npm:postgres@3.4.5";
const DATASET="8261f970-adc3-4f9a-8043-9e0f6cb90be8";
const ALLOWED=new Set(["forward_era_v1","geo_us_holdout_v1","geo_france_holdout_v1"]);

Deno.serve(async(req)=>{
  const u=new URL(req.url);
  const scenario=u.searchParams.get("scenario")||"";
  if(!ALLOWED.has(scenario)) return new Response("invalid scenario",{status:400});
  const offset=Math.max(0,Number(u.searchParams.get("offset")||"0"));
  const limit=Math.min(1000,Math.max(1,Number(u.searchParams.get("limit")||"1000")));
  const db=Deno.env.get("SUPABASE_DB_URL");
  if(!db) return new Response("missing db",{status:500});
  const sql=postgres(db,{prepare:false,max:1});
  try{
    const rows=await sql.unsafe(`
      select
        m.training_example_id,m.person_id,m.wikidata_id,m.cutoff_age,
        tsa.split_name,tsa.fold,tsa.split_group,
        m.y_raw_domain,m.y_class_4,
        jsonb_build_object(
          'background',m.x_features->'background',
          'raw_birth_calendar',m.x_features->'raw_birth_calendar',
          'history',m.x_features->'history',
          'objective_bazi_features',m.x_features->'objective_bazi_features',
          'four_pillars',m.x_features->'four_pillars',
          'bazi_quality_flags',m.x_features->'bazi_quality_flags'
        ) as x,
        pm.donor_person_id,
        coalesce(pm.eligible,false) as placebo_eligible,
        dbf.objective_features as donor_bazi_features,
        dbf.four_pillars as donor_four_pillars,
        dbf.quality_flags as donor_bazi_quality_flags
      from research.training_classification_rows_v1 m
      join research.training_split_assignments tsa
        on tsa.training_dataset_id=m.training_dataset_id
       and tsa.scenario_key='${scenario}'
       and tsa.person_id=m.person_id
      left join research.training_placebo_person_map pm
        on pm.training_dataset_id=m.training_dataset_id
       and pm.scenario_key='${scenario}'
       and pm.person_id=m.person_id
      left join research.bazi_feature_sets dbf
        on dbf.source_snapshot_id='42628250-3a51-4b92-b4bd-12c7dec846a8'::uuid
       and dbf.person_id=pm.donor_person_id
       and dbf.mode='timed'
       and dbf.feature_version='bazi-objective-v0.1'
      where m.training_dataset_id='${DATASET}'::uuid
      order by m.training_example_id
      limit ${limit} offset ${offset}
    `);
    await sql.end({timeout:3});
    return Response.json(rows,{headers:{"Cache-Control":"no-store","Content-Type":"application/json"}});
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({error:String(e?.stack||e)},{status:500});
  }
});
