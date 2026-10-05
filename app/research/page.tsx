import { getLifeGraphDatasetStatus } from "../../lib/lifegraph-db";

const tests=[
  ["Reality baseline","现实变量模型必须先跑；命理特征只有在增量预测上胜出才算有信号。"],
  ["Shuffled birthdays","打乱生日与人物生平。如果真实生日不显著优于假生日，命理层没有预测价值。"],
  ["Time split","只允许用某个年龄之前的信息预测之后的人生，禁止看完整生平后反推。"],
  ["Prediction ledger","公开版预测写入时间戳、区间、概率和验证标准；失败不能事后改口。"],
];

export default async function ResearchPage(){
  const db=await getLifeGraphDatasetStatus().catch(()=>null);

  return <main className="shell page research">
    <div className="page-title">
      <div className="eyebrow">LAB / 实验室</div>
      <h1>这个项目不是为了证明命理。<br/>而是让它第一次真正接受验证。</h1>
    </div>

    <section className="research-grid">
      <article className="panel">
        <h2>LifeGraph 数据库</h2>
        {db ? <>
          <p><b>{db.db_people?.toLocaleString()}</b> 个 verified timed people</p>
          <p><b>{db.db_events?.toLocaleString()}</b> 条完整原子事件</p>
          <p><b>{db.db_year_states?.toLocaleString()}</b> 个 cutoff-safe person-year states</p>
          <p><b>{db.model_ready_thick_people?.toLocaleString()}</b> 人达到当前严格 thick-data 标准</p>
          <p>Snapshot: <code>{db.dataset_key} / {db.version}</code></p>
        </> : <p>数据库已建立；当前运行环境未配置 server-side Supabase secret，因此这里不发起研究库查询。</p>}
      </article>

      <article className="panel">
        <h2>训练数据路线</h2>
        <p><b>Wikidata</b>：大规模人物基础字段与可追溯实体 ID。</p>
        <p><b>OpenAlex / MusicBrainz</b>：按职业补作品、机构与创作时间线。</p>
        <p><b>Biography text</b>：把 revision-pinned 传记抽成标准 life-event timeline。</p>
        <p><b>Astro-Databank</b>：只作为高质量出生时辰研究层，并严格遵守其授权。</p>
        <p><b>用户预测账本</b>：未来真正发生后形成最重要的前瞻验证集。</p>
      </article>

      <article className="panel">
        <h2>模型分层</h2>
        <ol>
          <li>BaZi feature engine：只计算，不解释。</li>
          <li>Traditional prior：把流派规则转成可量化 hypotheses。</li>
          <li>Calibration：过去经历与高信息量问答更新 posterior。</li>
          <li>Biography retrieval：找相似早期人生，而不是“像某名人”。</li>
          <li>Trajectory models：人生类型 + 多事件 hazard + sequence model。</li>
          <li>Narrative layer：LLM 只负责把模型结果写成“命书”。</li>
        </ol>
      </article>
    </section>

    <section className="tests">
      {tests.map(([a,b])=><article key={a}><small>{a}</small><h3>{b}</h3></article>)}
    </section>

    <section className="panel ledger">
      <div><div className="eyebrow">NON-NEGOTIABLE</div><h2>过去只能校准，未来才算预测。</h2></div>
      <pre>{`prediction_id: mg_2026_xxxx
created_at: 2026-10-02T...
information_cutoff: 2026-10-02
horizon: age 25–35
claim: "major cross-domain project reaches public release"
probability: 0.68
validation: public product / paper / portfolio exists
outcome: locked until horizon review`}</pre>
    </section>
  </main>
}