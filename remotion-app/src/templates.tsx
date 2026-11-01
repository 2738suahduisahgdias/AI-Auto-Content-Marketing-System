import React from "react";
import {
  Easing,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {BasicCaptions} from "./basic-captions";
import {Backdrop, SceneFade, SceneMedia} from "./effects";
import {Narration} from "./narration";
import {
  TalkingHeadAppearance,
  TalkingHeadProps,
  TalkingHeadScene,
} from "./VideoComposition";

const fontFamily = "Arial, PingFang SC, Microsoft YaHei, sans-serif";

const fallbackAppearance: TalkingHeadAppearance = {
  background: "#10251e",
  sceneBackground: "linear-gradient(145deg, #173d2e 0%, #0c1f19 70%)",
  textColor: "#f5f8f3",
  accentColor: "#d7f277",
  titleBackground: "rgba(9, 27, 21, 0.84)",
  sceneLabelBackground: "rgba(8, 25, 19, 0.76)",
  captionBackground: "rgba(64, 64, 64, 0.75)",
  captionColor: "#ffffff",
};

export const mediaSource = (src: string) =>
  /^(https?:|data:|blob:)/.test(src) ? src : staticFile(src);

export const useTheme = (appearance?: Partial<TalkingHeadAppearance>) => ({
  ...fallbackAppearance,
  ...appearance,
});

export const fadeIn = (frame: number, fps: number, delay = 0) =>
  interpolate(frame - delay, [0, Math.max(1, fps / 2)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

export const riseIn = (frame: number, fps: number, delay = 0) => {
  const progress = spring({
    frame: Math.max(0, frame - delay),
    fps,
    config: {damping: 16, stiffness: 120},
  });
  return {opacity: progress, transform: `translateY(${(1 - progress) * 60}px)`};
};

export const CaptionLayer: React.FC<{
  captions: TalkingHeadProps["captions"];
  theme: TalkingHeadAppearance;
}> = ({captions, theme}) => (
  <BasicCaptions
    width={900}
    style={{position: "absolute", bottom: 130, translate: "90px 0px"}}
    captions={captions}
    captionBackground={theme.captionBackground}
    captionColor={theme.captionColor}
  />
);

export const SceneSequences: React.FC<{
  scenes: TalkingHeadScene[];
  children: (scene: TalkingHeadScene, index: number) => React.ReactNode;
}> = ({scenes, children}) => {
  const {fps} = useVideoConfig();
  return (
    <>
      {scenes.map((scene, index) => (
        <Sequence
          key={scene.id}
          name={scene.name}
          from={Math.max(0, Math.round(scene.start_seconds * fps))}
          durationInFrames={Math.max(
            1,
            Math.round((scene.end_seconds - scene.start_seconds) * fps),
          )}
          premountFor={fps}
        >
          {children(scene, index)}
        </Sequence>
      ))}
    </>
  );
};

export const HeaderCard: React.FC<{
  eyebrow: string;
  title: string;
  theme: TalkingHeadAppearance;
}> = ({eyebrow, title, theme}) => (
  <div
    style={{
      position: "absolute",
      top: 86,
      left: 70,
      right: 70,
      padding: "26px 30px",
      borderRadius: 20,
      background: theme.titleBackground,
      color: theme.textColor,
      fontFamily,
    }}
  >
    <div
      style={{
        color: theme.accentColor,
        fontSize: 26,
        letterSpacing: 3,
        marginBottom: 12,
      }}
    >
      {eyebrow}
    </div>
    <div
      style={{
        fontSize: 44,
        fontWeight: 700,
        lineHeight: 1.35,
        textWrap: "balance",
        display: "-webkit-box",
        WebkitLineClamp: 2,
        WebkitBoxOrient: "vertical",
        overflow: "hidden",
      }}
    >
      {title}
    </div>
  </div>
);

// 宣传·产品推广：大标题、卖点逐条推进、结尾行动号召
export const PromoComposition: React.FC<TalkingHeadProps> = ({
  title,
  scenes,
  audio,
  audioSegments,
  captions,
  appearance,
}) => {
  const theme = useTheme(appearance);
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  return (
    <div style={{position: "absolute", inset: 0, fontFamily}}>
      <Backdrop theme={theme} grid={false} />
      <Narration audio={audio} audioSegments={audioSegments} />
      <SceneSequences scenes={scenes}>
        {(scene, index) => (
          <SceneFade durationSeconds={scene.end_seconds - scene.start_seconds}>
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              padding: "260px 90px 420px",
            }}
          >
            <SceneMedia scene={scene} opacity={0.45} />
            {scene.media ? <div style={{position: "absolute", inset: 0, background: "linear-gradient(180deg, rgba(0,0,0,0.25) 0%, rgba(0,0,0,0.55) 100%)"}} /> : null}
            <div
              style={{
                color: theme.accentColor,
                fontSize: 120,
                fontWeight: 800,
                lineHeight: 1,
                ...riseIn(frame, fps),
              }}
            >
              {String(index + 1).padStart(2, "0")}
            </div>
            <div
              style={{
                color: theme.textColor,
                fontSize: 64,
                fontWeight: 750,
                lineHeight: 1.4,
                marginTop: 30,
                textWrap: "balance",
                ...riseIn(frame, fps, Math.round(fps * 0.25)),
              }}
            >
              {scene.name}
            </div>
            <div
              style={{
                color: theme.textColor,
                opacity: 0.82 * fadeIn(frame, fps, Math.round(fps * 0.5)),
                fontSize: 40,
                lineHeight: 1.6,
                marginTop: 26,
              }}
            >
              {scene.description}
            </div>
          </div>
          </SceneFade>
        )}
      </SceneSequences>
      <Sequence from={Math.max(0, durationInFrames - Math.round(fps * 1.6))} name="行动号召">
        <div
          style={{
            position: "absolute",
            left: 70,
            right: 70,
            bottom: 330,
            padding: "30px 36px",
            borderRadius: 24,
            background: theme.accentColor,
            color: theme.background,
            fontSize: 44,
            fontWeight: 800,
            textAlign: "center",
            fontFamily,
          }}
        >
          {title} · 了解更多
        </div>
      </Sequence>
      <HeaderCard eyebrow="产品推荐" title={title} theme={theme} />
      <CaptionLayer captions={captions} theme={theme} />
    </div>
  );
};

// 科技·产品演示：深色网格、终端风格标签、功能卡推进
export const TechShowcaseComposition: React.FC<TalkingHeadProps> = ({
  title,
  scenes,
  audio,
  audioSegments,
  captions,
  appearance,
}) => {
  const theme = useTheme(appearance);
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <div style={{position: "absolute", inset: 0, fontFamily}}>
      <Backdrop theme={theme} />
      <Narration audio={audio} audioSegments={audioSegments} />
      <SceneSequences scenes={scenes}>
        {(scene, index) => (
          <SceneFade durationSeconds={scene.end_seconds - scene.start_seconds}>
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "240px 80px 420px",
            }}
          >
            <SceneMedia scene={scene} opacity={0.35} />
            <div
              style={{
                width: "100%",
                border: `1px solid ${theme.accentColor}`,
                borderRadius: 18,
                background: theme.titleBackground,
                padding: "46px 50px",
                ...riseIn(frame, fps),
              }}
            >
              <div
                style={{
                  color: theme.accentColor,
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                  fontSize: 28,
                  letterSpacing: 2,
                }}
              >
                $ feature_{String(index + 1).padStart(2, "0")} --{scene.asset_type}
              </div>
              <div
                style={{
                  color: theme.textColor,
                  fontSize: 58,
                  fontWeight: 700,
                  lineHeight: 1.4,
                  marginTop: 24,
                }}
              >
                {scene.name}
              </div>
              <div
                style={{
                  color: theme.textColor,
                  opacity: 0.8,
                  fontSize: 38,
                  lineHeight: 1.6,
                  marginTop: 22,
                }}
              >
                {scene.description}
              </div>
            </div>
          </div>
          </SceneFade>
        )}
      </SceneSequences>
      <HeaderCard eyebrow="TECH / DEMO" title={title} theme={theme} />
      <CaptionLayer captions={captions} theme={theme} />
    </div>
  );
};

// 数据·案例复盘：柱状图随分镜推进生长，显示每项占比
export const DataStoryComposition: React.FC<TalkingHeadProps> = ({
  title,
  scenes,
  audio,
  audioSegments,
  captions,
  appearance,
}) => {
  const theme = useTheme(appearance);
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const total = Math.max(
    1,
    scenes.reduce((sum, scene) => sum + (scene.end_seconds - scene.start_seconds), 0),
  );
  return (
    <div style={{position: "absolute", inset: 0, fontFamily}}>
      <Backdrop theme={theme} />
      <Narration audio={audio} audioSegments={audioSegments} />
      <div
        style={{
          position: "absolute",
          left: 80,
          right: 80,
          top: 430,
          bottom: 430,
          display: "flex",
          alignItems: "flex-end",
          gap: 36,
        }}
      >
        {scenes.map((scene, index) => {
          const share = (scene.end_seconds - scene.start_seconds) / total;
          const height = spring({
            frame: Math.max(0, frame - index * Math.round(fps * 0.4)),
            fps,
            config: {damping: 18, stiffness: 90},
          });
          return (
            <div key={scene.id} style={{flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end", height: "100%"}}>
              <div
                style={{
                  color: theme.accentColor,
                  fontSize: 40,
                  fontWeight: 800,
                  textAlign: "center",
                  opacity: fadeIn(frame, fps, index * Math.round(fps * 0.4)),
                }}
              >
                {Math.round(share * 100)}%
              </div>
              <div
                style={{
                  height: `${Math.max(4, share * 100 * height)}%`,
                  background: `linear-gradient(180deg, ${theme.accentColor} 0%, ${theme.accentColor}55 100%)`,
                  borderRadius: "16px 16px 0 0",
                  marginTop: 14,
                }}
              />
              <div
                style={{
                  color: theme.textColor,
                  fontSize: 26,
                  lineHeight: 1.4,
                  textAlign: "center",
                  marginTop: 18,
                  minHeight: 74,
                }}
              >
                {scene.name}
              </div>
            </div>
          );
        })}
      </div>
      <HeaderCard eyebrow="数据复盘" title={title} theme={theme} />
      <CaptionLayer captions={captions} theme={theme} />
    </div>
  );
};

// 音频·波形金句：大金句 + 随时间流动的波形
export const AudiogramComposition: React.FC<TalkingHeadProps> = ({
  title,
  scenes,
  audio,
  audioSegments,
  captions,
  appearance,
}) => {
  const theme = useTheme(appearance);
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const bars = 36;
  return (
    <div style={{position: "absolute", inset: 0, fontFamily}}>
      <Backdrop theme={theme} grid={false} />
      <Narration audio={audio} audioSegments={audioSegments} />
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "300px 90px 430px",
        }}
      >
        <div
          style={{
            color: theme.textColor,
            fontSize: 62,
            fontWeight: 700,
            lineHeight: 1.5,
            textAlign: "center",
            textWrap: "balance",
            ...riseIn(frame, fps),
          }}
        >
          「{title}」
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            height: 150,
            marginTop: 70,
          }}
        >
          {Array.from({length: bars}, (_, index) => {
            const wave =
              0.35 +
              0.65 *
                Math.abs(
                  Math.sin(frame / 6 + index * 0.55) * Math.cos(frame / 11 + index * 0.3),
                );
            return (
              <div
                key={index}
                style={{
                  width: 12,
                  height: `${Math.round(wave * 100)}%`,
                  borderRadius: 6,
                  background: theme.accentColor,
                  opacity: 0.55 + 0.45 * wave,
                }}
              />
            );
          })}
        </div>
        <div
          style={{
            color: theme.textColor,
            opacity: 0.7,
            fontSize: 30,
            textAlign: "center",
            marginTop: 50,
          }}
        >
          {scenes[0]?.description || scenes[0]?.name || ""}
        </div>
      </div>
      <CaptionLayer captions={captions} theme={theme} />
    </div>
  );
};

// 地图·路线叙事：抽象地图网格上，分镜作为站点依次点亮并连线
export const MapStoryComposition: React.FC<TalkingHeadProps> = ({
  title,
  scenes,
  audio,
  audioSegments,
  captions,
  appearance,
}) => {
  const theme = useTheme(appearance);
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const points = scenes.map((scene, index) => ({
    scene,
    x: 180 + (index % 2) * 480 + (index % 3) * 120,
    y: 480 + index * Math.min(220, 900 / Math.max(1, scenes.length)),
  }));
  const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const draw = interpolate(frame, [0, Math.max(1, durationInFrames - fps)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div style={{position: "absolute", inset: 0, fontFamily}}>
      <Backdrop theme={theme} grid={false} />
      <Narration audio={audio} audioSegments={audioSegments} />
      <svg style={{position: "absolute", inset: 0}} viewBox="0 0 1080 1920">
        <defs>
          <pattern id="map-grid" width="90" height="90" patternUnits="userSpaceOnUse">
            <path d="M 90 0 L 0 0 0 90" fill="none" stroke={theme.textColor} strokeOpacity="0.08" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="1080" height="1920" fill="url(#map-grid)" />
        <path d={path} fill="none" stroke={theme.accentColor} strokeWidth="6" strokeDasharray="14 12" pathLength={1} strokeDashoffset={1 - draw} strokeLinecap="round" />
      </svg>
      {points.map((point) => {
        const active = frame >= Math.round(point.scene.start_seconds * fps);
        const scale = spring({frame: Math.max(0, frame - Math.round(point.scene.start_seconds * fps)), fps, config: {damping: 12}});
        return (
          <div
            key={point.scene.id}
            style={{
              position: "absolute",
              left: point.x - 26,
              top: point.y - 26,
              width: 52,
              height: 52,
              borderRadius: "50%",
              background: active ? theme.accentColor : theme.sceneLabelBackground,
              border: `4px solid ${theme.accentColor}`,
              transform: `scale(${active ? scale : 0.6})`,
              opacity: active ? 1 : 0.5,
            }}
          />
        );
      })}
      <SceneSequences scenes={scenes}>
        {(scene, index) => {
          const point = points[index];
          return (
            <div
              style={{
                position: "absolute",
                left: Math.min(point.x + 60, 560),
                top: point.y - 40,
                maxWidth: 420,
                padding: "20px 26px",
                borderRadius: 16,
                background: theme.titleBackground,
                color: theme.textColor,
                ...riseIn(frame, fps),
              }}
            >
              <div style={{color: theme.accentColor, fontSize: 24, letterSpacing: 2}}>
                第 {index + 1} 站
              </div>
              <div style={{fontSize: 38, fontWeight: 700, lineHeight: 1.4, marginTop: 8}}>{scene.name}</div>
              <div style={{fontSize: 28, opacity: 0.82, lineHeight: 1.55, marginTop: 8}}>{scene.description}</div>
            </div>
          );
        }}
      </SceneSequences>
      <HeaderCard eyebrow="路线叙事" title={title} theme={theme} />
      <CaptionLayer captions={captions} theme={theme} />
    </div>
  );
};
