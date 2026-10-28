import { describe, expect, it } from "vitest";
import { aggregateCustom, periodFor, publicationTrend } from "./analyticsDimensions";
import type { LeadRecord } from "@/components/LeadPanel";

const lead: LeadRecord = { id: "lead-1", platform: "douyin", author_alias: "测试", profile_text: "", message_text: "详情", need_text: "", source_content_id: null, source_url: null,
  occurred_at: "2026-10-27T02:00:00Z", stage: "deal", notes: "", revenue: 19900, deal_at: "2026-10-28T03:00:00Z", created_at: "", updated_at: "" };

describe("analytics dimensions", () => {
  it("keeps inquiry and deal in their actual periods", () => {
    const contents = [{ id: "pub-1", source_id: "source-1", platform: "douyin" as const, kind: "video" as const, published_at: "2026-10-28T01:00:00Z", verified: true }];
    const today = periodFor("custom", "2026-10-28", "2026-10-28", new Date("2026-10-28T12:00:00+08:00"));
    const yesterday = periodFor("custom", "2026-10-27", "2026-10-27", new Date("2026-10-28T12:00:00+08:00"));
    const todayMetrics = aggregateCustom(contents, [lead], today);
    const yesterdayMetrics = aggregateCustom(contents, [lead], yesterday);
    expect(todayMetrics.inquiries).toBe(0);
    expect(todayMetrics.deals).toBe(1);
    expect(todayMetrics.revenue).toBe(19900);
    expect(todayMetrics.publications).toBe(1);
    expect(yesterdayMetrics.inquiries).toBe(1);
    expect(yesterdayMetrics.deals).toBe(0);
    expect(publicationTrend(contents, today).values).toEqual([1]);
  });
});
