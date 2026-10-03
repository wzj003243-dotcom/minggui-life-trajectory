import { Solar } from "lunar-typescript";

export type Element = "木" | "火" | "土" | "金" | "水";

const stemElement: Record<string, Element> = {
  甲: "木", 乙: "木", 丙: "火", 丁: "火", 戊: "土", 己: "土", 庚: "金", 辛: "金", 壬: "水", 癸: "水",
};
const branchElement: Record<string, Element> = {
  寅: "木", 卯: "木", 巳: "火", 午: "火", 辰: "土", 戌: "土", 丑: "土", 未: "土", 申: "金", 酉: "金", 亥: "水", 子: "水",
};

export interface BaziProfile {
  pillars: { year: string; month: string; day: string; time: string | null };
  dayMaster: string;
  dayMasterElement: Element;
  elementCounts: Record<Element, number>;
  knownTime: boolean;
}

function addElement(counts: Record<Element, number>, char?: string) {
  if (!char) return;
  const el = stemElement[char] ?? branchElement[char];
  if (el) counts[el] += 1;
}

export function calculateBazi(input: {
  year: number; month: number; day: number; hour?: number; minute?: number; knownTime: boolean;
}): BaziProfile {
  const hour = input.knownTime ? (input.hour ?? 12) : 12;
  const minute = input.knownTime ? (input.minute ?? 0) : 0;
  const lunar = Solar.fromYmdHms(input.year, input.month, input.day, hour, minute, 0).getLunar();
  const ec = lunar.getEightChar();
  const year = ec.getYear();
  const month = ec.getMonth();
  const day = ec.getDay();
  const time = input.knownTime ? ec.getTime() : null;
  const counts: Record<Element, number> = { 木: 0, 火: 0, 土: 0, 金: 0, 水: 0 };
  for (const p of [year, month, day, ...(time ? [time] : [])]) {
    addElement(counts, p[0]);
    addElement(counts, p[1]);
  }
  const dayMaster = ec.getDayGan();
  return {
    pillars: { year, month, day, time },
    dayMaster,
    dayMasterElement: stemElement[dayMaster],
    elementCounts: counts,
    knownTime: input.knownTime,
  };
}
