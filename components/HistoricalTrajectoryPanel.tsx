"use client";

import {useMemo,useState} from "react";
import {historicalDomains,simulateHistoricalDocumentedPaths,type HistoricalDomain} from "../lib/historical-trajectory";
import styles from "./historical-trajectory.module.css";

const names:Record<HistoricalDomain,string>={
  career:"职业",recognition:"荣誉",relationship:"关系",other:"其他作品/活动",
};
const labels:{d:HistoricalDomain;color:string}[]=[
  {d:"career",color:"#d58d66"},
  {d:"recognition",color:"#dcc48f"},
  {d:"relationship",color:"#87a5a2"},
  {d:"other",color:"#907eaa"},
];
const fmt=(n:number)=>n.toFixed(n<1?2:1);
const horizons=[5,10,20] as const;

export default function HistoricalTrajectoryPanel({fromAge}:{fromAge:number}){
  const [horizon,setHorizon]=useState<5|10|20>(10);
  const [showPaths,setShowPaths]=useState(false);
  const data=useMemo(()=>simulateHistoricalDocumentedPaths({fromAge,horizon,sampleCount:1200,seed:20261015}),[fromAge,horizon]);
  const max=Math.max(.1,...data.stages.map(s=>s.expectedDocumentedRecords));
  return <section className={styles.card} aria-label="历史人物传记轨迹模拟">
    <div className={styles.head}>
      <div>
        <div className={styles.eyebrow}>RESEARCH ENGINE · R8</div>
        <h3>数据模型怎样展开一段人生？</h3>
        <p>下面是从真实历史传记训练出的年龄分布，进行的多年度<strong>研究模拟</strong>。它模拟的是“传记里留下多少事件记录”，<strong>不是你会经历什么</strong>。</p>
      </div>
      <span className={styles.status}>开发实验 · 未校准个人预测</span>
    </div>
    <div className={styles.horizons}>
      <strong>观察多少年</strong>
      <div>
      {horizons.map(h=><button type="button" key={h} onClick={()=>{setHorizon(h);setShowPaths(false)}}
        aria-pressed={h===horizon} className={h===horizon?styles.active:styles.inactive}>{h} 年</button>)}
      </div>
    </div>
    <div className={styles.overview}>
      <div><small>覆盖的年龄</small><strong>{data.fromAge}–{data.toAgeExclusive-1} 岁</strong></div>
      <div><small>模型预期的传记记录条数</small><strong>{fmt(data.meanExpectedRecords)}</strong></div>
      <div><small>模拟路径的第 10 / 50 / 90 百分位</small><strong>{data.quantiles.p10} / {data.quantiles.p50} / {data.quantiles.p90}</strong></div>
    </div>
    <div className={styles.chart} role="img"
      aria-label={"历史传记研究模型将未来分为 "+data.stages.length+" 个阶段；记录数不是实际生活发生率"}>
      {data.stages.map(stage=><div className={styles.stage} key={stage.fromAge}>
        <div className={styles.stageTop}><b>{stage.fromAge}–{stage.toAgeExclusive-1} 岁</b>
          <span>{fmt(stage.expectedDocumentedRecords)} 条</span></div>
        <div className={styles.track}>
          <div className={styles.fill} style={{width:Math.max(2,stage.expectedDocumentedRecords/max*100)+"%"}}>
            {labels.map(({d,color})=><span key={d} style={{
              flexGrow:stage.domainExpectedDocumentedRecords[d],
              backgroundColor:color,
              display:stage.domainExpectedDocumentedRecords[d]>0?"block":"none"
            }}/>)}
          </div>
        </div>
      </div>)}
    </div>
    <div className={styles.legend}>{labels.map(x=><span key={x.d}><i style={{backgroundColor:x.color}}/>{names[x.d]}</span>)}</div>
    <button className={styles.details} type="button" onClick={()=>setShowPaths(x=>!x)} aria-expanded={showPaths}>
      {showPaths?"收起模拟样本":"展开看看模型生成的三条不同记录路径"} <span>{showPaths?"↑":"↓"}</span>
    </button>
    {showPaths?<div className={styles.samples}>{data.illustrativePaths.map(path=><div className={styles.sample} key={path.label}>
      <small>{path.label} · 模拟的传记记录 {path.count} 条</small>
      {path.events.length? <div className={styles.events}>{path.events.slice(0,12).map((ev,i)=>
        <div key={i}><b>{ev.age} 岁</b><span>{names[ev.domain]}类记录</span></div>)}
        {path.events.length>12?<p>还有 {path.events.length-12} 条省略</p>:null}
        </div>:<p>此条模拟路径没有留下模型定义的相关记录。**不代表没有生活经历。**</p>}
    </div>)}</div>:null}
    <div className={styles.disclosure}>
      <b>怎样理解这张图？</b> 使用 R6 冻结训练集的年龄分段 Poisson 速率，重复随机生成 {data.sampledPaths.toLocaleString()} 条可能的<strong>传记记录序列</strong>。没有使用你的出生地、八字、个人经历或职业状况来改变速率；这些数字不能解释成你的个人命运概率。名人选择偏差、传记遗漏、事件相关性、生存与长期滚动校准尚未解决。
      <p>来源：固定快照 {data.sourceSnapshot.slice(0,8)}… · 训练暴露 {data.trainingPersonYears.toLocaleString()} 人物年份。仅支持 18–87 岁，超龄截断、不外推。</p>
    </div>
  </section>;
}
