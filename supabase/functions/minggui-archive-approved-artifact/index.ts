import postgres from "npm:postgres@3.4.5";

const APPROVED: Record<string,{artifactId:string;runId:string;name:string;kind:string;metadata?:Record<string,unknown>}> = {
  "c39faf8249a723e0528cb91acbfc812fcc00373df63a8c7be6e90df4363153ef":{
    artifactId:"11341368186",runId:"37299045081",name:"minggui-final-lossless-identity-core",kind:"final-identity-core"
  },
  "508d7456f903590d7748a4514350c8fd02d483c9379b3349f50cb73b0f3015fd":{
    artifactId:"11332091633",runId:"37280940659",name:"minggui-timed-core-multisource",kind:"timed-core-multisource-source"
  },
  "3c3a678005980a9f4e63c20fae813dd73f76e8b575998b9c733c00bdc63cff96":{
    artifactId:"11398193051",runId:"37429050813",name:"minggui-v11-biography-shard-0-partial",
    kind:"v11-biography-partial-recovery-source",
    metadata:{archive_only:true,training_eligible:false,reason:"cancelled streaming fetch; complete JSONL prefix recoverable"}
  },
  "443e863906e83426b61d678ad6cf8855bd4d74cbde43b2b103eed508b89259af":{
    artifactId:"11398456161",runId:"37429050813",name:"minggui-v11-biography-shard-1-partial",
    kind:"v11-biography-partial-recovery-source",
    metadata:{archive_only:true,training_eligible:false,reason:"cancelled streaming fetch; complete JSONL prefix recoverable"}
  },
  "fe45b95ecd65be89cda353fd6de0c42ef9ddd907d023eaf7bff14185d6fc5bf8":{
    artifactId:"11405355636",runId:"37447942474",name:"minggui-v11-biography-shard-2-rejected",
    kind:"v11-biography-rejected-multititle",
    metadata:{archive_only:true,training_eligible:false,reason:"resolved sitelinks but multi-title revision mapping emitted zero biographies"}
  },
  "99ad0934b2570784fd63b03cd53822172e0ebfb5ba852d6330cdb0aa1006617f":{
    artifactId:"11405600697",runId:"37447942474",name:"minggui-v11-biography-shard-3-rejected",
    kind:"v11-biography-rejected-multititle",
    metadata:{archive_only:true,training_eligible:false,reason:"resolved sitelinks but multi-title revision mapping emitted zero biographies"}
  }
};

const hex=(buf:ArrayBuffer)=>Array.from(new Uint8Array(buf))
  .map(b=>b.toString(16).padStart(2,"0")).join("");

async function serverSecret(){
  const legacy=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const secretJson=Deno.env.get("SUPABASE_SECRET_KEYS");
  let secret=legacy;
  if(secretJson){try{secret=JSON.parse(secretJson)?.default||secret;}catch{}}
  return secret;
}

Deno.serve(async(req)=>{
  if(req.method!=="POST")return new Response("POST only",{status:405});
  const db=Deno.env.get("SUPABASE_DB_URL");
  const url=Deno.env.get("SUPABASE_URL");
  const secret=await serverSecret();
  if(!db||!url||!secret)return new Response("missing server credentials",{status:500});

  const sql=postgres(db,{prepare:false,max:1});
  try{
    const bytes=new Uint8Array(await req.arrayBuffer());
    const sha=hex(await crypto.subtle.digest("SHA-256",bytes));
    const cfg=APPROVED[sha];
    if(!cfg){
      await sql.end({timeout:2});
      return Response.json({ok:false,error:"unapproved artifact sha",sha256:sha},{status:400});
    }

    const path=`github-actions/${cfg.artifactId}-${sha}.zip`;
    const res=await fetch(`${url}/storage/v1/object/research-artifacts/${path}`,{
      method:"POST",
      headers:{
        Authorization:`Bearer ${secret}`,
        apikey:secret,
        "Content-Type":"application/zip",
        "x-upsert":"true"
      },
      body:bytes
    });
    const body=await res.text();
    if(!res.ok)throw new Error(`storage archive failed ${res.status}: ${body}`);

    const metadata={archive_only:true,...(cfg.metadata||{})};
    await sql.unsafe(
      "insert into research.artifact_registry("+
      "artifact_key,provider,provider_artifact_id,artifact_name,artifact_kind,sha256,size_bytes,"+
      "source_workflow_run_id,storage_bucket,storage_path,status,metadata,archived_at) "+
      "values($1,'github-actions',$2,$3,$4,$5,$6,$7,'research-artifacts',$8,'archived',$9::jsonb,now()) "+
      "on conflict(artifact_key) do update set "+
      "storage_bucket=excluded.storage_bucket,storage_path=excluded.storage_path,size_bytes=excluded.size_bytes,"+
      "status='archived',archived_at=coalesce(research.artifact_registry.archived_at,now()),"+
      "metadata=research.artifact_registry.metadata||excluded.metadata",
      [
        "github-actions:"+cfg.artifactId+":"+sha,cfg.artifactId,cfg.name,cfg.kind,sha,
        bytes.length,cfg.runId,path,JSON.stringify(metadata)
      ]
    );
    await sql.end({timeout:5});
    return Response.json({
      ok:true,artifact_id:cfg.artifactId,kind:cfg.kind,sha256:sha,
      size_bytes:bytes.length,storage_path:path
    });
  }catch(e){
    try{await sql.end({timeout:2})}catch{}
    return Response.json({ok:false,error:String(e?.stack||e)},{status:500});
  }
});
