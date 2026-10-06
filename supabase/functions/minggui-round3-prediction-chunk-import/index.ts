
import postgres from "npm:postgres@3.4.5";
import Papa from "npm:papaparse@5.4.1";

const APPROVED={"175008e8670824efabc3e5774ada638fc33c796663b2e34bf8e97505de7db08f":["forward_era_v1","bazi_decade_shuffle_placebo_v1",4294],"9989153c7eef8268be424bfd7f45709e56e5b63e115cdfaf7e531e5ac8d23597":["forward_era_v1","bazi_objective_only_v1",4294],"7ac510f761f607f859bd6565987137582d87f81d34fc06d2d1d6734f51517f89":["forward_era_v1","history_plus_bazi_v1",4294],"c1731deff5d119a07a6c8cc1aecdf2656491076ccb5fc31be00cc53d43f3befa":["forward_era_v1","history_reality_v1",4294],"b6ea9c65ee1244ea9cdb69f6082670ca62f28f7aee30004e9dee0bf7d2c4cdde":["forward_era_v1","raw_birth_calendar_v1",4294],"48c52a6dad29a504269c897548ed181bb5a7c992c55e8d2ac6cdf5d2bfcf20c3":["geo_france_holdout_v1","bazi_decade_shuffle_placebo_v1",3859],"f3070cee247935630e513ad16b2d7d86ef98641ff5ea0d75ac42b0647aca8083":["geo_france_holdout_v1","bazi_objective_only_v1",3908],"240380824356600e284f5b09e451748b9825c8e57c3aae2a3ac868a09cb1a253":["geo_france_holdout_v1","history_plus_bazi_v1",3908],"ada394cb58240d58f03e4807547b8f26d85679c7762efd3fd3e38122066cea81":["geo_france_holdout_v1","history_reality_v1",3908],"6473cc133efef4c9ad4ed1c6b42ac630bceda3dd2762341508e41c750932dbb5":["geo_france_holdout_v1","raw_birth_calendar_v1",3908],"6071445d74ad4c4a0eeec7a0dbfb016dd07517978efb9b95dace7a1c94ede9b7":["geo_us_holdout_v1","bazi_decade_shuffle_placebo_v1",3859],"437dc455f2946e1721ab10394105815c7027cded837196c50149e30370b425df":["geo_us_holdout_v1","bazi_objective_only_v1",3908],"8e1cc7776d9cae42a6bb7919a9523ce07acc44aa068a5dd926067a6f2542eb34":["geo_us_holdout_v1","history_plus_bazi_v1",3908],"b50cc62304aa0a0fc906600b48b685ccafd01bfdf233dbf252c22e76361f94f5":["geo_us_holdout_v1","history_reality_v1",3908],"0257c261fe24a59319339bf804ffd39f1a7ebe174da344bfc9cfe9cae23671fa":["geo_us_holdout_v1","raw_birth_calendar_v1",3908]};
const hex=(buf)=>Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,"0")).join("");

async function gunzip(bytes){
  const ds=new DecompressionStream("gzip");
  return await new Response(new Blob([bytes]).stream().pipeThrough(ds)).text();
}

Deno.serve(async(req)=>{
  if(req.method!=="POST") return new Response("POST only",{status:405});
  const db=Deno.env.get("SUPABASE_DB_URL");
  if(!db) return new Response("missing db",{status:500});
  const sql=postgres(db,{prepare:false,max:1});
  const q=(text,params=[])=>sql.unsafe(text,params);
  try{
    const bytes=new Uint8Array(await req.arrayBuffer());
    const sha=hex(await crypto.subtle.digest("SHA-256",bytes));
    const cfg=APPROVED[sha];
    if(!cfg){
      await sql.end({timeout:2});
      return Response.json({ok:false,error:"unapproved chunk sha",sha256:sha},{status:400});
    }
    const [scenario,variant,expectedRows]=cfg;
    const parsed=Papa.parse(await gunzip(bytes),{header:true,skipEmptyLines:true,dynamicTyping:true});
    if(parsed.errors?.length) throw new Error("CSV parse error "+JSON.stringify(parsed.errors.slice(0,3)));
    const rows=parsed.data;
    if(rows.length!==expectedRows) throw new Error("row count mismatch "+rows.length+" != "+expectedRows);
    for(const r of rows){
      if(r.scenario_key!==scenario || r.feature_variant!==variant) throw new Error("chunk identity mismatch");
    }
    const rr=await q(
      "select id from research.model_runs where run_key=$1",
      ["final-v1-r3-"+scenario+"-hgb-"+variant]
    );
    if(rr.length!==1) throw new Error("missing model run");
    const runId=String(rr[0].id);

    const batchSize=250;
    for(let start=0;start<rows.length;start+=batchSize){
      const batch=rows.slice(start,start+batchSize);
      const params=[];
      const values=[];
      let n=1;
      for(const r of batch){
        values.push("($"+(n++)+"::uuid,$"+(n++)+"::bigint,$"+(n++)+",$"+(n++)+",$"+(n++)+",$"+(n++)+"::jsonb,$"+(n++)+"::jsonb)");
        params.push(
          runId,Number(r.training_example_id),r.split_name,r.y_true,r.y_pred,
          JSON.stringify({
            career:Number(r.p_career),
            other:Number(r.p_other),
            recognition:Number(r.p_recognition),
            relationship:Number(r.p_relationship)
          }),
          JSON.stringify({
            round:"final-v1-round3",
            scenario_key:scenario,
            person_id:Number(r.person_id),
            prediction_chunk_sha256:sha
          })
        );
      }
      await q(
        "insert into research.model_predictions(run_id,training_example_id,split_name,y_true,y_pred,probabilities,metadata) values "+values.join(",")+
        " on conflict(run_id,training_example_id) do update set split_name=excluded.split_name,y_true=excluded.y_true,y_pred=excluded.y_pred,probabilities=excluded.probabilities,metadata=excluded.metadata",
        params
      );
    }

    await q(
      "update research.model_predictions set probabilities=(probabilities #>> '{}')::jsonb where run_id=$1::uuid and jsonb_typeof(probabilities)='string'",
      [runId]
    );
    await q(
      "update research.model_predictions set metadata=(metadata #>> '{}')::jsonb where run_id=$1::uuid and jsonb_typeof(metadata)='string'",
      [runId]
    );
    const count=await q("select count(*)::int n from research.model_predictions where run_id=$1::uuid",[runId]);
    await sql.end({timeout:3});
    return Response.json({ok:true,sha256:sha,scenario_key:scenario,feature_variant:variant,chunk_rows:rows.length,stored_rows:count[0].n});
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e?.stack||e)},{status:500});
  }
});
