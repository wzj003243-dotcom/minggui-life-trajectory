import { describe, expect, it } from "vitest";
import { calculateBazi } from "./bazi";

describe("BaZi calendar adapter", () => {
  it("matches upstream documented 2005-12-23 08:37 example", () => {
    const p = calculateBazi({ year: 2005, month: 12, day: 23, hour: 8, minute: 37, knownTime: true });
    expect(p.pillars).toEqual({ year: "乙酉", month: "戊子", day: "辛巳", time: "壬辰" });
  });

  it("does not expose a fabricated hour pillar when time is unknown", () => {
    const p = calculateBazi({ year: 2004, month: 2, day: 3, knownTime: false });
    expect(p.pillars.time).toBeNull();
    expect(p.knownTime).toBe(false);
  });
});
