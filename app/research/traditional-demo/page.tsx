"use client";

import { useMemo, useState } from "react";
import { annualPillarAfterLichun, auditedYunTimeline } from "../../../lib/traditional-luck-cycles";
import { explainYear, relationText, stemTenGod } from "../../../lib/traditional-relation-graph";
import styles from "./demo.module.css";

// FICTIONAL chart fixture. Not a user's chart or verified historical record.
const DEMO_BIRTH = {
  year: 1995, month: 6, day: 15, hour: 10, minute: 35,
  localCivilTimeVerified: true as const,
  timezoneProvenance: "SYNTHETIC DEMO: Asia/Shanghai assumed wall clock, not source verified",
  birthTimeSourceGrade: "other" as const,
  conventionalYunGender: "male" as const,
  yunSect: 1 as const,
  eightCharSect: 2 as const,
};

const startYear=2020;
const endYear=2060;
const arms=[
  {name:"仅年龄",relationship:0.05073226176372906,career:0.14576343296041835},
  {name:"加入命局结构",relationship:0.05115121605821423,career:0.14622218316085794},
  {name:"再加入真实流年冲合",relationship:0.051300336243086546,career:0.1464863759107583},
];

export default function TraditionalDemoPage(){
  const [year,setYear]=useState(2026);
  const chart=useMemo(()=>auditedYunTimeline(DEMO_BIRTH),[]);
  const annual=useMemo(()=>annualPillarAfterLichun(year),[year]);
  const period=chart.periods.find(p=>p.pillar&&p.startYear<=year&&year<=p.endYear)??null;
  const luck=period?.pillar??null;
  const age=year-DEMO_BIRTH.year;
  const rules=useMemo(()=>explainYear(chart.natal,luck,annual),[chart.natal,luck,annual]);
  const natalPillars=[
    {name:"年柱",value:chart.natal.year},
    {name:"月柱",value:chart.natal.month},
    {name:"日柱",value:chart.natal.day},
    {name:"时柱",value:chart.natal.hour},
  ];
  const annualTenGod=stemTenGod(chart.natal.dayMaster,annual[0]);
  const luckTenGod=luck?stemTenGod(chart.natal.dayMaster,luck[0]):"未入运";

  return (
    <main className={"shell " + styles.main}>
      <header className={styles.head}>
        <div>
          <div className="eyebrow">MINGGUI / TRADITIONAL INFERENCE LAB</div>
          <h1>看见规则如何推演，<br/>而不是只听结果。</h1>
          <p>以一份虚构出生资料展示：固定命局之后，移动年份，根据历法引擎切换大运与流年；观察十神、合与冲在哪里触发。下方的真实验证成绩与符号推演严格分离。</p>
        </div>
        <span className={styles.tag}>研究演示 · 并非个人命书</span>
      </header>

      <div className={styles.two}>
        <section className={styles.panel} aria-label="动态八字推演">
          <div className={styles.label}>01 / NATAL CHART</div>
          <h2 className={styles.sectionTitle}>命局不动，岁运流转</h2>
          <div className={styles.pillars}>
            {natalPillars.map(p=>(
              <div key={p.name} className={styles.pillar}>
                <span>{p.name}</span><strong>{p.value[0]}<br/>{p.value[1]}</strong>
                <em>{p.name==="日柱"?"日主":stemTenGod(chart.natal.dayMaster,p.value[0])}</em>
              </div>
            ))}
          </div>
          <div className={styles.controls}>
            <div>
              <div className={styles.label}>02 / TIME SCROLL</div>
              <div className={styles.year}>{year} <span className={styles.small}>公历 · 约 {age} 岁</span></div>
            </div>
            <div style={{display:"flex",gap:8}}>
              <button className={styles.button} disabled={year===startYear} onClick={()=>setYear(y=>Math.max(startYear,y-1))} aria-label="上一年">←</button>
              <button className={styles.button} disabled={year===endYear} onClick={()=>setYear(y=>Math.min(endYear,y+1))} aria-label="下一年">→</button>
            </div>
          </div>
          <input aria-label="选择查看的年份" className={styles.range} type="range"
            min={startYear} max={endYear} value={year} onChange={e=>setYear(Number(e.target.value))}/>
          <div className={styles.axis}><span>2020</span><span>2040</span><span>2060</span></div>
          <div className={styles.cycle}>
            <div className={styles.cycleCard}>
              <div>大运 · D A Y U N</div>
              <strong>{luck??"—"}</strong>
              <span>{period?period.startYear+"–"+period.endYear+" · "+luckTenGod:"尚未匹配大运段"}</span>
            </div>
            <div className={styles.cycleCard}>
              <div>流年 · A N N U A L</div>
              <strong>{annual}</strong>
              <span>{annualTenGod} · 立春后年柱</span>
            </div>
          </div>

          <div className={styles.label}>03 / SYMBOLIC RULE GRAPH</div>
          <h2 className={styles.sectionTitle}>本年触发的传统关系 <span className={styles.small}>({rules.length})</span></h2>
          {rules.length ? rules.slice(0,12).map((r,i)=>(
            <div className={styles.relation} key={r.source+"-"+r.target+"-"+r.kind+"-"+i}>
              <span className={styles.symbol}>{r.signs}</span>
              <div>
                <b>{relationText[r.kind]}</b>
                <p>{r.source} × {r.target} · 结构对应，不代表吉凶或必然发生事件</p>
              </div>
            </div>
          )):<p className={styles.empty}>当前演示年份没有触发本模块收录的合、冲或同柱关系。不能据此推断现实中没有人生变化。</p>}
          {rules.length>12?<p className={styles.small}>另有 {rules.length-12} 条关系未在紧凑视图中展开。</p>:null}
          <div className={styles.notice}>
            演示采用虚构的 1995-06-15 10:35 当地钟表时间与固定传统起运约定，不对应真实人物。历法显示的是年份立春后的年柱，不能覆盖该年一月和立春前的精细事件判定。这里展示的是<strong>规则激活</strong>，不是经过验证的事件概率。
          </div>
        </section>

        <aside className={styles.panel}>
          <div className={styles.label}>04 / EVIDENCE LEDGER</div>
          <h2 className={styles.sectionTitle}>传统推演，与实证成绩分开</h2>
          <div className={styles.metric}>
            <div className={styles.stat}><small>验证人物年份</small><b>24,464</b><small>R7B 人物级数据隔离</small></div>
            <div className={styles.stat}><small>实际增量提升</small><b className={styles.bad}>未检出</b><small>职业和关系目标均未改善</small></div>
          </div>
          <table className={styles.scoretable}>
            <thead><tr><th>模型</th><th>关系 Log-loss</th><th>职业 Log-loss</th></tr></thead>
            <tbody>{arms.map((row,i)=>(
              <tr key={row.name}>
                <td>{row.name}</td>
                <td className={i===0?styles.good:styles.bad}>{row.relationship.toFixed(5)}</td>
                <td className={i===0?styles.good:styles.bad}>{row.career.toFixed(5)}</td>
              </tr>
            ))}</tbody>
          </table>
          <p className={styles.foot}>分数越小越好。命局结构包括日主五行、月支与日支六冲；流年使用公历年近似而不是完整立春边界。该实验尚未加入真实大运周期，因此它不是完整传统命理的检验。</p>
          <div className={styles.notice}>
            <b>模型结论：</b>仅从这份历史名人数据的初步对照来看，新增的命理组合没有稳定改善对传记事件记录的预测。更复杂的传统解释不应自动转化为更高的预测概率。
          </div>
          <p className={styles.foot}>
            <a className={styles.link} href="https://github.com/wzj003243-dotcom/minggui-life-trajectory/tree/research/bazi-interactions-r7b/research/traditional" target="_blank" rel="noreferrer">
              查看规则、实验数据与可复验代码 ↗
            </a>
          </p>
          <div className={styles.legend}><span className={styles.dot}/> 当前版本只展示有明确算法定义的规则，不展示未经实证的断语</div>
        </aside>
      </div>
    </main>
  );
}
