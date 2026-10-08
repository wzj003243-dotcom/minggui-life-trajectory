import postgres from "npm:postgres@3.4.5";
const SNAP="7fce3b79-ebfc-40b2-a5f0-e91b28db6a02";
const FINGERPRINT="2af1167d562c83789c0eaa0c0f7b793706ce2e17e9273c8c22450f80791dc5cf";
const EXPECTED_RUN="37712781470";
async function authorized(req:Request){
  const token=req.headers.get("Authorization")||"";
  if(!/^Bearer [a-zA-Z0-9_.-]+$/.test(token))return false;
  try{
    const r=await fetch("https://api.github.com/repos/wzj003243-dotcom/minggui-life-trajectory/actions/runs/"+EXPECTED_RUN,{
      headers:{"Authorization":token,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"MingGui-v11-research-export"},
      signal:AbortSignal.timeout(8000)
    });
    if(!r.ok)return false;
    const data=await r.json();
    return String(data.id)===EXPECTED_RUN&&data.conclusion==="success";
  }catch{return false;}
}
Deno.serve(async(req)=>{
  if(req.method!=="GET")return new Response("GET only",{status:405});
  if(!(await authorized(req)))return new Response("authorized repository token required",{status:403});
  const u=new URL(req.url),kind=u.searchParams.get("kind")||"";
  if(!["cutoffs","periods"].includes(kind))return new Response("invalid kind",{status:400});
  const offset=Math.max(0,Math.min(200000,parseInt(u.searchParams.get("offset")||"0",10)||0));
  const limit=Math.min(2000,Math.max(1,parseInt(u.searchParams.get("limit")||"1000",10)||1000));
  const db=Deno.env.get("SUPABASE_DB_URL");
  if(!db)return new Response("missing DB",{status:500});
  const sql=postgres(db,{prepare:false,max:1});
  try{
    const snaps=await sql.unsafe("select status,canonical_event_sha256 from research.dataset_snapshots where id=$1::uuid",[SNAP]);
    if(snaps.length!==1||snaps[0].status!=="frozen"||snaps[0].canonical_event_sha256!==FINGERPRINT)throw new Error("snapshot integrity check failed");
    let rows;
    if(kind==="cutoffs"){
      rows=await sql.unsafe(`
        select source_training_example_id,person_id,wikidata_id,cutoff_age,cutoff_date,
          information_cutoff,observation_end_date,split_name,fold,
          x_features_old,x_features_new,
          target_canonical_event_key,target_domain,target_observable_from,
          old_target_canonical_event_key,old_target_observable_from
        from research.v11_r5_cutoffs
        order by source_training_example_id limit ${limit} offset ${offset}`);
    }else{
      rows=await sql.unsafe(`
        select person_period_id,source_training_example_id,person_id,cutoff_age,
          interval_index,interval_start_year,interval_end_year,interval_width_years,
          interval_start_date,interval_end_date,outcome_class,
          target_canonical_event_key,target_domain,target_observable_from,observation_end_date
        from research.v11_r5_periods
        order by person_period_id limit ${limit} offset ${offset}`);
    }
    await sql.end({timeout:3});
    return Response.json(rows,{headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({error:String(e?.stack||e)},{status:500});
  }
});