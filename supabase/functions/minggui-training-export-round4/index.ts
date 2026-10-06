
import postgres from "npm:postgres@3.4.5";
const TRAJ="731fa601-9c18-4ce8-9a8a-557ded47395d";
const SOURCE="8261f970-adc3-4f9a-8043-9e0f6cb90be8";
const SNAP="42628250-3a51-4b92-b4bd-12c7dec846a8";

Deno.serve(async(req)=>{
  const u=new URL(req.url);
  const kind=u.searchParams.get("kind")||"";
  if(!["cutoffs","periods"].includes(kind)) return new Response("invalid kind",{status:400});
  const offset=Math.max(0,Number(u.searchParams.get("offset")||"0"));
  const limit=Math.min(2500,Math.max(1,Number(u.searchParams.get("limit")||"1000")));
  const db=Deno.env.get("SUPABASE_DB_URL");
  if(!db) return new Response("missing db",{status:500});
  const sql=postgres(db,{prepare:false,max:1});
  try{
    let rows;
    if(kind==="cutoffs"){
      rows=await sql.unsafe(`
        select
          c.training_dataset_id,
          c.source_training_example_id,
          c.person_id,
          c.wikidata_id,
          c.cutoff_age,
          c.cutoff_date,
          c.information_cutoff,
          c.source_target_canonical_event_key,
          c.source_target_domain,
          c.source_target_observable_from,
          c.source_observation_end_date,
          c.source_right_censored,
          c.x_features,
          c.provenance_raw_history_event_keys,
          c.modeled_history_canonical_event_keys,
          a.split_name,
          a.fold,
          a.split_group,
          pm.donor_person_id,
          coalesce(pm.eligible,false) placebo_eligible,
          dbf.objective_features donor_bazi_features,
          dbf.four_pillars donor_four_pillars,
          dbf.quality_flags donor_bazi_quality_flags
        from research.trajectory_cutoff_matrix_v1 c
        join research.training_split_assignments a
          on a.training_dataset_id='${SOURCE}'::uuid
         and a.scenario_key='person_hash_v1'
         and a.person_id=c.person_id
        left join research.training_placebo_person_map pm
          on pm.training_dataset_id='${SOURCE}'::uuid
         and pm.scenario_key='person_hash_v1'
         and pm.person_id=c.person_id
        left join research.bazi_feature_sets dbf
          on dbf.source_snapshot_id='${SNAP}'::uuid
         and dbf.person_id=pm.donor_person_id
         and dbf.mode='timed'
         and dbf.feature_version='bazi-objective-v0.1'
        where c.training_dataset_id='${TRAJ}'::uuid
        order by c.source_training_example_id
        limit ${limit} offset ${offset}
      `);
    }else{
      rows=await sql.unsafe(`
        select
          id,
          training_dataset_id,
          source_training_example_id,
          person_id,
          cutoff_age,
          cutoff_date,
          information_cutoff,
          interval_index,
          interval_start_year,
          interval_end_year,
          interval_start_date,
          interval_end_date,
          interval_width_years,
          outcome_class,
          event_observed,
          target_domain,
          target_canonical_event_key,
          target_observable_from,
          observation_end_date,
          source_right_censored,
          exposure_policy_key,
          source_feature_spec_version
        from research.trajectory_person_period_examples
        where training_dataset_id='${TRAJ}'::uuid
        order by id
        limit ${limit} offset ${offset}
      `);
    }
    await sql.end({timeout:3});
    return Response.json(rows,{headers:{"Cache-Control":"no-store","Content-Type":"application/json"}});
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({error:String(e?.stack||e)},{status:500});
  }
});
