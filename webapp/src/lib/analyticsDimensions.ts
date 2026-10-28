import type { LeadRecord } from "@/components/LeadPanel";
import type { PlatformKey, RangeKey } from "@/lib/analyticsDemo";

export type DimensionRange = RangeKey | "custom";
export interface Period { start: Date; end: Date }
export interface DimensionContent {
  id: string;
  source_id?: string | null;
  platform: PlatformKey;
  kind: "article" | "video";
  published_at: string | null;
  captured_at?: string;
  verified: boolean;
}

export function localDay(date: Date) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}

export function periodFor(range: DimensionRange, start?: string, end?: string, now = new Date()): Period {
  const todayText = localDay(now);
  const today = new Date(`${todayText}T00:00:00+08:00`);
  if (range === "custom") {
    const customStart = new Date(`${start || localDay(new Date(today.getTime() - 6 * 86400000))}T00:00:00+08:00`);
    const customEnd = new Date(`${end || todayText}T00:00:00+08:00`);
    return { start: customStart, end: new Date(customEnd.getTime() + 86400000) };
  }
  if (range === "today") return { start: today, end: now };
  if (range === "yesterday") return { start: new Date(today.getTime() - 86400000), end: today };
  const days = range === "7d" ? 7 : 30;
  return { start: new Date(now.getTime() - days * 86400000), end: now };
}

export function inPeriod(value: string | null | undefined, period: Period) {
  if (!value) return false;
  const time = new Date(value).getTime();
  return Number.isFinite(time) && time >= period.start.getTime() && time < period.end.getTime();
}

export function aggregateCustom(contents: DimensionContent[], leads: LeadRecord[], period: Period, platform?: PlatformKey) {
  const publications = contents.filter(item => item.verified && (!platform || item.platform === platform) && inPeriod(item.published_at, period));
  const originalIds = new Set(publications.map(item => item.source_id || item.id));
  const articles = new Set(publications.filter(item => item.kind === "article").map(item => item.source_id || item.id));
  const videos = new Set(publications.filter(item => item.kind === "video").map(item => item.source_id || item.id));
  const scopedLeads = leads.filter(lead => !platform || lead.platform === platform);
  const periodLeads = scopedLeads.filter(lead => inPeriod(lead.occurred_at, period));
  const periodDeals = scopedLeads.filter(lead => lead.stage === "deal" && inPeriod(lead.deal_at, period));
  const qualified = new Set(["qualified", "high_intent", "meeting", "deal"]);
  const highIntent = new Set(["high_intent", "meeting", "deal"]);
  const revenue = periodDeals.filter(lead => lead.revenue !== null).reduce((sum, lead) => sum + (lead.revenue || 0), 0);
  return { originals: originalIds.size, publications: publications.length, articles: articles.size, videos: videos.size,
    reach: null, likes: null, comments: null, shares: null, favorites: null,
    inquiries: periodLeads.length, qualifiedLeads: periodLeads.filter(lead => qualified.has(lead.stage)).length,
    highIntentLeads: periodLeads.filter(lead => highIntent.has(lead.stage)).length,
    meetings: periodLeads.filter(lead => ["meeting", "deal"].includes(lead.stage)).length,
    deals: periodDeals.length, revenue: periodDeals.some(lead => lead.revenue !== null) ? revenue : null };
}

export function publicationTrend(contents: DimensionContent[], period: Period, platform?: PlatformKey) {
  const days = Math.max(1, Math.min(62, Math.ceil((period.end.getTime() - period.start.getTime()) / 86400000)));
  const labels: string[] = [];
  const values: number[] = [];
  for (let index = days - 1; index >= 0; index--) {
    const day = new Date(period.end.getTime() - index * 86400000 - 1);
    const dayText = localDay(day);
    const start = new Date(`${dayText}T00:00:00+08:00`);
    const end = new Date(start.getTime() + 86400000);
    labels.push(dayText.slice(5));
    values.push(contents.filter(item => item.verified && (!platform || item.platform === platform) && inPeriod(item.published_at, { start, end })).length);
  }
  return { labels, values };
}
