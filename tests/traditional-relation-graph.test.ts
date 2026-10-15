import { describe, it, expect } from "vitest";
import { explainYear, relationBetween, stemTenGod } from "../lib/traditional-relation-graph";

describe("traceable traditional symbolic graph",()=>{
  it("computes ten gods for all ten Jia-day stems",()=>{
    expect(["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
      .map(s=>stemTenGod("甲",s))).toEqual(
       ["比肩","劫财","食神","伤官","偏财","正财","七杀","正官","偏印","正印"]
    );
  });
  it("reports genuine pair relation without asserting outcomes",()=>{
    const pair=relationBetween("流年","庚子","日柱","甲午");
    expect(pair.some(x=>x.kind==="branch_clash"&&x.signs==="子午")).toBe(true);
    expect(pair.every(x=>!x.explanation.includes("结婚")&&!x.explanation.includes("灾"))).toBe(true);
  });
  it("distinguishes same luck and annual pillars from historical outcome",()=>{
    const pair=relationBetween("大运","己未","流年","己未");
    expect(pair.some(x=>x.kind==="same_pillar")).toBe(true);
    expect(pair.every(x=>x.source&&x.target)).toBe(true);
  });
  it("only describes documented symbolic relationships in graph",()=>{
    const graph=explainYear(
      {year:"甲子",month:"丙寅",day:"甲午",hour:"丁卯"},"己未","庚子");
    expect(graph.some(x=>x.source==="流年"&&x.target==="日柱"&&x.kind==="branch_clash")).toBe(true);
    expect(graph.some(x=>x.source==="大运"&&x.target==="日柱"&&x.kind==="branch_combine")).toBe(true);
    expect(graph.every(x=>Object.keys(x).sort().join(",")==="explanation,kind,signs,source,target")).toBe(true);
  });
  it("rejects invalid pillars and invalid day masters",()=>{
    expect(()=>stemTenGod("X","甲")).toThrow();
    expect(()=>relationBetween("A","invalid","B","甲子")).toThrow();
  });
});
