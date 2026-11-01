import {
  ArrowRight,
  Bot,
  Briefcase,
  ChartColumn,
  CircleCheck,
  Clock,
  Database,
  FileText,
  Heart,
  Lightbulb,
  ListChecks,
  MapPin,
  MessageSquare,
  Search,
  ShieldCheck,
  Sparkles,
  Store,
  Target,
  TrendingUp,
  TriangleAlert,
  Users,
  Wallet,
  Workflow,
  Zap,
  type LucideIcon,
} from "lucide-react";
import React from "react";
import {Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {Backdrop, SceneMedia} from "./effects";
import {hasStyleVariant, StyleScene} from "./style-scenes";
import type {TalkingHeadAppearance, TalkingHeadScene} from "./VideoComposition";

const fontFamily = "Arial, PingFang SC, Microsoft YaHei, sans-serif";
const typeNames: Record<string, string> = {
  hook: "核心问题", key_point: "关键观点", metric: "数据洞察", process: "实施路径",
  comparison: "方式对比", timeline: "进程回顾", architecture: "系统协同", map: "地点与路线",
  media: "真实素材", quote: "情感共鸣", cta: "行动建议",
};

const iconFor = (scene: TalkingHeadScene): LucideIcon => {
  const text = `${scene.narration || scene.description} ${(scene.keywords || []).join(" ")}`;
  const entries: [RegExp, LucideIcon][] = [
    [/数据|图表/, ChartColumn], [/客户|团队|用户/, Users], [/任务|清单/, ListChecks],
    [/时间|效率/, Clock], [/增长|提升|趋势/, TrendingUp], [/风险|问题|失败/, TriangleAlert],
    [/成本|钱|预算|元/, Wallet], [/AI|人工智能|机器人/i, Bot], [/流程|协同/, Workflow],
    [/目标/, Target], [/方案|方法|启发/, Lightbulb], [/留言|沟通|消息/, MessageSquare],
    [/店铺|电商/, Store], [/老板|企业|创始人/, Briefcase], [/安全/, ShieldCheck],
    [/完成|结果/, CircleCheck], [/搜索/, Search], [/文档|文章/, FileText],
    [/情绪|睡眠|身体|陪伴|更年期/, Heart], [/系统|平台|Agent|智能体/i, Database],
  ];
  return entries.find(([pattern]) => pattern.test(text))?.[1] || Sparkles;
};

const enter = (frame: number, fps: number, delay = 0) => spring({
  frame: Math.max(0, frame - delay), fps, config: {damping: 17, stiffness: 115},
});

const HighlightText: React.FC<{text: string; scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({text, scene, theme}) => {
  const words = [...new Set([...(scene.keywords || []), ...(scene.locations || [])])].filter(Boolean);
  const pattern = new RegExp(`(${[...words].map(word => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")}|\\d+(?:\\.\\d+)?\\s*(?:%|％|个|条|家|倍|万|元|分钟|小时|天|周|月|年|步)?)`, "g");
  const parts = pattern.source !== "()" && words.length + text.length > 0 ? text.split(pattern) : [text];
  return <>{parts.map((part, index) => {
    const emphasized = words.includes(part) || /^\d/.test(part);
    return <span key={index} style={emphasized ? {color: theme.accentColor, fontWeight: 800} : undefined}>{part}</span>;
  })}</>;
};

const SceneHeading: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance; children: React.ReactNode}> = ({scene, theme, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return <div style={{position: "relative", zIndex: 2, marginBottom: 34, opacity: enter(frame, fps), translate: `0 ${interpolate(enter(frame, fps), [0, 1], [34, 0])}px`}}>
    <div style={{display: "flex", alignItems: "center", gap: 12, color: theme.accentColor, fontSize: 24, letterSpacing: 3, fontWeight: 700}}>
      <span style={{width: 34, height: 3, background: theme.accentColor}} />
      {typeNames[scene.type || "key_point"]}
    </div>
    <div style={{color: theme.textColor, fontSize: 42, fontWeight: 700, lineHeight: 1.35, marginTop: 14, textWrap: "balance"}}>{children}</div>
  </div>;
};

const MetricVisual: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const metric = scene.data?.metric || {value: 1, unit: "", direction: "up" as const};
  const valueProgress = interpolate(frame, [fps * 0.25, fps * 2.6], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic)});
  const current = metric.value * valueProgress;
  const display = Number.isInteger(metric.value) ? Math.round(current) : current.toFixed(1);
  const ring = interpolate(frame, [fps * 0.4, fps * 2.8], [0, Math.min(1, metric.value / 100)], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const beat = Math.floor(frame / (fps * 2.8));
  const Icon = metric.direction === "down" ? TrendingUp : ChartColumn;
  return <div style={{display: "grid", gridTemplateColumns: "1.05fr .95fr", alignItems: "center", gap: 40, flex: 1}}>
    <div>
      <SceneHeading scene={scene} theme={theme}>{scene.headline || scene.name}</SceneHeading>
      <div style={{color: theme.accentColor, fontSize: 142, lineHeight: 1, fontWeight: 850, letterSpacing: -6, scale: 1 + Math.min(beat, 1) * 0.025, transformOrigin: "left center"}}>
        {display}<span style={{fontSize: 64, letterSpacing: 0, marginLeft: 8}}>{metric.unit}</span>
      </div>
      <div style={{color: theme.textColor, opacity: 0.76, fontSize: 30, lineHeight: 1.6, marginTop: 28}}>
        <HighlightText text={scene.narration || scene.description} scene={scene} theme={theme} />
      </div>
    </div>
    <div style={{position: "relative", width: 360, height: 360, margin: "0 auto", scale: enter(frame, fps, 8)}}>
      <svg viewBox="0 0 360 360" style={{position: "absolute", inset: 0, rotate: "-90deg"}}>
        <circle cx="180" cy="180" r="142" fill="none" stroke={theme.textColor} strokeOpacity="0.12" strokeWidth="22" />
        <circle cx="180" cy="180" r="142" fill="none" stroke={theme.accentColor} strokeWidth="22" strokeLinecap="round" pathLength={1} strokeDasharray="1" strokeDashoffset={1 - ring} />
      </svg>
      <div style={{position: "absolute", inset: 0, display: "grid", placeItems: "center"}}>
        <Icon size={128} color={theme.accentColor} strokeWidth={1.25} />
      </div>
      {[0.32, 0.55, 0.82].map((height, index) => <div key={index} style={{position: "absolute", bottom: -62, left: 92 + index * 74, width: 36, height: 120 * height * valueProgress, background: theme.accentColor, opacity: 0.28 + index * 0.22, borderRadius: "8px 8px 0 0"}} />)}
    </div>
  </div>;
};

const ProcessVisual: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const items = (scene.data?.items || [scene.name]).slice(0, 4);
  const active = Math.min(items.length - 1, Math.floor(frame / (fps * 2.35)));
  return <div style={{flex: 1, display: "flex", flexDirection: "column"}}>
    <SceneHeading scene={scene} theme={theme}>{scene.headline || "从任务到结果，逐步推进"}</SceneHeading>
    <div style={{position: "relative", display: "flex", flexDirection: "column", gap: 20, marginTop: 12}}>
      <div style={{position: "absolute", left: 39, top: 40, bottom: 40, width: 3, background: theme.textColor, opacity: 0.12}} />
      <div style={{position: "absolute", left: 39, top: 40, width: 3, height: `${interpolate(frame, [0, Math.max(1, items.length * fps * 2.35)], [0, 100], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})}%`, maxHeight: "calc(100% - 80px)", background: theme.accentColor}} />
      {items.map((item, index) => {
        const shown = index <= active;
        const progress = enter(frame, fps, index * Math.round(fps * 0.5));
        return <div key={`${item}-${index}`} style={{position: "relative", display: "grid", gridTemplateColumns: "80px 1fr auto", alignItems: "center", gap: 24, minHeight: 118, opacity: shown ? progress : 0.18, translate: `${shown ? 0 : 30}px 0`, scale: index === active ? 1.02 : 1, transformOrigin: "left center"}}>
          <div style={{width: 80, height: 80, borderRadius: "50%", display: "grid", placeItems: "center", background: index <= active ? theme.accentColor : theme.sceneLabelBackground, color: index <= active ? theme.background : theme.textColor, border: `2px solid ${theme.accentColor}`, fontSize: 30, fontWeight: 800, zIndex: 1}}>{index + 1}</div>
          <div style={{padding: "22px 26px", borderRadius: 16, background: theme.titleBackground, color: theme.textColor, fontSize: 34, fontWeight: index === active ? 750 : 550, lineHeight: 1.45, border: `1px solid ${index === active ? theme.accentColor : "transparent"}`}}>{item}</div>
          {index < active ? <CircleCheck size={38} color={theme.accentColor} /> : index === active ? <Zap size={38} color={theme.accentColor} /> : null}
        </div>;
      })}
    </div>
  </div>;
};

const ComparisonVisual: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const text = scene.narration || scene.description;
  const sides = text.split(/而不是|相比|对比|vs|VS|，但|，而/).map(part => part.trim()).filter(Boolean);
  const before = sides[0] || "传统方式：重复操作";
  const after = sides[1] || "AI 方式：任务自动协同";
  const reveal = interpolate(frame, [fps * 0.7, fps * 2.4], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  return <div style={{flex: 1, display: "flex", flexDirection: "column"}}>
    <SceneHeading scene={scene} theme={theme}>不是替换人，而是改变工作方式</SceneHeading>
    <div style={{display: "grid", gridTemplateColumns: "1fr 74px 1fr", gap: 14, alignItems: "center", flex: 1}}>
      <div style={{minHeight: 440, padding: 34, borderRadius: 24, background: theme.titleBackground, color: theme.textColor, opacity: 0.58 + (1 - reveal) * 0.42, scale: 1 - reveal * 0.04}}>
        <TriangleAlert size={66} color={theme.textColor} />
        <div style={{fontSize: 26, opacity: 0.65, marginTop: 28}}>过去 / 传统方式</div>
        <div style={{fontSize: 38, fontWeight: 700, lineHeight: 1.5, marginTop: 18}}>{before}</div>
      </div>
      <ArrowRight size={64} color={theme.accentColor} style={{translate: `${interpolate(reveal, [0, 1], [-20, 12])}px 0`}} />
      <div style={{minHeight: 440, padding: 34, borderRadius: 24, background: theme.accentColor, color: theme.background, opacity: enter(frame, fps, Math.round(fps * 0.7)), translate: `${interpolate(reveal, [0, 1], [60, 0])}px 0`, scale: 0.94 + reveal * 0.06}}>
        <Bot size={72} color={theme.background} />
        <div style={{fontSize: 26, opacity: 0.72, marginTop: 28}}>现在 / AI 协同</div>
        <div style={{fontSize: 38, fontWeight: 800, lineHeight: 1.5, marginTop: 18}}>{after}</div>
      </div>
    </div>
  </div>;
};

const TimelineVisual: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const items = (scene.data?.items || [scene.name]).slice(0, 4);
  const active = Math.min(items.length - 1, Math.floor(frame / (fps * 2.4)));
  return <div style={{flex: 1, display: "flex", flexDirection: "column", justifyContent: "center"}}>
    <SceneHeading scene={scene} theme={theme}>{scene.headline || scene.name}</SceneHeading>
    <div style={{position: "relative", display: "flex", justifyContent: "space-between", marginTop: 110, minHeight: 350}}>
      <div style={{position: "absolute", top: 43, left: 50, right: 50, height: 4, background: theme.textColor, opacity: 0.15}} />
      <div style={{position: "absolute", top: 43, left: 50, height: 4, width: `${active / Math.max(1, items.length - 1) * 88}%`, background: theme.accentColor}} />
      {items.map((item, index) => <div key={index} style={{position: "relative", width: `${92 / items.length}%`, opacity: index <= active ? 1 : 0.25, translate: `0 ${index === active ? -14 : 0}px`}}>
        <div style={{width: 88, height: 88, borderRadius: "50%", display: "grid", placeItems: "center", background: index <= active ? theme.accentColor : theme.titleBackground, color: index <= active ? theme.background : theme.textColor, fontSize: 28, fontWeight: 800}}>{index + 1}</div>
        <div style={{color: theme.textColor, fontSize: 29, fontWeight: index === active ? 750 : 500, lineHeight: 1.5, marginTop: 32}}>{item}</div>
      </div>)}
    </div>
  </div>;
};

const ArchitectureVisual: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const items = (scene.data?.items || scene.keywords || ["业务任务", "AI Agent", "结果交付"]).slice(0, 4);
  const active = Math.min(items.length - 1, Math.floor(frame / (fps * 2.3)));
  const positions = [[130, 130], [570, 100], [160, 500], [590, 470]];
  return <div style={{flex: 1, display: "flex", flexDirection: "column"}}>
    <SceneHeading scene={scene} theme={theme}>{scene.headline || "系统协同"}</SceneHeading>
    <div style={{position: "relative", flex: 1, minHeight: 690}}>
      <svg viewBox="0 0 900 700" style={{position: "absolute", inset: 0, width: "100%", height: "100%"}}>
        {items.slice(1).map((_, index) => <line key={index} x1="300" y1="350" x2={positions[index + 1][0] + 120} y2={positions[index + 1][1] + 70} stroke={theme.accentColor} strokeWidth="5" strokeDasharray="12 10" strokeDashoffset={-frame * 1.8} opacity={index < active ? 0.9 : 0.16} />)}
      </svg>
      <div style={{position: "absolute", left: 300, top: 280, width: 260, height: 150, borderRadius: 28, display: "grid", placeItems: "center", background: theme.accentColor, color: theme.background, scale: 1 + Math.sin(frame / 18) * 0.025}}>
        <Bot size={74} /><span style={{fontSize: 28, fontWeight: 800}}>AI 协同中枢</span>
      </div>
      {items.map((item, index) => <div key={index} style={{position: "absolute", left: positions[index][0], top: positions[index][1], width: 240, minHeight: 130, padding: 20, borderRadius: 22, background: theme.titleBackground, border: `2px solid ${index <= active ? theme.accentColor : "transparent"}`, color: theme.textColor, opacity: index <= active ? 1 : 0.3, scale: index === active ? 1.06 : 0.94}}>
        {index % 2 ? <Database size={40} color={theme.accentColor} /> : <Workflow size={40} color={theme.accentColor} />}
        <div style={{fontSize: 28, fontWeight: 700, lineHeight: 1.4, marginTop: 12}}>{item}</div>
      </div>)}
    </div>
  </div>;
};

const MapVisual: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const locations = (scene.locations?.length ? scene.locations : scene.data?.items || ["起点", "目标"]).slice(0, 4);
  const points = [[190, 480], [460, 270], [710, 460], [520, 650]];
  const active = Math.min(locations.length - 1, Math.floor(frame / (fps * 2.4)));
  const path = locations.map((_, index) => `${index ? "L" : "M"} ${points[index][0]} ${points[index][1]}`).join(" ");
  return <div style={{flex: 1, display: "flex", flexDirection: "column"}}>
    <SceneHeading scene={scene} theme={theme}>{scene.headline || "业务路线"}</SceneHeading>
    <div style={{position: "relative", flex: 1, minHeight: 730, borderRadius: 32, overflow: "hidden", background: theme.titleBackground, scale: 1 + interpolate(frame, [0, fps * 8], [0, 0.035], {extrapolateRight: "clamp"})}}>
      <svg viewBox="0 0 900 760" style={{position: "absolute", inset: 0, width: "100%", height: "100%"}}>
        <defs><pattern id="content-map-grid" width="70" height="70" patternUnits="userSpaceOnUse"><path d="M70 0H0V70" fill="none" stroke={theme.textColor} strokeOpacity="0.08" /></pattern></defs>
        <rect width="900" height="760" fill="url(#content-map-grid)" />
        <path d="M60 180 C220 60 390 160 510 90 C700 20 830 160 850 330 C790 520 660 690 430 700 C210 660 40 480 60 180Z" fill={theme.accentColor} opacity="0.055" />
        <path d={path} fill="none" stroke={theme.accentColor} strokeWidth="8" strokeLinecap="round" strokeDasharray="16 12" pathLength={1} strokeDashoffset={interpolate(frame, [0, fps * 5], [1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})} />
      </svg>
      {locations.map((location, index) => <div key={location} style={{position: "absolute", left: `${points[index][0] / 9}%`, top: `${points[index][1] / 7.6}%`, translate: "-50% -50%", textAlign: "center", opacity: index <= active ? 1 : 0.22, scale: index === active ? 1.12 : 0.88}}>
        <MapPin size={index === active ? 76 : 58} color={theme.accentColor} fill={index < active ? theme.accentColor : "transparent"} />
        <div style={{marginTop: 8, padding: "10px 18px", borderRadius: 12, background: theme.titleBackground, color: theme.textColor, fontSize: 28, fontWeight: 750, whiteSpace: "nowrap"}}>{location}</div>
      </div>)}
    </div>
  </div>;
};

const QuoteVisual: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const Icon = iconFor(scene);
  const progress = enter(frame, fps);
  return <div style={{flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", textAlign: "center"}}>
    <div style={{width: 118, height: 118, borderRadius: "50%", display: "grid", placeItems: "center", background: theme.titleBackground, scale: 1 + Math.sin(frame / 24) * 0.04}}><Icon size={62} color={theme.accentColor} strokeWidth={1.4} /></div>
    <div style={{color: theme.textColor, fontSize: 54, fontWeight: 650, lineHeight: 1.65, marginTop: 54, textWrap: "balance", opacity: progress, translate: `0 ${interpolate(progress, [0, 1], [35, 0])}px`}}>「<HighlightText text={scene.narration || scene.description} scene={scene} theme={theme} />」</div>
    <div style={{width: interpolate(frame, [fps * 0.5, fps * 2.8], [0, 260], {extrapolateLeft: "clamp", extrapolateRight: "clamp"}), height: 5, background: theme.accentColor, marginTop: 54, borderRadius: 4}} />
  </div>;
};

const KeyPointVisual: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const Icon = iconFor(scene);
  const beat = Math.floor(frame / (fps * 2.7));
  const keywords = (scene.keywords?.length ? scene.keywords : scene.data?.items || ["真实任务", "清晰目标", "完整交付"]).slice(0, 4);
  return <div style={{flex: 1, display: "flex", flexDirection: "column"}}>
    <SceneHeading scene={scene} theme={theme}>{scene.type === "cta" ? "下一步，从一个真实任务开始" : scene.headline || scene.name}</SceneHeading>
    <div style={{display: "grid", gridTemplateColumns: "210px 1fr", gap: 42, alignItems: "center", flex: 1}}>
      <div style={{width: 200, height: 200, borderRadius: 44, display: "grid", placeItems: "center", background: theme.accentColor, color: theme.background, rotate: `${beat % 2 ? -3 : 3}deg`, scale: enter(frame, fps)}}><Icon size={112} strokeWidth={1.35} /></div>
      <div style={{color: theme.textColor, fontSize: scene.type === "hook" ? 54 : 44, fontWeight: 700, lineHeight: 1.55, textWrap: "balance"}}><HighlightText text={scene.narration || scene.description} scene={scene} theme={theme} /></div>
    </div>
    <div style={{display: "flex", flexWrap: "wrap", gap: 16, marginTop: 30}}>{keywords.map((keyword, index) => <div key={keyword} style={{padding: "16px 22px", borderRadius: 14, background: index === beat % keywords.length ? theme.accentColor : theme.titleBackground, color: index === beat % keywords.length ? theme.background : theme.textColor, fontSize: 27, fontWeight: 700, opacity: enter(frame, fps, index * 7)}}>{keyword}</div>)}</div>
  </div>;
};

const MediaVisual: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return <div style={{position: "absolute", inset: 0, fontFamily}}>
    <Backdrop theme={theme} />
    <SceneMedia scene={scene} opacity={0.72} />
    <div style={{position: "absolute", inset: 0, background: "linear-gradient(180deg, rgba(0,0,0,.16) 0%, rgba(0,0,0,.08) 42%, rgba(0,0,0,.78) 100%)"}} />
    <div style={{position: "absolute", left: 76, right: 76, bottom: 370, padding: "28px 30px", borderRadius: 22, background: theme.titleBackground, color: theme.textColor, opacity: enter(frame, fps), translate: `0 ${interpolate(enter(frame, fps), [0, 1], [50, 0])}px`}}>
      <div style={{color: theme.accentColor, fontSize: 24, letterSpacing: 2, marginBottom: 12}}>{typeNames.media} · 真实内容</div>
      <div style={{fontSize: 38, fontWeight: 700, lineHeight: 1.5}}><HighlightText text={scene.narration || scene.description} scene={scene} theme={theme} /></div>
    </div>
  </div>;
};

export const SmartScene: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  if (scene.type === "media" && scene.media) return <MediaVisual scene={scene} theme={theme} />;
  if (hasStyleVariant(theme)) return <StyleScene scene={scene} theme={theme} />;
  const content = scene.type === "metric" ? <MetricVisual scene={scene} theme={theme} />
    : scene.type === "process" ? <ProcessVisual scene={scene} theme={theme} />
      : scene.type === "comparison" ? <ComparisonVisual scene={scene} theme={theme} />
        : scene.type === "timeline" ? <TimelineVisual scene={scene} theme={theme} />
          : scene.type === "architecture" ? <ArchitectureVisual scene={scene} theme={theme} />
            : scene.type === "map" ? <MapVisual scene={scene} theme={theme} />
              : scene.type === "quote" ? <QuoteVisual scene={scene} theme={theme} />
                : <KeyPointVisual scene={scene} theme={theme} />;
  return <div style={{position: "absolute", inset: 0, overflow: "hidden", fontFamily}}>
    <Backdrop theme={theme} />
    <div style={{position: "absolute", inset: 0, display: "flex", flexDirection: "column", padding: "330px 74px 390px"}}>{content}</div>
  </div>;
};
