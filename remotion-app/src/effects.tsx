// 共享视觉特效层：动态背景、场景媒体（Ken Burns/视频）、场景淡入淡出。
// 散景光斑参考 reactvideoeditor/remotion-templates 的 bokeh-circles（MIT），
// 改为按模板主题色取色。
import {Video} from "@remotion/media";
import React from "react";
import {CanvasImage, interpolate, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {TalkingHeadAppearance, TalkingHeadScene} from "./VideoComposition";

const hexToRgb = (value: string, fallback: [number, number, number]): [number, number, number] => {
  const match = /^#([0-9a-f]{6})$/i.exec(value.trim());
  if (!match) return fallback;
  const raw = match[1];
  return [parseInt(raw.slice(0, 2), 16), parseInt(raw.slice(2, 4), 16), parseInt(raw.slice(4, 6), 16)];
};

const rgba = ([r, g, b]: [number, number, number], alpha: number) => `rgba(${r}, ${g}, ${b}, ${alpha})`;

// 动态散景 + 光带扫过 + 细网格，全部按模板主题色生成，不依赖任何外部素材。
export const Backdrop: React.FC<{theme: TalkingHeadAppearance; grid?: boolean}> = ({theme, grid = true}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const accent = hexToRgb(theme.accentColor, [215, 242, 119]);
  const text = hexToRgb(theme.textColor, [245, 248, 243]);
  const orbs = Array.from({length: 10}, (_, index) => {
    const baseX = ((index * 173 + 53) % 100) / 100;
    const baseY = ((index * 241 + 97) % 100) / 100;
    const x = baseX * width + Math.sin(t * 0.25 + index * 1.3) * 60;
    const y = baseY * height + Math.cos(t * 0.18 + index * 0.9) * 50;
    const size = (140 + ((index * 37 + 11) % 220)) * (Math.sin(t * 0.4 + index * 0.7) * 0.15 + 1);
    const rgb = index % 3 === 2 ? text : accent;
    const opacity = 0.06 + ((index * 19 + 7) % 14) / 100;
    return {x, y, size, rgb, opacity, key: index};
  });
  const sweep = (t * 120) % (width * 2.4) - width * 0.7;
  return (
    <div style={{position: "absolute", inset: 0, overflow: "hidden", background: theme.background}}>
      {grid ? (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: `linear-gradient(${rgba(text, 0.045)} 1px, transparent 1px), linear-gradient(90deg, ${rgba(text, 0.045)} 1px, transparent 1px)`,
            backgroundSize: "84px 84px",
          }}
        />
      ) : null}
      {orbs.map((orb) => (
        <div
          key={orb.key}
          style={{
            position: "absolute",
            left: orb.x - orb.size / 2,
            top: orb.y - orb.size / 2,
            width: orb.size,
            height: orb.size,
            borderRadius: "50%",
            background: `radial-gradient(circle, ${rgba(orb.rgb, orb.opacity)} 0%, transparent 68%)`,
          }}
        />
      ))}
      <div
        style={{
          position: "absolute",
          top: -height * 0.2,
          left: sweep,
          width: width * 0.45,
          height: height * 1.4,
          transform: "rotate(18deg)",
          background: `linear-gradient(90deg, transparent 0%, ${rgba(accent, 0.05)} 50%, transparent 100%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at 50% 42%, transparent 55%, ${rgba([0, 0, 0], 0.22)} 100%)`,
        }}
      />
    </div>
  );
};

// 场景级淡入淡出：进入 12 帧、结束前保留 0.15 透明度，避免场景间黑闪。
export const SceneFade: React.FC<{durationSeconds: number; children: React.ReactNode}> = ({durationSeconds, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const total = Math.max(1, Math.round(durationSeconds * fps));
  const opacity = interpolate(frame, [0, Math.min(12, total / 4), Math.max(0, total - 10), total], [0, 1, 1, 0.15], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return <div style={{position: "absolute", inset: 0, opacity}}>{children}</div>;
};

const mediaSource = (src: string) => (/^(https?:|data:|blob:)/.test(src) ? src : staticFile(src));

// 场景媒体：视频直接铺满播放；图片使用 Ken Burns 缓慢推拉。
export const SceneMedia: React.FC<{scene: TalkingHeadScene; opacity?: number}> = ({scene, opacity = 1}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (scene.media?.kind === "video") {
    return (
      <Video
        name={scene.name}
        src={mediaSource(scene.media.src)}
        trimBefore={Math.max(0, Math.round((scene.source_start_seconds || 0) * fps))}
        premountFor={fps}
        objectFit="cover"
        style={{position: "absolute", width: "100%", height: "100%", opacity}}
      />
    );
  }
  if (scene.media?.kind === "image") {
    const total = Math.max(1, Math.round((scene.end_seconds - scene.start_seconds) * fps));
    const scale = interpolate(frame, [0, total], [1.02, 1.14], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
    const moveX = interpolate(frame, [0, total], [-14, 14], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
    return (
      <CanvasImage
        name={scene.name}
        src={mediaSource(scene.media.src)}
        premountFor={fps}
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity,
          scale,
          translate: `${moveX}px 0px`,
        }}
      />
    );
  }
  return null;
};
