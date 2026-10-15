/** Pure, explainable symbolic relation graph for UI and research demonstrations.
 * Rule activation is NOT a probabilistic or causal forecast.
 */
const stems = "甲乙丙丁戊己庚辛壬癸";
const branches = "子丑寅卯辰巳午未申酉戌亥";
const stemElements = "木木火火土土金金水水";
const elements = "木火土金水";
const stemPairs = ["甲己","乙庚","丙辛","丁壬","戊癸"];
const branchPairs = ["子丑","寅亥","卯戌","辰酉","巳申","午未"];
const clashPairs = ["子午","丑未","寅申","卯酉","辰戌","巳亥"];

export type RelationType="stem_combine"|"branch_combine"|"branch_clash"|"same_pillar";
export interface SymbolicRelation {
  source:string; target:string; kind:RelationType;
  signs:string; explanation:string;
}
export const relationText:Record<RelationType,string>={
  stem_combine:"天干五合",
  branch_combine:"地支六合",
  branch_clash:"地支六冲",
  same_pillar:"岁运同柱",
};

function pairIncludes(pairs:string[],a:string,b:string) {
  return pairs.some(p=>p.includes(a)&&p.includes(b)&&a!==b);
}

export function stemTenGod(dayStem:string,otherStem:string):string {
  const d=stems.indexOf(dayStem),o=stems.indexOf(otherStem);
  if(d<0||o<0)throw new Error("Invalid heavenly stem");
  const start=elements.indexOf(stemElements[d]),end=elements.indexOf(stemElements[o]);
  const same=(d%2)===(o%2);
  if(start===end)return same?"比肩":"劫财";
  if((start+1)%5===end)return same?"食神":"伤官";
  if((start+2)%5===end)return same?"偏财":"正财";
  if((end+2)%5===start)return same?"七杀":"正官";
  return same?"偏印":"正印";
}

export function relationBetween(source:string,a:string,target:string,b:string):SymbolicRelation[] {
  if(a.length!==2||b.length!==2||
     !stems.includes(a[0])||!stems.includes(b[0])||
     !branches.includes(a[1])||!branches.includes(b[1]))throw new Error("invalid pillar");
  const out:SymbolicRelation[]=[];
  const add=(kind:RelationType,signs:string)=>{
    out.push({source,target,kind,signs,explanation:relationText[kind]});
  };
  if(pairIncludes(stemPairs,a[0],b[0]))add("stem_combine",a[0]+b[0]);
  if(pairIncludes(branchPairs,a[1],b[1]))add("branch_combine",a[1]+b[1]);
  if(pairIncludes(clashPairs,a[1],b[1]))add("branch_clash",a[1]+b[1]);
  if(source==="大运"&&target==="流年"&&a===b)add("same_pillar",a);
  return out;
}

export function explainYear(
  natal:{year:string;month:string;day:string;hour:string},
  luckPillar:string|null,
  annualPillar:string
):SymbolicRelation[] {
  const natalEntries: [string,string][]=[
    ["年柱",natal.year],["月柱",natal.month],["日柱",natal.day],["时柱",natal.hour],
  ];
  const rel:SymbolicRelation[]=[];
  for(const [label,pillar] of natalEntries){
    rel.push(...relationBetween("流年",annualPillar,label,pillar));
    if(luckPillar)rel.push(...relationBetween("大运",luckPillar,label,pillar));
  }
  if(luckPillar)rel.push(...relationBetween("大运",luckPillar,"流年",annualPillar));
  return rel;
}
