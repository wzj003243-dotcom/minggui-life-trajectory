import {describe,it,expect} from "vitest";
import {makeReading,validatedBirth,type ReadingInput} from "../lib/public-reading";

const base:ReadingInput={
  birthDate:"1997-07-20",birthPlace:"测试城市",knownBirthTime:false,birthTime:"",
  pastEvents:[],focus:"career",
};

describe("Public reading: a scientific input/output firewall",()=>{
  it("rejects invalid and future civil birthdays",()=>{
    expect(validatedBirth("2000-02-29","2026-10-15").age).toBe(26);
    expect(()=>validatedBirth("2001-02-29","2026-10-15")).toThrow();
    expect(()=>validatedBirth("2027-01-01","2026-10-15")).toThrow();
    expect(()=>validatedBirth("bad date","2026-10-15")).toThrow();
    expect(validatedBirth("2004-10-16","2026-10-15").age).toBe(21);
  });
  it("does not hallucinate a past or a future when input empty",()=>{
    const result=makeReading(base,"2026-10-15");
    expect(result.facts).toHaveLength(0);
    expect(result.prospectiveLikelihood).toBeNull();
    expect(result.status).toMatch(/not-validated/);
    expect(result.narrative.some(x=>x.includes("没有填写过去经历"))).toBe(true);
  });
  it("preserves only self-reported chronology and does not count future as past",()=>{
    const input:ReadingInput={...base,pastEvents:[
      {id:"a",age:24,kind:"work",note:"换工作"},
      {id:"b",age:18,kind:"study",note:"入学"}
    ]};
    const result=makeReading(input,"2026-10-15");
    expect(result.facts.map(x=>x.age)).toEqual([18,24]);
    expect(result.counts.career).toBe(1);
    expect(result.counts.other).toBe(1);
    const withFuture={...input,pastEvents:[...input.pastEvents,{id:"c",age:30,kind:"family" as const,note:"未来"}]};
    expect(()=>makeReading(withFuture,"2026-10-15")).toThrow();
  });
  it("never silently sets a missing birth hour to noon",()=>{
    const r=makeReading(base,"2026-10-15");
    expect(r.natalEligibility).toMatch(/hour-unknown/);
    const withKnownHour:ReadingInput={...base,knownBirthTime:true,birthTime:"10:35"};
    expect(makeReading(withKnownHour,"2026-10-15").natalEligibility).toMatch(/unverified/);
    expect(()=>makeReading({...withKnownHour,birthTime:""},"2026-10-15")).toThrow();
  });
  it("treats historical counts as documentary density, never a user probability",()=>{
    const r=makeReading(base,"2026-10-15");
    expect(r.reference).not.toBeNull();
    expect(r.reference?.label).toBe("28-37");
    expect(r.reference?.eligibleTrainPersonYears).toBeGreaterThan(100);
    expect(r.reference?.warning).toMatch(/不是你实际遇到事件的概率/);
    expect(r.prospectiveLikelihood).toBeNull();
    const withEvents={...base,pastEvents:[
      {id:"m",age:20,kind:"move" as const,note:""}
    ]};
    // Changing self-reports NEVER changes the research cohort likelihood.
    expect(makeReading(withEvents,"2026-10-15").reference).toEqual(r.reference);
  });
  it("refuses to extrapolate beyond trained age support",()=>{
    const young=makeReading({...base,birthDate:"2017-06-01"},"2026-10-15");
    expect(young.reference).toBeNull();
    const older=makeReading({...base,birthDate:"1930-01-01"},"2026-10-15");
    expect(older.reference).toBeNull();
  });
  it("refuses 30+ events and duplicated identifiers",()=>{
    const e={id:"repeated",age:20,kind:"study" as const,note:""};
    expect(()=>makeReading({...base,pastEvents:[e,e]},"2026-10-15")).toThrow();
    expect(()=>makeReading({...base,pastEvents:Array.from({length:31},(_,i)=>({...e,id:String(i)}))},"2026-10-15")).toThrow();
  });
});
