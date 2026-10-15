"use client";

import {useMemo,useState} from "react";
import {calculateBazi} from "../lib/bazi";
import {annualPillarAfterLichun} from "../lib/traditional-luck-cycles";
import {explainYear} from "../lib/traditional-relation-graph";
import {
  makeReading,validatedBirth,areaNames,eventNames,evidenceDomainNames,
  type PublicReading,type ReadingInput,type RecordedEvent,type PastKind,type DesiredArea
} from "../lib/public-reading";
import styles from "./public-reading.module.css";

const empty:ReadingInput={
  birthDate:"", birthPlace:"", knownBirthTime:false, birthTime:"",
  pastEvents:[],focus:"undecided"
};
const kinds=Object.keys(eventNames) as PastKind[];
const focuses=Object.keys(areaNames) as DesiredArea[];
const pad=(n:number)=>String(n).padStart(2,"0");
function localDate(){
  const d=new Date();return [d.getFullYear(),pad(d.getMonth()+1),pad(d.getDate())].join("-");
}
type DisplayReport={reading:PublicReading;input:ReadingInput};

export default function Analyzer(){
  const [draft,setDraft]=useState<ReadingInput>(empty);
  const [step,setStep]=useState(0);
  const [error,setError]=useState("");
  const [report,setReport]=useState<DisplayReport|null>(null);
  const [detail,setDetail]=useState(false);
  const [copied,setCopied]=useState(false);
  const [scenario,setScenario]=useState<"continue"|"change"|"unknown">("continue");

  const birthAge=useMemo(()=>{
    if(!draft.birthDate)return null;
    try{return validatedBirth(draft.birthDate,localDate()).age}catch{return null}
  },[draft.birthDate]);

  function change(next:Partial<ReadingInput>){
    setDraft(prev=>({...prev,...next}));
    setError("");
  }
  function forward(){
    if(step===0){
      try{
        validatedBirth(draft.birthDate,localDate());
        if(draft.knownBirthTime&&!/^([01]\d|2[0-3]):[0-5]\d$/.test(draft.birthTime)) {
          throw new Error("请输入正确的出生时间，或选择「不知道」");
        }
      }catch(e){setError(e instanceof Error?e.message:"日期不正确");return}
    }
    setError("");setStep(x=>Math.min(x+1,2));
  }
  function addEvent(){
    const newEvent:RecordedEvent={id:"e-"+Date.now()+"-"+draft.pastEvents.length,age:Math.min(18,birthAge??18),kind:"study",note:""};
    change({pastEvents:[...draft.pastEvents,newEvent]});
  }
  function updateEvent(id:string,partial:Partial<RecordedEvent>){
    change({pastEvents:draft.pastEvents.map(e=>e.id===id?{...e,...partial}:e)});
  }
  function produce(){
    try{
      const current=structuredClone(draft);
      const reading=makeReading(current,localDate());
      setReport({reading,input:current});setDetail(false);setStep(3);setError("");
    }catch(e){setError(e instanceof Error?e.message:"报告暂时无法生成")}
  }
  function showDemo(){
    const example:ReadingInput={
      birthDate:"1995-06-15",birthPlace:"示例城市（虚构）",knownBirthTime:false,birthTime:"",
      focus:"career",
      pastEvents:[
        {id:"demo-1",age:18,kind:"study",note:"进入新的学校"},
        {id:"demo-2",age:24,kind:"move",note:"搬到另一座城市"},
        {id:"demo-3",age:28,kind:"work",note:"决定调整工作方向"},
      ],
    };
    setDraft(example);
    setReport({reading:makeReading(example,localDate()),input:example});
    setStep(3);setError("");
  }

  async function copyReport(r:DisplayReport){
    const lines=[
      "命轨 | 个人研究报告（非经过验证的命运预测）",
      "截止日期："+r.reading.asOf,
      ...r.reading.narrative,
      ...r.reading.facts.map(e=>e.age+"岁："+eventNames[e.kind]+(e.note?" — "+e.note:"")),
      "接下来关注："+r.reading.focusName,
      "未来情景：继续现状 / 尝试改变 / 保留不确定性（非概率预测）",
      "历史数据仅是特定传记记录密度，不能推断个人命运。",
      "传统解释为文化符号展示；未获独立预测准确率支持。",
      "研究协议："+r.reading.protocol,
    ];
    try{
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopied(true);
    }catch{setError("复制未成功，可手动选中文本保存。")}
  }

  // Unverified civil-time input is never used for a *DaYun* claim.
  const symbolic=useMemo(()=>{
    if(!report?.input.knownBirthTime)return null;
    try{
      const [y,m,d]=report.input.birthDate.split("-").map(Number);
      const [h,min]=report.input.birthTime.split(":").map(Number);
      const chart=calculateBazi({year:y,month:m,day:d,hour:h,minute:min,knownTime:true});
      const year=Number(report.reading.asOf.slice(0,4));
      const annual=annualPillarAfterLichun(year);
      return {
        chart,annual,
        relations:explainYear({
          year:chart.pillars.year,month:chart.pillars.month,
          day:chart.pillars.day,hour:chart.pillars.time??chart.pillars.day,
        },null,annual)
      };
    }catch{return null}
  },[report]);

  if(report){
    const r=report.reading;
    const focusText=r.focus==="undecided"?"你尚未确定最关注哪件事。":"你目前最想了解的是「"+r.focusName+"」。";
    const scenarioContent={
      continue:{title:"如果沿着现在的路径走",body:"可以先梳理已经积累的能力、关系与资源，记录未来一年实际发生的变化。这里描述的是一种可选择的情景，而非推断它必定发生。"},
      change:{title:"如果你决定主动改变",body:"可以明确准备转向的目标、成本和触发条件；日后对照实际选择与结果。这一分支不代表传统命理认为转变概率更高。"},
      unknown:{title:"如果未来暂时没有明确方向",body:"先保留多种可能性，不强行指定结婚、发财、职业突破的年份。随着新的真实经历出现，下一次报告再更新。"},
    };
    return <section className={styles.layout}>
      <div className={styles.strap}>
        <span className={styles.kicker}>MINGGUI / 个人命轨书 · 研究预览</span>
        <button className={styles.lightButton} onClick={()=>{setReport(null);setStep(0);setCopied(false)}}>← 修改我的资料</button>
      </div>
      <div className={styles.reportHero}>
        <div className={styles.seal}>命轨</div>
        <div><p className={styles.kicker}>PERSONAL LIFE MAP · EVIDENCE FIRST</p>
          <h2>先看走过的路，<br/>再谈未走的路。</h2>
          <p>截至 {r.asOf} · {r.age} 岁 · {report.input.birthPlace||"未填写城市"}</p>
        </div>
      </div>

      <div className={styles.three}>
        <div className={styles.stat}><small>你记录的关键经历</small><strong>{r.facts.length} 件</strong><span>来自你的填写</span></div>
        <div className={styles.stat}><small>目前最关注</small><strong className={styles.smaller}>{r.focusName}</strong><span>未来选择，而非注定事件</span></div>
        <div className={styles.stat}><small>经过验证的个人预测概率</small><strong className={styles.smaller}>暂不提供</strong><span>尚缺独立外部验证</span></div>
      </div>

      <div className={styles.grid}>
        <article className={styles.card}>
          <div className={styles.kicker}>01 · 已经发生 / FACTS</div>
          <h3>你的人生年表</h3>
          <p className={styles.sub}>这里都是你输入的往事。系统不会把事后了解的事情记成自己“算准了”。</p>
          <div className={styles.lifeLine}>
            {r.facts.length? r.facts.map(ev=><div className={styles.lifeItem} key={ev.id}>
              <b>{ev.age} 岁</b>
              <div><strong>{eventNames[ev.kind]}</strong>{ev.note?<p>{ev.note}</p>:null}</div>
            </div>):<div className={styles.quiet}>你还没有填写经历。这一部分会保持空白，而不是自动编造故事。</div>}
          </div>
          <p className={styles.sub}>{r.narrative[0]}</p>
        </article>

        <article className={styles.card}>
          <div className={styles.kicker}>02 · 尚未发生 / POSSIBILITIES</div>
          <h3>未来不是只有一条线</h3>
          <p className={styles.sub}>{focusText} 我们先展示可讨论的选择，不把它们包装成预测概率。</p>
          <div className={styles.choices}>
            {([
              ["continue","延续现在"],["change","主动转向"],["unknown","保持开放"],
            ] as const).map(([key,label])=><button
              key={key} className={scenario===key?styles.selected:styles.choice}
              onClick={()=>setScenario(key)}>{label}</button>)}
          </div>
          <div className={styles.scenario}>
            <h4>{scenarioContent[scenario].title}</h4>
            <p>{scenarioContent[scenario].body}</p>
            <small>情景分析 · 没有概率排名 · 不代表具体事件会发生</small>
          </div>
          <p className={styles.sub}>下一次更新时，可把后来真正发生的经历补入年表；旧报告的预测须另外留存，不能事后重写。</p>
        </article>
      </div>

      <div className={styles.grid}>
        <article className={styles.card}>
          <div className={styles.kicker}>03 · 传统视角 / CULTURAL LENS</div>
          <h3>用传统语言读懂命盘</h3>
          {!report.input.knownBirthTime?<p className={styles.sub}>你选择了“不知道出生时辰”。为了不假装知道时柱与起运，我们暂不出具涉及日柱、时柱和大运的个人解读。你仍然可以查看独立的示例推演。</p>: symbolic?<>
            <div className={styles.pillars}>{([
              ["年",symbolic.chart.pillars.year],["月",symbolic.chart.pillars.month],
              ["日",symbolic.chart.pillars.day],["时",symbolic.chart.pillars.time??"未知"]
            ] as const).map(([name,p])=><div key={name}><small>{name}柱</small><strong>{p}</strong></div>)}</div>
            <p className={styles.sub}>日主：{symbolic.chart.dayMaster} · 当年立春后流年：{symbolic.annual}。</p>
            <p className={styles.sub}>{symbolic.relations.length? "收录的合冲符号关系："+symbolic.relations.slice(0,4).map(x=>x.source+"与"+x.target+" "+x.explanation).join("；")+"。":"按目前收录的合冲定义，这一年度没有触发对应关系。"}</p>
            <p className={styles.caveat}>暂按所填当地钟表时间排盘，未经地点、时区、夏令时及历法边界核验，属于条件性符号演示；不计算个人大运，更不推断吉凶。</p>
          </>:<p className={styles.sub}>该日期暂时无法可靠排盘，因此不提供传统结果。</p>}
          <a className={styles.textLink} href="/research/traditional-demo">查看完整的大运流年交互演示 →</a>
        </article>
        <article className={styles.card}>
          <div className={styles.kicker}>04 · 科学依据 / RESEARCH</div>
          <h3>历史数据到底能告诉我们什么？</h3>
          <p className={styles.sub}>研究模型分析的是被收录到传记里的重大事件，而不是普通人生活中所有真实发生的事情。</p>
          {r.reference?<div className={styles.researchFacts}>
            <p>当前年龄对应研究阶段：<strong>{r.reference.label} 岁</strong></p>
            <p>该年龄段训练资料覆盖 <strong>{r.reference.eligibleTrainPersonYears.toLocaleString()} 个人物年份</strong>。</p>
            <details><summary>展开历史记录密度（仅研究参考）</summary>
              <p className={styles.sub}>每 1,000 个研究人物年份，模型估计的传记事件条数（不是你的发生概率）：</p>
              {(["career","recognition","relationship","other"] as const).map(k=><div className={styles.rate} key={k}><span>{evidenceDomainNames[k]}</span><b>{r.reference?.eventsPer1000ResearchPersonYears[k]}</b></div>)}
              <p className={styles.caveat}>不能把你填写的生活经历数量直接代入这个名人传记模型：两种事件的记录方式不同。</p>
            </details>
          </div>:<p className={styles.caveat}>当前年龄不在模型的有效研究范围内，不展示外推统计。</p>}
          <p className={styles.caveat}>目前八字动态规则尚未证实能提高预测准确性。传统层不能获得额外的个人概率权重。</p>
          <button className={styles.lightButton} onClick={()=>setDetail(x=>!x)}>{detail?"收起":"查看"}研究说明</button>
          {detail?<div className={styles.researchFacts}>
            <p><b>R6：</b>历史传记年度模型在开发验证中改善了记录事件的预测误差，但未证明可预测普通人的人生。</p>
            <p><b>R7B：</b>命局结构 × 流年关系的初步实验没有优于年龄基线。</p>
            <p><b>方法：</b>冻结数据、人物隔离、测试错位流年；目前仍缺外部全新人群、可信的时间边界和长期路径校准。</p>
            <a className={styles.textLink} href="/research">进入研究实验室 →</a>
          </div>:null}
        </article>
      </div>
      {error?<p className={styles.error} role="alert">{error}</p>:null}
      <div className={styles.bottom}><p>数据仅在当前页面处理，不会因生成本报告而自动上传或存储。</p><button className={styles.primary} onClick={()=>void copyReport(report)}>{copied?"已复制摘要":"复制我的报告摘要"}</button></div>
    </section>
  }

  return <section className={styles.layout}>
    <div className={styles.intro}>
      <div className={styles.kicker}>MINGGUI / 命轨 · NEW READING</div>
      <h2>看见人生的多种可能。</h2>
      <p>不用懂八字，也不用回答几十道问题。只需出生资料和少量经历，我们先整理你的真实人生，再告诉你：哪些是传统解释，哪些有研究依据，哪些还无法预测。</p>
    </div>
    <div className={styles.steps}>
      {["出生资料","走过的经历","最想了解的未来"].map((label,i)=>
        <span key={label} className={step===i?styles.stepActive:styles.step}>{pad(i+1)} · {label}</span>)}
    </div>
    <div className={styles.inputCard}>
      {step===0?<div>
        <div className={styles.kicker}>STEP 01 / FROM WHERE YOU BEGIN</div>
        <h3>先告诉我，你何时出生？</h3>
        <p className={styles.sub}>不需要准确家庭地址。时辰不知道就如实选择不知道，绝不自动补一个时辰。</p>
        <label className={styles.field}>出生日期 <input type="date" min="1850-01-01" max={localDate()} value={draft.birthDate} onChange={e=>change({birthDate:e.target.value})}/></label>
        <label className={styles.field}>出生城市（选填）<input value={draft.birthPlace} maxLength={80} placeholder="例如：贵阳" onChange={e=>change({birthPlace:e.target.value})}/></label>
        <label className={styles.toggle}><input type="checkbox" checked={draft.knownBirthTime} onChange={e=>change({knownBirthTime:e.target.checked})}/> 我知道出生的具体时间</label>
        {draft.knownBirthTime?<label className={styles.field}>当地出生时间 <input type="time" value={draft.birthTime} onChange={e=>change({birthTime:e.target.value})}/></label>:<p className={styles.sub}>没关系，不知道时辰也能做以真实经历为核心的报告。传统命盘会保留未知部分。</p>}
        <button className={styles.secondary} onClick={showDemo}>先看一份虚构人物的示例报告</button>
      </div>:step===1?<div>
        <div className={styles.kicker}>STEP 02 / WHAT HAS HAPPENED</div>
        <h3>有什么事情，改变过你的人生方向？</h3>
        <p className={styles.sub}>不必把所有往事列出来。你可以填写 0–30 件重要经历，作为个人时间线。不会把这些事当成模型“预测成功”。</p>
        <div className={styles.eventRows}>{draft.pastEvents.map(e=>
          <div className={styles.eventRow} key={e.id}>
            <label>年龄<input type="number" min={0} max={birthAge??120} value={e.age} onChange={x=>updateEvent(e.id,{age:Number(x.target.value)})}/></label>
            <label>发生了什么<select value={e.kind} onChange={x=>updateEvent(e.id,{kind:x.target.value as PastKind})}>{kinds.map(k=><option value={k} key={k}>{eventNames[k]}</option>)}</select></label>
            <label className={styles.eventNote}>一句话（可留空）<input value={e.note} maxLength={240} placeholder="例如：换了一座城市" onChange={x=>updateEvent(e.id,{note:x.target.value})}/></label>
            <button className={styles.remove} aria-label="删除这条经历" onClick={()=>change({pastEvents:draft.pastEvents.filter(x=>x.id!==e.id)})}>×</button>
          </div>)}</div>
        <button className={styles.secondary} disabled={draft.pastEvents.length>=30} onClick={addEvent}>＋ 添加一件经历</button>
        <p className={styles.sub}>跳过也可以。人生没有被记录，不代表人生没有发生。</p>
      </div>:<div>
        <div className={styles.kicker}>STEP 03 / THE UNWRITTEN PART</div>
        <h3>如果只问一个问题，你最想知道什么？</h3>
        <p className={styles.sub}>只是选择报告关注点，并不会改变模型对某件事发生概率的判断。</p>
        <div className={styles.focusChoices}>{focuses.map(f=>
          <button key={f} onClick={()=>change({focus:f})} className={draft.focus===f?styles.focusSelected:styles.focus}>{areaNames[f]}</button>)}</div>
        <div className={styles.notice}><b>我们会明确告诉你：</b>哪些内容来自你自己，哪些来自传统命理，哪些来自历史研究，以及哪些目前没有足够证据预测。</div>
      </div>}
      {error?<p className={styles.error} role="alert">{error}</p>:null}
      <div className={styles.controls}>
        {step>0?<button onClick={()=>{setStep(s=>s-1);setError("")}} className={styles.secondary}>← 上一步</button>:<span/>}
        {step<2?<button onClick={forward} className={styles.primary}>继续 →</button>:<button onClick={produce} className={styles.primary}>展开我的命轨书 →</button>}
      </div>
    </div>
    <p className={styles.footerNote}>当前为科研原型。不会通过输入表单自动上传个人资料；也不会编造已发生的事件、配偶、财富或寿命。</p>
  </section>;
}
