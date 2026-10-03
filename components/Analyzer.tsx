"use client";

import { useMemo, useState } from "react";
import { calculateBazi } from "../lib/bazi";
import { calibrate, heuristicBranches, stageNarrative, traitLabels, traditionalPrior, type CalibrationAnswers, type TraitKey } from "../lib/model";

const pct = (x: number) => `${Math.round(x * 100)}%`;

export default function Analyzer() {
  const [birth, setBirth] = useState({ date: "2004-02-03", time: "12:00", knownTime: false, place: "贵阳", gender: "male" });
  const [answers, setAnswers] = useState<CalibrationAnswers>({ underPressure:"research", projectMode:"system", biggestFear:"direction", consistency:3, mobility:4 });
  const [submitted, setSubmitted] = useState(false);

  const result = useMemo(() => {
    const [y,m,d] = birth.date.split("-").map(Number);
    const [hh,mm] = birth.time.split(":").map(Number);
    if (!y || !m || !d) return null;
    const chart = calculateBazi({ year:y, month:m, day:d, hour:hh, minute:mm, knownTime:birth.knownTime });
    const prior = traditionalPrior(chart);
    const posterior = calibrate(prior, answers);
    const branches = heuristicBranches(posterior);
    return { chart, prior, posterior, branches };
  }, [birth, answers]);

  return (
    <div className="analyzer-grid">
      <section className="panel form-panel">
        <div className="eyebrow">INPUT / 输入</div>
        <h2>先给命盘，再给过去。</h2>
        <label>出生日期<input type="date" value={birth.date} onChange={e=>setBirth({...birth,date:e.target.value})}/></label>
        <div className="row"><label className="check"><input type="checkbox" checked={birth.knownTime} onChange={e=>setBirth({...birth,knownTime:e.target.checked})}/>知道出生时间</label><input type="time" disabled={!birth.knownTime} value={birth.time} onChange={e=>setBirth({...birth,time:e.target.value})}/></div>
        <label>出生地点<input value={birth.place} onChange={e=>setBirth({...birth,place:e.target.value})} placeholder="城市即可"/></label>

        <hr/>
        <h3>高信息量校准</h3>
        <label>压力大时你更常做什么？<select value={answers.underPressure} onChange={e=>setAnswers({...answers,underPressure:e.target.value as CalibrationAnswers["underPressure"]})}><option value="research">疯狂查资料 / 想更多</option><option value="act">先行动再说</option><option value="avoid">逃避 / 延后</option><option value="ask">找人讨论 / 借外力</option></select></label>
        <label>做项目更像哪种？<select value={answers.projectMode} onChange={e=>setAnswers({...answers,projectMode:e.target.value as CalibrationAnswers["projectMode"]})}><option value="system">先想完整系统</option><option value="prototype">先做最小可用版本</option><option value="switch">容易开很多坑 / 换方向</option><option value="steady">慢但稳定推进</option></select></label>
        <label>你最怕哪类失败？<select value={answers.biggestFear} onChange={e=>setAnswers({...answers,biggestFear:e.target.value as CalibrationAnswers["biggestFear"]})}><option value="direction">没有方向</option><option value="money">经济不安全</option><option value="status">被否定 / 没有地位</option><option value="relationship">重要关系失控</option><option value="wasted">努力很久却没有结果</option></select></label>
        <label>长期坚持能力：{answers.consistency}/5<input type="range" min="1" max="5" value={answers.consistency} onChange={e=>setAnswers({...answers,consistency:Number(e.target.value)})}/></label>
        <label>你对迁移/换环境的接受度：{answers.mobility}/5<input type="range" min="1" max="5" value={answers.mobility} onChange={e=>setAnswers({...answers,mobility:Number(e.target.value)})}/></label>
        <button className="button primary wide" onClick={()=>setSubmitted(true)}>展开命轨</button>
        <p className="fine">当前公开预览仅运行“传统先验 + 个人校准”。历史人物训练层尚未接入时不会伪造案例概率。</p>
      </section>

      <section className="panel report-panel">
        {!submitted || !result ? <div className="empty"><span className="seal big">轨</span><h2>等待展开</h2><p>我们会先展示命理先验，然后让你看到校准到底改了什么。</p></div> : <>
          <div className="report-head"><div><div className="eyebrow">命轨书 / RESEARCH PREVIEW</div><h2>{birth.date} · {birth.place}</h2></div><span className="status">未接历史模型</span></div>

          <div className="pillars">
            {Object.entries(result.chart.pillars).map(([k,v])=><div key={k}><small>{k.toUpperCase()}</small><strong>{v ?? "未知"}</strong></div>)}
          </div>
          <p className="muted">日主 {result.chart.dayMaster} · 出生时间{result.chart.knownTime?"已知":"未知，因此时柱与起运相关判断不进入结果"}</p>

          <h3>一、传统先验 → 个人校准</h3>
          <div className="traits">
            {(Object.keys(result.prior) as TraitKey[]).map(k=><div className="trait" key={k}><div className="trait-name"><b>{traitLabels[k].zh}</b><small>{traitLabels[k].desc}</small></div><div className="bars"><span style={{width:pct(result.prior[k])}} className="bar prior"></span><span style={{width:pct(result.posterior[k])}} className="bar posterior"></span></div><div className="score"><span>{pct(result.prior[k])}</span><b>→ {pct(result.posterior[k])}</b></div></div>)}
          </div>
          <div className="legend"><span><i className="dot prior-dot"/>命理先验</span><span><i className="dot post-dot"/>个人校准后</span></div>

          <h3>二、当前最可能的人生结构</h3>
          <div className="branches">
            {result.branches.map((b,i)=><article key={b.name}><span className="rank">0{i+1}</span><div><h4>{b.name}<em>{pct(b.probability)}</em></h4><p>{b.summary}</p><small>关键节点：{b.hinge}</small></div></article>)}
          </div>
          <p className="warning">这里的分支概率目前只是规则校准后的启发式权重，不是历史数据库训练结果。真正上线前必须由人物生平模型替换。</p>

          <h3>三、一生长卷（当前个体结构版）</h3>
          <div className="timeline">
            {[10,20,30,40,50,60,70].map((a,i)=><div key={a}><span>{i===0?"0–20":`${a}–${a+10}`}</span><p>{stageNarrative(i===0?18:a+5,result.posterior)}</p></div>)}
          </div>

          <h3>四、证据构成</h3>
          <div className="evidence"><div><b>35%</b><span>传统命理先验</span></div><div><b>65%</b><span>个人校准问答</span></div><div className="disabled"><b>—</b><span>历史人物数据库（待训练）</span></div></div>
        </>}
      </section>
    </div>
  )
}
