import {ArrowRight, Check, Heart, MapPin, Play, Sparkles, Terminal, TrendingUp} from "lucide-react";
import React from "react";
import {interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {Backdrop, SceneMedia} from "./effects";
import type {TalkingHeadAppearance, TalkingHeadScene} from "./VideoComposition";

const sans = "Arial, PingFang SC, Microsoft YaHei, sans-serif";
const serif = "Songti SC, STSong, SimSun, serif";

const useEnter = (delay = 0) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: Math.max(0, frame - delay), fps, config: {damping: 18, stiffness: 110}});
};

const metricOf = (scene: TalkingHeadScene) => scene.data?.metric || null;
const itemsOf = (scene: TalkingHeadScene) => (scene.data?.items?.length ? scene.data.items : [scene.name]).slice(0, 3);
const narrationOf = (scene: TalkingHeadScene) => scene.narration || scene.description || scene.name;

const FounderScene: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = useEnter();
  const metric = metricOf(scene);
  const count = metric ? Math.round(metric.value * interpolate(frame, [0, fps * 2.4], [0, 1], {extrapolateRight: "clamp"})) : null;
  return <div style={{position: "absolute", inset: 0, fontFamily: sans}}>
    <Backdrop theme={theme} grid={false} />
    <SceneMedia scene={scene} opacity={0.22} />
    <div style={{position: "absolute", left: 72, top: 330, bottom: 380, width: 6, background: theme.accentColor}} />
    <div style={{position: "absolute", left: 112, right: 64, top: 320, color: theme.accentColor, fontSize: 22, letterSpacing: 5}}>FOUNDER'S NOTE / 创始人笔记</div>
    <div style={{position: "absolute", left: 102, top: 350, color: theme.accentColor, opacity: 0.16, fontFamily: serif, fontSize: 330, lineHeight: 1}}>“</div>
    <div style={{position: "absolute", left: 112, right: 74, top: 480, color: theme.textColor, fontSize: 62, fontWeight: 760, lineHeight: 1.48, letterSpacing: -1, clipPath: `inset(0 ${100 - enter * 100}% 0 0)`}}>{narrationOf(scene)}</div>
    {metric ? <div style={{position: "absolute", right: 64, bottom: 385, color: theme.accentColor, fontSize: 142, fontWeight: 850, lineHeight: 1, letterSpacing: -7}}>{count}<span style={{fontSize: 56, letterSpacing: 0}}>{metric.unit}</span></div> : <div style={{position: "absolute", right: 74, bottom: 430, color: theme.accentColor, fontSize: 28, fontStyle: "italic", opacity: 0.75}}>真实经验，不是标准答案</div>}
    <div style={{position: "absolute", left: 112, bottom: 370, display: "flex", gap: 12}}>{itemsOf(scene).map((item, index) => <div key={index} style={{borderTop: `2px solid ${theme.accentColor}`, paddingTop: 10, width: 180, color: theme.textColor, opacity: 0.55 + index * 0.15, fontSize: 20}}>0{index + 1} {item.slice(0, 12)}</div>)}</div>
  </div>;
};

const EnterpriseScene: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = useEnter();
  const metric = metricOf(scene);
  const items = itemsOf(scene);
  return <div style={{position: "absolute", inset: 0, fontFamily: sans}}>
    <Backdrop theme={theme} />
    <div style={{position: "absolute", left: 54, right: 54, top: 320, bottom: 360, borderRadius: 28, background: theme.titleBackground, border: `1px solid ${theme.accentColor}35`, boxShadow: "0 24px 80px rgba(0,0,0,.12)", opacity: enter, translate: `0 ${(1 - enter) * 45}px`}}>
      <div style={{height: 74, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 30px", borderBottom: `1px solid ${theme.accentColor}30`, color: theme.textColor}}>
        <div style={{display: "flex", alignItems: "center", gap: 12}}><span style={{width: 12, height: 12, borderRadius: "50%", background: theme.accentColor}} /><strong style={{fontSize: 23}}>业务落地工作台</strong></div>
        <span style={{fontSize: 18, letterSpacing: 2, color: theme.accentColor}}>LIVE WORKFLOW</span>
      </div>
      <div style={{display: "grid", gridTemplateColumns: metric ? "0.85fr 1.15fr" : "1fr", gap: 24, padding: 30}}>
        {metric ? <div style={{borderRadius: 20, padding: 26, background: theme.accentColor, color: theme.background}}>
          <div style={{fontSize: 20, opacity: 0.75}}>当前核心指标</div>
          <div style={{fontSize: 94, fontWeight: 850, marginTop: 26, letterSpacing: -5}}>{Math.round(metric.value * interpolate(frame, [0, fps * 2.2], [0, 1], {extrapolateRight: "clamp"}))}<span style={{fontSize: 40}}>{metric.unit}</span></div>
          <div style={{display: "flex", alignItems: "center", gap: 8, marginTop: 22, fontSize: 21}}><TrendingUp size={26} />{metric.direction === "down" ? "重复投入下降" : "业务结果提升"}</div>
        </div> : null}
        <div style={{color: theme.textColor}}>
          <div style={{fontSize: 32, fontWeight: 750, lineHeight: 1.45}}>{scene.headline || scene.name}</div>
          <div style={{fontSize: 25, lineHeight: 1.55, opacity: 0.72, marginTop: 14}}>{narrationOf(scene)}</div>
          <div style={{display: "flex", flexDirection: "column", gap: 14, marginTop: 26}}>{items.map((item, index) => {
            const active = Math.min(items.length - 1, Math.floor(frame / (fps * 2.2)));
            return <div key={index} style={{display: "grid", gridTemplateColumns: "40px 1fr auto", alignItems: "center", gap: 14, padding: "14px 16px", borderRadius: 12, background: index === active ? `${theme.accentColor}22` : "transparent", border: `1px solid ${index === active ? theme.accentColor : `${theme.accentColor}25`}`, opacity: index <= active ? 1 : 0.35}}>
              <span style={{width: 34, height: 34, borderRadius: 9, display: "grid", placeItems: "center", background: index <= active ? theme.accentColor : theme.sceneLabelBackground, color: index <= active ? theme.background : theme.textColor, fontSize: 19, fontWeight: 800}}>{index + 1}</span>
              <span style={{fontSize: 23, fontWeight: 600}}>{item}</span>{index < active ? <Check size={25} color={theme.accentColor} /> : null}
            </div>;
          })}</div>
        </div>
      </div>
    </div>
  </div>;
};

const TechScene: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const metric = metricOf(scene);
  const text = narrationOf(scene);
  const typed = text.slice(0, Math.floor(interpolate(frame, [0, fps * 2.5], [0, text.length], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})));
  const active = Math.floor(frame / (fps * 2.4)) % 3;
  return <div style={{position: "absolute", inset: 0, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace"}}>
    <Backdrop theme={theme} />
    <div style={{position: "absolute", left: 58, right: 58, top: 330, bottom: 390, borderRadius: 18, background: "rgba(3,9,18,.9)", border: `1px solid ${theme.accentColor}80`, boxShadow: `0 0 45px ${theme.accentColor}18`, overflow: "hidden"}}>
      <div style={{height: 66, display: "flex", alignItems: "center", gap: 10, padding: "0 24px", background: `${theme.accentColor}12`, borderBottom: `1px solid ${theme.accentColor}40`}}>
        {["#ff5f57", "#febc2e", "#28c840"].map(color => <span key={color} style={{width: 15, height: 15, borderRadius: "50%", background: color}} />)}
        <span style={{marginLeft: 18, color: theme.accentColor, fontSize: 19}}>agent workflow — live</span><Terminal size={23} color={theme.accentColor} style={{marginLeft: "auto"}} />
      </div>
      <div style={{padding: "34px 32px", color: theme.textColor, fontSize: 25, lineHeight: 1.8}}>
        <div><span style={{color: theme.accentColor}}>const</span> objective = <span style={{color: "#ffd580"}}>"{scene.headline || scene.name}"</span>;</div>
        <div style={{marginTop: 22}}><span style={{color: theme.accentColor}}>await</span> agent.run(<span style={{color: "#9dffcf"}}>task</span>);</div>
        <div style={{marginTop: 22, color: "#9dffcf"}}>// {typed}<span style={{opacity: Math.floor(frame / 12) % 2 ? 0 : 1}}>▋</span></div>
        {metric ? <div style={{marginTop: 38, padding: "22px 24px", border: `1px solid ${theme.accentColor}`, background: `${theme.accentColor}0d`}}>
          <span style={{fontSize: 19}}>OPTIMIZATION_METRIC</span>
          <div style={{color: theme.accentColor, fontSize: 88, fontWeight: 800, lineHeight: 1.2}}>{Math.round(metric.value * interpolate(frame, [0, fps * 2.2], [0, 1], {extrapolateRight: "clamp"}))}{metric.unit}</div>
        </div> : null}
        <div style={{display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14, marginTop: 30}}>{itemsOf(scene).map((item, index) => <div key={index} style={{padding: 14, border: `1px solid ${index === active ? theme.accentColor : `${theme.accentColor}35`}`, background: index === active ? `${theme.accentColor}18` : "transparent", fontSize: 18}}>[{index === active ? "RUNNING" : index < active ? "DONE" : "QUEUED"}]<br />{item.slice(0, 15)}</div>)}</div>
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: interpolate(frame % (fps * 4), [0, fps * 4], [66, 850]), height: 2, background: theme.accentColor, opacity: 0.2}} />
    </div>
  </div>;
};

const WarmScene: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const enter = useEnter();
  const metric = metricOf(scene);
  return <div style={{position: "absolute", inset: 0, fontFamily: serif}}>
    <Backdrop theme={theme} grid={false} />
    <SceneMedia scene={scene} opacity={0.2} />
    <div style={{position: "absolute", left: 82, right: 82, top: 370, bottom: 430, padding: "60px 52px", background: "rgba(255,253,247,.88)", boxShadow: "0 18px 55px rgba(90,60,45,.14)", rotate: `${interpolate(enter, [0, 1], [-2.5, -0.6])}deg`, opacity: enter}}>
      <div style={{position: "absolute", left: 50, top: -42, width: 86, height: 86, borderRadius: "50%", display: "grid", placeItems: "center", background: theme.accentColor}}><Heart size={42} color="#fff" /></div>
      <div style={{color: theme.accentColor, fontSize: 21, letterSpacing: 4, textAlign: "center"}}>写给你的一段话</div>
      <div style={{color: theme.textColor, fontSize: 43, fontWeight: 600, lineHeight: 1.85, marginTop: 34, textAlign: "center", textWrap: "balance"}}>{narrationOf(scene)}</div>
      {metric ? <div style={{margin: "28px auto 0", width: 150, padding: "12px 20px", border: `2px solid ${theme.accentColor}`, borderRadius: "50%", color: theme.accentColor, fontSize: 44, fontWeight: 700, textAlign: "center", rotate: "-5deg"}}>{metric.value}{metric.unit}</div> : null}
      <div style={{marginTop: 36, color: theme.accentColor, textAlign: "center", fontSize: 23, fontStyle: "italic"}}>愿你也允许自己，慢下来。</div>
    </div>
    <div style={{position: "absolute", left: 110, bottom: 390, width: interpolate(frame, [0, 75], [0, 260], {extrapolateRight: "clamp"}), height: 2, background: theme.accentColor, opacity: 0.6}} />
  </div>;
};

const PromoScene: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = useEnter();
  const metric = metricOf(scene);
  return <div style={{position: "absolute", inset: 0, overflow: "hidden", fontFamily: sans}}>
    <Backdrop theme={theme} grid={false} />
    <div style={{position: "absolute", left: -220, right: 180, top: 290, bottom: 520, background: theme.accentColor, rotate: "-10deg", translate: `${(1 - enter) * -500}px 0`}} />
    <div style={{position: "absolute", right: -80, top: 280, color: theme.textColor, opacity: 0.06, fontSize: 430, fontWeight: 900, letterSpacing: -40}}>AI</div>
    <div style={{position: "absolute", left: 68, right: 68, top: 360}}>
      <div style={{display: "inline-flex", alignItems: "center", gap: 10, padding: "12px 20px", background: theme.textColor, color: theme.background, fontSize: 22, fontWeight: 800, letterSpacing: 2, rotate: "-2deg"}}><Sparkles size={25} />LIMITED / 限时方法公开</div>
      <div style={{color: theme.textColor, fontSize: 68, fontWeight: 900, lineHeight: 1.25, marginTop: 34, textTransform: "uppercase", textWrap: "balance", textShadow: "0 3px 0 rgba(0,0,0,.16)"}}>{scene.headline || scene.name}</div>
      <div style={{color: theme.textColor, fontSize: 37, fontWeight: 700, lineHeight: 1.5, marginTop: 26, maxWidth: 760}}>{narrationOf(scene)}</div>
      {metric ? <div style={{color: theme.textColor, fontSize: 154, fontWeight: 900, letterSpacing: -8, lineHeight: 1, marginTop: 20}}>{Math.round(metric.value * interpolate(frame, [0, fps * 2], [0, 1], {extrapolateRight: "clamp"}))}<span style={{fontSize: 62}}>{metric.unit}</span></div> : null}
      <div style={{display: "flex", flexWrap: "wrap", gap: 12, marginTop: 28}}>{itemsOf(scene).map((item, index) => <span key={index} style={{padding: "12px 18px", border: `2px solid ${theme.textColor}`, color: theme.textColor, fontSize: 22, fontWeight: 700, opacity: Math.min(1, Math.max(0, frame / fps - index * 0.5))}}>✓ {item}</span>)}</div>
    </div>
    <div style={{position: "absolute", left: 70, right: 70, bottom: 350, height: 86, display: "flex", alignItems: "center", justifyContent: "center", gap: 18, borderRadius: 8, background: theme.textColor, color: theme.background, fontSize: 32, fontWeight: 900, scale: 1 + Math.sin(frame / 15) * 0.025, boxShadow: `10px 10px 0 ${theme.accentColor}`}}><Play size={34} fill="currentColor" />现在开始，少走弯路<ArrowRight size={38} /></div>
  </div>;
};

const MapStyleScene: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const items = (scene.locations?.length ? scene.locations : itemsOf(scene)).slice(0, 3);
  const active = Math.min(items.length - 1, Math.floor(frame / (fps * 2.4)));
  const points = [[220, 700], [530, 420], [770, 650]];
  return <div style={{position: "absolute", inset: 0, fontFamily: sans}}>
    <Backdrop theme={theme} grid={false} />
    <div style={{position: "absolute", left: 50, top: 330, width: 320, bottom: 390, padding: 28, background: theme.titleBackground, color: theme.textColor, zIndex: 2, borderLeft: `5px solid ${theme.accentColor}`}}>
      <div style={{color: theme.accentColor, fontSize: 22, letterSpacing: 3}}>ROUTE / 业务路线</div>
      <div style={{fontSize: 36, fontWeight: 800, lineHeight: 1.45, marginTop: 20}}>{scene.headline || scene.name}</div>
      <div style={{display: "flex", flexDirection: "column", gap: 26, marginTop: 36}}>{items.map((item, index) => <div key={index} style={{display: "flex", alignItems: "center", gap: 14, opacity: index <= active ? 1 : 0.3}}><MapPin size={30} color={theme.accentColor} /><span style={{fontSize: 26, fontWeight: index === active ? 800 : 500}}>{item}</span></div>)}</div>
      <div style={{fontSize: 22, lineHeight: 1.65, opacity: 0.68, marginTop: 36}}>{narrationOf(scene)}</div>
    </div>
    <svg viewBox="0 0 1080 1300" style={{position: "absolute", left: 260, top: 290, width: 900, height: 1100, scale: 1 + interpolate(frame, [0, fps * 8], [0, 0.05], {extrapolateRight: "clamp"}), translate: `${interpolate(frame, [0, fps * 8], [0, -35], {extrapolateRight: "clamp"})}px 0`}}>
      <defs><pattern id="route-grid" width="65" height="65" patternUnits="userSpaceOnUse"><path d="M65 0H0V65" fill="none" stroke={theme.textColor} strokeOpacity="0.09" /></pattern></defs>
      <rect width="1080" height="1300" fill="url(#route-grid)" />
      <path d="M120 240 C300 80 490 220 650 130 C830 80 980 260 920 480 C1010 720 810 990 610 1040 C350 1120 100 900 130 660 C40 500 40 360 120 240Z" fill={theme.accentColor} opacity="0.08" />
      <path d={items.map((_, index) => `${index ? "L" : "M"}${points[index][0]},${points[index][1]}`).join(" ")} fill="none" stroke={theme.accentColor} strokeWidth="9" strokeDasharray="18 12" pathLength={1} strokeDashoffset={interpolate(frame, [0, fps * 4], [1, 0], {extrapolateRight: "clamp"})} />
      {items.map((item, index) => <g key={index} opacity={index <= active ? 1 : 0.25}><circle cx={points[index][0]} cy={points[index][1]} r={index === active ? 32 : 22} fill={theme.accentColor} /><text x={points[index][0] + 45} y={points[index][1] + 10} fill={theme.textColor} fontSize="34" fontWeight="700">{item}</text></g>)}
    </svg>
  </div>;
};

export const StyleScene: React.FC<{scene: TalkingHeadScene; theme: TalkingHeadAppearance}> = ({scene, theme}) => {
  switch (theme.variant) {
    case "founder": return <FounderScene scene={scene} theme={theme} />;
    case "enterprise": return <EnterpriseScene scene={scene} theme={theme} />;
    case "tech": return <TechScene scene={scene} theme={theme} />;
    case "warm": return <WarmScene scene={scene} theme={theme} />;
    case "promo": return <PromoScene scene={scene} theme={theme} />;
    case "map": return <MapStyleScene scene={scene} theme={theme} />;
    default: return null;
  }
};

export const hasStyleVariant = (theme: TalkingHeadAppearance) => Boolean(theme.variant && ["founder", "enterprise", "tech", "warm", "promo", "map"].includes(theme.variant));
