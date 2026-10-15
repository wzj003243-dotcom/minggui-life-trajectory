/**
 * R8 / Age-only historical DOCUMENTATION trajectory simulator.
 *
 * This is a reproducible cohort research visualization, NOT a life forecast.
 * Every annual Poisson intensity comes directly from frozen R6 TRAIN-only
 * age_rates (expected canonical biography entries per person-year).
 * Unlike the history lookup, the simulator does NOT map a living person's
 * self-reported milestones to archival canonical event counts.
 *
 * There is NO mortality, publication, population sampling, or long-rollout
 * calibration model. Never display these rates as a person's life probability.
 */
import model from "../research/benchmarks/results/v12_r6_dev_lifetime_lookup.json";

export const historicalDomains = ["career", "recognition", "relationship", "other"] as const;
export type HistoricalDomain = typeof historicalDomains[number];
export type HistoricalSampleEvent = {age: number; domain: HistoricalDomain};
export interface HistoricalStage {
  fromAge: number; toAgeExclusive: number;
  expectedDocumentedRecords: number;
  domainExpectedDocumentedRecords: Record<HistoricalDomain,number>;
}
export interface IllustrativePath {
  label: "较少记录"|"中间样本"|"较多记录";
  count: number;
  events: HistoricalSampleEvent[];
}
export interface HistoricalTrajectory {
  schema: "minggui-r8-historical-trajectory-demo-v1";
  labelScope: "retrospectively_documented_canonical_events_only";
  sourceSnapshot: string;
  modelProtocol: string;
  trainingPersonYears: number;
  fromAge: number;
  toAgeExclusive: number;
  requestedHorizon: 5|10|20;
  actualYears: number;
  meanExpectedRecords: number;
  quantiles: {p10:number;p50:number;p90:number};
  stages:HistoricalStage[];
  illustrativePaths:IllustrativePath[];
  sampledPaths:number;
  sourceMethod: "R6 age-only Poisson model, frozen training rates";
  personallyCalibrated:false;
  longHorizonCalibrated:false;
}

type ModelJson=typeof model;
const ageRanges=(model.age_bands as string[]).map(b=>{
  const [from,to]=b.split("-").map(Number);
  return {from,to,label:b as keyof ModelJson["age_rates"]};
});

function ageRates(age:number): Record<HistoricalDomain,number>{
  const band=ageRanges.find(r=>age>=r.from&&age<=r.to);
  if(!band)throw new Error("R6 model age support is 18–87 only");
  const raw=model.age_rates[band.label];
  const rates={} as Record<HistoricalDomain,number>;
  for(const d of historicalDomains){
    const v=raw[d];
    if(!Number.isFinite(v)||v<0||v>10)throw new Error("invalid frozen R6 documented-event rate");
    rates[d]=v;
  }
  return rates;
}

// Completely deterministic small PRNG so research demo can be regression-tested.
function seededRandom(initial:number){
  let state=initial>>>0;
  return ()=>{
    state=(state+0x6D2B79F5)>>>0;
    let x=state;
    x=Math.imul(x^(x>>>15),x|1);
    x^=x+Math.imul(x^(x>>>7),x|61);
    return ((x^(x>>>14))>>>0)/4294967296;
  };
}
function poisson(lambda:number,draw:()=>number){
  if(lambda===0)return 0;
  let k=0,product=1;
  const p0=Math.exp(-lambda);
  do {k++;product*=Math.max(draw(),1e-12)} while(product>p0);
  return k-1;
}
function quantile(ordered:number[],q:number){
  return ordered[Math.floor((ordered.length-1)*q)];
}

export function simulateHistoricalDocumentedPaths({
  fromAge,horizon=20,sampleCount=1200,seed=20261015,
}:{
  fromAge:number;horizon?:5|10|20;sampleCount?:number;seed?:number;
}):HistoricalTrajectory {
  if(!Number.isInteger(fromAge)||fromAge<18||fromAge>87)
    throw new Error("Historical R6 simulation only supports ages 18–87");
  if(![5,10,20].includes(horizon))throw new Error("invalid horizon");
  if(!Number.isInteger(sampleCount)||sampleCount<100||sampleCount>5000)
    throw new Error("simulation sampleCount must be 100–5000");
  if(!Number.isSafeInteger(seed))throw new Error("invalid deterministic seed");
  const end=Math.min(88,fromAge+horizon);
  const stages:HistoricalStage[]=[];
  let totalExpected=0;
  for(let lo=fromAge;lo<end;lo+=5){
    const hi=Math.min(lo+5,end);
    const expected={career:0,recognition:0,relationship:0,other:0};
    for(let age=lo;age<hi;age++){
      const annual=ageRates(age);
      for(const d of historicalDomains)expected[d]+=annual[d];
    }
    const count=historicalDomains.reduce((n,d)=>n+expected[d],0);
    stages.push({fromAge:lo,toAgeExclusive:hi,expectedDocumentedRecords:count,
                 domainExpectedDocumentedRecords:expected});
    totalExpected+=count;
  }
  const rand=seededRandom(seed);
  const all:HistoricalSampleEvent[][]=[];
  for(let p=0;p<sampleCount;p++){
    const path:HistoricalSampleEvent[]=[];
    for(let age=fromAge;age<end;age++){
      const rates=ageRates(age);
      for(const domain of historicalDomains){
        const count=poisson(rates[domain],rand);
        for(let j=0;j<count;j++)path.push({age,domain});
      }
    }
    all.push(path);
  }
  // Sorted sample index is a demonstration of stochastic trajectories,
  // not a percentile confidence interval of one's actual future.
  const sorted=all.slice().sort((a,b)=>a.length-b.length);
  const take=(q:number,label:IllustrativePath["label"]):IllustrativePath=>{
    const events=sorted[Math.floor((sorted.length-1)*q)];
    return {label,count:events.length,events:events.slice()};
  };
  const countSort=sorted.map(x=>x.length);
  return {
    schema:"minggui-r8-historical-trajectory-demo-v1",
    labelScope:"retrospectively_documented_canonical_events_only",
    sourceSnapshot:model.source_snapshot,
    modelProtocol:model.protocol,
    trainingPersonYears:model.train_exposure_person_years,
    fromAge,toAgeExclusive:end,requestedHorizon:horizon,
    actualYears:end-fromAge,
    meanExpectedRecords:totalExpected,
    quantiles:{p10:quantile(countSort,.10),p50:quantile(countSort,.50),p90:quantile(countSort,.90)},
    stages,illustrativePaths:[take(.1,"较少记录"),take(.5,"中间样本"),take(.9,"较多记录")],
    sampledPaths:sampleCount,
    sourceMethod:"R6 age-only Poisson model, frozen training rates",
    personallyCalibrated:false,longHorizonCalibrated:false,
  };
}
