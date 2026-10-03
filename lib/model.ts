import type { BaziProfile } from "./bazi";

export type TraitKey = "exploration" | "execution" | "structure" | "stability" | "expression";
export type TraitScores = Record<TraitKey, number>;

const clamp = (n: number) => Math.max(0.08, Math.min(0.92, n));
const n = (x: number, total: number) => x / Math.max(total, 1);

export function traditionalPrior(profile: BaziProfile): TraitScores {
  const e = profile.elementCounts;
  const total = Object.values(e).reduce((a, b) => a + b, 0);
  return {
    exploration: clamp(.35 + .50 * (n(e.水, total) + n(e.木, total)) / 2),
    execution: clamp(.28 + .72 * n(e.火, total)),
    structure: clamp(.30 + .70 * n(e.金, total)),
    stability: clamp(.30 + .70 * n(e.土, total)),
    expression: clamp(.30 + .42 * n(e.火, total) + .28 * n(e.木, total)),
  };
}

export type CalibrationAnswers = {
  underPressure: "research" | "act" | "avoid" | "ask";
  projectMode: "system" | "prototype" | "switch" | "steady";
  biggestFear: "money" | "direction" | "status" | "relationship" | "wasted";
  consistency: number;
  mobility: number;
};

function logit(p: number) { return Math.log(p / (1 - p)); }
function sigmoid(x: number) { return 1 / (1 + Math.exp(-x)); }

export function calibrate(prior: TraitScores, a: CalibrationAnswers): TraitScores {
  const delta: TraitScores = { exploration: 0, execution: 0, structure: 0, stability: 0, expression: 0 };
  if (a.underPressure === "research") { delta.exploration += .65; delta.execution -= .25; }
  if (a.underPressure === "act") { delta.execution += .70; delta.exploration -= .10; }
  if (a.underPressure === "avoid") { delta.execution -= .65; delta.stability -= .10; }
  if (a.underPressure === "ask") { delta.expression += .30; delta.stability += .15; }
  if (a.projectMode === "system") { delta.exploration += .40; delta.structure += .25; delta.execution -= .15; }
  if (a.projectMode === "prototype") { delta.execution += .50; delta.expression += .15; }
  if (a.projectMode === "switch") { delta.exploration += .30; delta.stability -= .35; }
  if (a.projectMode === "steady") { delta.stability += .45; delta.structure += .20; }
  delta.execution += (a.consistency - 3) * .18;
  delta.exploration += (a.mobility - 3) * .12;
  delta.stability -= (a.mobility - 3) * .10;
  if (a.biggestFear === "direction") delta.exploration += .22;
  if (a.biggestFear === "money") delta.stability += .20;
  if (a.biggestFear === "status") delta.expression += .18;
  if (a.biggestFear === "relationship") delta.stability += .12;
  if (a.biggestFear === "wasted") { delta.execution += .10; delta.exploration += .10; }

  return Object.fromEntries(
    Object.entries(prior).map(([k, p]) => [k, clamp(sigmoid(logit(p) + delta[k as TraitKey]))])
  ) as TraitScores;
}

export const traitLabels: Record<TraitKey, { zh: string; desc: string }> = {
  exploration: { zh: "探索 / 信息", desc: "跨领域、学习、迁移、处理复杂信息的倾向" },
  execution: { zh: "行动 / 热量", desc: "启动、推进、表达与把想法变成交付的能力" },
  structure: { zh: "规则 / 边界", desc: "收敛、判断、秩序、拒绝与做决定的能力" },
  stability: { zh: "稳定 / 承压", desc: "长期积累、现实责任、安全感与抗波动能力" },
  expression: { zh: "表达 / 外显", desc: "创作、影响他人、曝光、社交输出的倾向" },
};

export type Branch = { name: string; probability: number; summary: string; hinge: string };

export function heuristicBranches(s: TraitScores): Branch[] {
  const raw = [
    { name: "漂移重构型", score: 0.30 + s.exploration * .75 + (1-s.stability)*.20, summary: "先跨域、迁移与试错，后把不同能力组合成独特位置。", hinge: "必须把探索沉淀成一个可被外界验证的代表作。" },
    { name: "系统建造型", score: 0.25 + s.structure*.50 + s.execution*.45 + s.exploration*.20, summary: "从解决复杂问题开始，逐渐形成自己的系统、产品或组织。", hinge: "从亲自解决问题转向让系统重复解决问题。" },
    { name: "稳定专家型", score: 0.22 + s.stability*.70 + s.structure*.35, summary: "沿专业与机构路径积累声望、技能和长期资源。", hinge: "是否愿意用自由度交换长期确定性。" },
    { name: "创作影响型", score: 0.18 + s.expression*.75 + s.exploration*.30, summary: "通过内容、审美、叙事或公开表达形成个人影响力。", hinge: "灵感必须转成持续发布机制。" },
  ];
  const total = raw.reduce((a,b)=>a+b.score,0);
  return raw.map(x=>({ name:x.name, probability:x.score/total, summary:x.summary, hinge:x.hinge })).sort((a,b)=>b.probability-a.probability);
}

export function stageNarrative(age: number, s: TraitScores) {
  if (age < 20) return "环境塑形与能力底层形成期：家庭、学校与迁移经历对后续选择惯性影响最大。";
  if (age < 30) return s.exploration > s.stability ? "探索与迁移期：机会来自跨领域和新环境，风险是方向过多、成果沉淀不足。" : "能力定型期：适合把专业技能做深，风险是过早把安全感当成唯一目标。";
  if (age < 40) return s.execution > .55 ? "结构成型期：个人能力开始向产品、团队、职位或稳定事业结构转换。" : "重构窗口期：如果前一阶段长期停留在规划，这十年会迫使你重新选择主线。";
  if (age < 50) return "影响力扩张期：资源整合、身份跃迁与管理能力比单点技能更重要。";
  if (age < 60) return "资产与传承期：把经验转成资本、方法论、品牌或可复制体系。";
  return "收束与传承期：人生评价逐渐从外部成绩转向作品、关系、健康与留下什么。";
}
