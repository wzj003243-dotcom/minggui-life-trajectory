import { describe, expect, it } from "vitest";
import { annualPillarAfterLichun, auditedYunTimeline } from "../lib/traditional-luck-cycles";

const knownBirth = {
  year: 1995, month: 6, day: 15, hour: 10, minute: 35,
  localCivilTimeVerified: true,
  timezoneProvenance: "Asia/Shanghai: verified local civil time by source",
  birthTimeSourceGrade: "AA",
  conventionalYunGender: "male",
  yunSect: 1,
  eightCharSect: 2,
} as const;

describe("traditional luck timeline - calendar calculation only", () => {
  it("anchors representative year stems after LiChun", () => {
    expect(annualPillarAfterLichun(1984)).toBe("甲子");
    expect(annualPillarAfterLichun(2024)).toBe("甲辰");
    expect(annualPillarAfterLichun(2026)).toBe("丙午");
    expect(() => annualPillarAfterLichun(1356)).toThrow();
  });

  it("generates real calculated DaYun periods, not guessed age-mod-10 cycles", () => {
    const result = auditedYunTimeline(knownBirth);
    expect(result.library).toBe("lunar-typescript@1.8.6");
    expect(result.natal.day).toMatch(/^[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]$/);
    expect(result.natal.hour).toMatch(/^[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]$/);
    expect(result.startYun.civilDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(result.periods.length).toBeGreaterThan(4);
    expect(result.periods.filter((p) => p.pillar != null).length).toBeGreaterThan(3);
    expect(result.periods.every((p) => p.endYear >= p.startYear)).toBe(true);
    expect(result.predictiveProbability).toBeNull();
  });

  it("requires explicit traditional direction and verified local civil time", () => {
    expect(() => auditedYunTimeline({
      ...knownBirth, timezoneProvenance: "",
    })).toThrow();
    expect(() => auditedYunTimeline({
      ...knownBirth, conventionalYunGender: "unknown" as "male",
    })).toThrow();
    expect(() => auditedYunTimeline({
      ...knownBirth, localCivilTimeVerified: false as true,
    })).toThrow();
  });

  it("does not silently infer or normalize birth hours", () => {
    expect(() => auditedYunTimeline({...knownBirth, hour: 24})).toThrow();
    expect(() => auditedYunTimeline({...knownBirth, minute: 60})).toThrow();
  });

  it("keeps sect and direction traceable", () => {
    const a = auditedYunTimeline(knownBirth);
    const b = auditedYunTimeline({...knownBirth, conventionalYunGender: "female" as const});
    expect(a.sect.yunSect).toBe(1);
    expect(a.traditionalDirectionConvention).toBe("male");
    expect(b.traditionalDirectionConvention).toBe("female");
    expect(a.periods.map((x) => x.pillar)).not.toEqual(b.periods.map((x) => x.pillar));
  });
});
