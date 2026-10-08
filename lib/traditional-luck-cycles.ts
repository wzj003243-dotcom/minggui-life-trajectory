/* Traceable BaZi timing adapter using the already pinned lunar-typescript 1.8.6.
 * Tradition is an auditable symbol/period description, NEVER a risk estimate.
 * Birth date/time are trusted local CIVIL time already prepared upstream. This
 * library does not know historical birthplace timezone; caller must supply and
 * attest to the provenance. Do not infer a missing hour or direction.
 */
import { Solar } from "lunar-typescript";

export type ConventionalYunGender = "male" | "female";
export type SourceGrade = "AA" | "A" | "B" | "other";

export interface AuditedLocalBirth {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  /** Caller has resolved civil time, place, DST/timezone history already. */
  localCivilTimeVerified: true;
  /** Audit label only; Solar.fromYmdHms does not perform zone conversion. */
  timezoneProvenance: string;
  birthTimeSourceGrade: SourceGrade;
  /** Traditional convention for Yun direction: caller-supplied, NOT inferred. */
  conventionalYunGender: ConventionalYunGender;
  /** Different schools use different methods; fixed per run. */
  yunSect: 1 | 2;
  /** EightChar day boundary convention, must be fixed for a cohort. */
  eightCharSect: 1 | 2;
}

export function annualPillarAfterLichun(year: number): string {
  if (!Number.isInteger(year) || year < 1600 || year > 2200) {
    throw new Error("year outside adapter's allowed research range");
  }
  // March 1 is safely AFTER LiChun in the standard library's calendar,
  // but this MUST NOT be assigned to Jan/Feb events without event dates.
  return Solar.fromYmdHms(year, 3, 1, 12, 0, 0).getLunar().getEightChar().getYear();
}

export function auditedYunTimeline(birth: AuditedLocalBirth) {
  const {
    year, month, day, hour, minute, timezoneProvenance, conventionalYunGender,
    birthTimeSourceGrade, localCivilTimeVerified, yunSect, eightCharSect,
  } = birth;
  if (
    localCivilTimeVerified !== true || !timezoneProvenance.trim() ||
    !Number.isInteger(year) || year < 1600 || year > 2100 ||
    !Number.isInteger(month) || month < 1 || month > 12 ||
    !Number.isInteger(day) || day < 1 || day > 31 ||
    !Number.isInteger(hour) || hour < 0 || hour > 23 ||
    !Number.isInteger(minute) || minute < 0 || minute > 59 ||
    !["male", "female"].includes(conventionalYunGender) ||
    ![1, 2].includes(yunSect) || ![1, 2].includes(eightCharSect)
  ) {
    throw new Error("complete, verified civil birth / sect / direction input required");
  }

  const solar = Solar.fromYmdHms(year,month,day,hour,minute,0);
  if (
    solar.getYear() !== year || solar.getMonth() !== month || solar.getDay() !== day ||
    solar.getHour() !== hour || solar.getMinute() !== minute
  ) {
    throw new Error("invalid Gregorian birth date or library normalized birth instant");
  }
  const bazi = solar.getLunar().getEightChar();
  bazi.setSect(eightCharSect);
  const yun = bazi.getYun(conventionalYunGender === "male" ? 1 : 0, yunSect);
  const periods = yun.getDaYun().map((period) => ({
    startYear: period.getStartYear(),
    endYear: period.getEndYear(),
    startAgeLibrary: period.getStartAge(),
    endAgeLibrary: period.getEndAge(),
    pillar: period.getGanZhi() || null,
  }));
  const boundariesValid = periods.every((p) => p.endYear >= p.startYear
                                                && p.endAgeLibrary >= p.startAgeLibrary);
  if (!boundariesValid) throw new Error("invalid DaYun period returned by calendar library");
  return {
    schema: "minggui-audited-yun-timeline-v1" as const,
    library: "lunar-typescript@1.8.6" as const,
    birthplaceCivilTimezone: timezoneProvenance,
    sourceGrade: birthTimeSourceGrade,
    sect: { yunSect, eightCharSect },
    traditionalDirectionConvention: conventionalYunGender,
    natal: {
      year: bazi.getYear(),
      month: bazi.getMonth(),
      day: bazi.getDay(),
      hour: bazi.getTime(),
      dayMaster: bazi.getDayGan(),
    },
    startYun: {
      afterYears: yun.getStartYear(),
      afterMonths: yun.getStartMonth(),
      afterDays: yun.getStartDay(),
      civilDate: yun.getStartSolar().toYmd(),
    },
    periods,
    predictiveProbability: null as null,
    calendarBoundaryCaveat: "Year pillar after LiChun; Jan/Feb must be timed individually",
    limitation: "Historical civil-time conversion must be verified upstream; no event prediction is inferred",
  };
}
