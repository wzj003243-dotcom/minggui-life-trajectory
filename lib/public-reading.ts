/** Transparent, user-facing reading contract.
 * No inferred personal fate or unvalidated likelihoods in this module.
 * The account of past events is a *user-provided fact*, not prediction success.
 */
import research from "../research/benchmarks/results/v12_r6_dev_lifetime_lookup.json";

export type LifeArea = "career" | "relationship" | "recognition" | "other";
export type PastKind = "study" | "work" | "move" | "relationship" | "family" | "project" | "recognition" | "setback";
export type DesiredArea = "career" | "relationship" | "learning" | "home" | "undecided";
export type RecordedEvent = {id:string; age:number; kind:PastKind; note:string};

export interface ReadingInput {
  birthDate:string;
  birthPlace:string;
  knownBirthTime:boolean;
  birthTime:string;
  pastEvents:RecordedEvent[];
  focus:DesiredArea;
}

export const eventNames:Record<PastKind,string>={
  study:"升学或转学",work:"工作或职业变化",move:"搬家或迁移",
  relationship:"重要关系变化",family:"家庭责任变化",
  project:"完成重要作品或项目",recognition:"获得认可",setback:"重大挫折",
};
export const areaNames:Record<DesiredArea,string>={
  career:"事业和工作",relationship:"关系与家庭",learning:"学习与成长",
  home:"居住与生活方式",undecided:"还没有决定",
};
const referenceAreas:Record<DesiredArea,LifeArea>={
  career:"career",relationship:"relationship",learning:"other",home:"other",undecided:"other",
};
export const evidenceDomainNames:Record<LifeArea,string>={
  career:"事业类记录",relationship:"关系类记录",recognition:"成就类记录",other:"其他记录",
};

export function validatedBirth(date:string,cutoffDate:string):{date:Date;age:number} {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!/^\d{4}-\d{2}-\d{2}$/.test(cutoffDate)) {
    throw new Error("请填写有效的出生年月日");
  }
  // Use UTC only for civil day parsing; NOT a timezone correction of a birth instant.
  const [y,m,d]=date.split("-").map(Number);
  const [cy,cm,cd]=cutoffDate.split("-").map(Number);
  const from=new Date(Date.UTC(y,m-1,d));
  const to=new Date(Date.UTC(cy,cm-1,cd));
  if(y<1850||y>2100||from.toISOString().slice(0,10)!==date||
     to.toISOString().slice(0,10)!==cutoffDate||from>to) {
    throw new Error("出生日期不正确，或在报告日期之后");
  }
  const age=cy-y-(cm<m||(cm===m&&cd<d)?1:0);
  return {date:from,age};
}

function eventDomain(kind:PastKind):LifeArea{
  if(kind==="work")return "career";
  if(kind==="relationship"||kind==="family")return "relationship";
  if(kind==="recognition")return "recognition";
  return "other";
}

export function makeReading(input:ReadingInput,cutoffDate:string){
  const {age}=validatedBirth(input.birthDate,cutoffDate);
  if(input.knownBirthTime&&!/^([01]\d|2[0-3]):[0-5]\d$/.test(input.birthTime)){
    throw new Error("请填写有效的出生时间，或者选择「不清楚」");
  }
  if(input.pastEvents.length>30)throw new Error("一次最多记录 30 件重要经历");
  const seen=new Set<string>();
  const facts=input.pastEvents.map(e=>{
    if(!Number.isInteger(e.age)||e.age<0||e.age>age||!(e.kind in eventNames)||
       !e.id||seen.has(e.id)||e.note.length>240)throw new Error("请检查经历的年龄、类型和描述");
    seen.add(e.id);
    return {...e,note:e.note.trim(),domain:eventDomain(e.kind)};
  }).sort((a,b)=>a.age-b.age);
  const totals:{[key in LifeArea]:number}={career:0,relationship:0,recognition:0,other:0};
  for(const e of facts)totals[e.domain]++;
  const nextStage=age<18?"18-27":age>=88?null:(research.age_bands as string[]).find(b=>{
    const [lo,hi]=b.split("-").map(Number);
    return age>=lo&&age<=hi;
  }) ?? null;
  const ref=nextStage?research.age_rates[nextStage as keyof typeof research.age_rates]:null;
  const reference=ref ? {
    label:nextStage,
    model:"R6 | documented-biography age-only research baseline",
    // Expected number of DOCUMENTED canonical source records, not real-life event incidence.
    eventsPer1000ResearchPersonYears:{
      career:Math.round(ref.career*1000*10)/10,
      relationship:Math.round(ref.relationship*1000*10)/10,
      recognition:Math.round(ref.recognition*1000*10)/10,
      other:Math.round(ref.other*1000*10)/10,
    },
    eligibleTrainPersonYears:Object.values(
      research.history_group_support[nextStage as keyof typeof research.history_group_support]
    ).reduce((a,b)=>a+b,0),
    warning:"这些是历史名人传记中被收录的事件密度，不是你实际遇到事件的概率。",
  }:null;
  const statements:string[]=[];
  statements.push("截至报告生成时，你填写了 "+facts.length+" 件人生经历。它们是你提供的事实，不是系统算中的过去。");
  if(facts.length){
    statements.push("你提供的经历中，较早的一件发生在约 "+facts[0].age+" 岁，最近的一件在约 "+facts[facts.length-1].age+" 岁。");
  } else {
    statements.push("你还没有填写过去经历。系统不会替你编造任何成长故事。");
  }
  if(age<18)statements.push("当前年龄不在历史模型已研究的成年阶段，暂不显示数据参考。");
  if(age>=88)statements.push("当前年龄超过历史模型的训练年龄范围，暂不外推数据。");
  return {
    protocol:"minggui-public-evidence-first-v1" as const,
    status:"research-preview-not-validated-personal-prediction" as const,
    asOf:cutoffDate,
    age,
    facts,
    counts:totals,
    focus:input.focus,
    focusName:areaNames[input.focus],
    narrative:statements,
    reference,
    natalEligibility:input.knownBirthTime?
      "unverified-local-civil-time-symbolic-preview-only":
      "hour-unknown-no-hour-or-day-sensitive-reading",
    prospectiveLikelihood:null,
    certainty:"尚无经过独立外部验证的个人命运概率",
  };
}

export type PublicReading = ReturnType<typeof makeReading>;
