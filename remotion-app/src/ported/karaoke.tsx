// Ported from AleBrito124356/remotion-video-templates (MIT License)
// https://github.com/AleBrito124356/remotion-video-templates
// Adapted to the shared TalkingHeadProps contract: sentence-level captions are
// split into per-character timings, Zod schemas replaced by the shared types,
// Google Fonts replaced by the system font stack.
import React from "react";
import {interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {Backdrop} from "../effects";
import {Narration} from "../narration";
import {useTheme} from "../templates";
import {TalkingHeadProps} from "../VideoComposition";

const fontFamily = "Arial, PingFang SC, Microsoft YaHei, sans-serif";

const SNAPPY = {mass: 0.6, stiffness: 180, damping: 20};

const withAlpha = (hex: string, alpha: number) => {
  const value = hex.replace("#", "");
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

type CaptionWord = {word: string; startMs: number; endMs: number};

const toWords = (captions: TalkingHeadProps["captions"]): CaptionWord[] => {
  const words: CaptionWord[] = [];
  for (const caption of captions) {
    const chars = Array.from(caption.text.trim()).filter((char) => char.trim());
    if (!chars.length) continue;
    const start = caption.startMs ?? 0;
    const end = caption.endMs ?? start + 500;
    const step = Math.max(60, (end - start) / chars.length);
    chars.forEach((char, index) => {
      words.push({word: char, startMs: start + index * step, endMs: Math.min(end, start + (index + 1) * step + 120)});
    });
  }
  return words;
};

const activeWordIndex = (captions: CaptionWord[], ms: number): number => {
  for (let i = 0; i < captions.length; i++) {
    if (ms >= captions[i].startMs && ms < captions[i].endMs) return i;
  }
  let held = -1;
  for (let i = 0; i < captions.length; i++) {
    if (ms >= captions[i].startMs) held = i;
  }
  return held;
};

export const KaraokeCaptionComposition: React.FC<TalkingHeadProps> = ({
  title,
  audio,
  audioSegments,
  captions,
  appearance,
}) => {
  const theme = useTheme(appearance);
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const words = toWords(captions);
  const ms = (frame / fps) * 1000;
  const totalMs = words.reduce((max, word) => Math.max(max, word.endMs), 1);
  const active = activeWordIndex(words, ms);
  const displayIndex = Math.max(0, active);
  const wordStartMs = words[displayIndex]?.startMs ?? 0;
  const localFrame = Math.max(0, frame - (wordStartMs / 1000) * fps);
  const pop = spring({frame: localFrame, fps, config: SNAPPY});
  const popScale = interpolate(pop, [0, 1], [0.7, 1]);
  const progress = Math.min(1, ms / totalMs);
  const wordsPerGroup = 6;
  const groupStart = Math.floor(displayIndex / wordsPerGroup) * wordsPerGroup;
  const visible = words.slice(groupStart, groupStart + wordsPerGroup);
  const barX = width * 0.06;
  const barW = width * 0.88;
  const barY = height * 0.86;
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        fontFamily,
      }}
    >
      <Backdrop theme={theme} grid={false} />
      <Narration audio={audio} audioSegments={audioSegments} />
      <div
        style={{
          position: "absolute",
          top: height * 0.08,
          left: 0,
          right: 0,
          textAlign: "center",
          fontWeight: 600,
          fontSize: 40,
          letterSpacing: 1,
          color: withAlpha("#ffffff", 0.7),
        }}
      >
        {title}
      </div>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          padding: `0 ${width * 0.06}px`,
        }}
      >
        <div style={{display: "flex", flexWrap: "wrap", justifyContent: "center", alignItems: "center", gap: 18}}>
          {visible.map((word, index) => {
            const globalIndex = groupStart + index;
            const isActive = globalIndex === active;
            return (
              <span
                key={globalIndex}
                style={{
                  fontWeight: 800,
                  fontSize: 104,
                  lineHeight: 1.05,
                  color: isActive ? theme.accentColor : "#ffffff",
                  transform: isActive ? `scale(${popScale})` : "scale(1)",
                  opacity: isActive ? 1 : 0.55,
                  textShadow: `0 6px 30px ${withAlpha("#000000", 0.55)}`,
                  display: "inline-block",
                }}
              >
                {word.word}
              </span>
            );
          })}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: barX,
          top: barY,
          width: barW,
          height: 10,
          borderRadius: 5,
          backgroundColor: withAlpha("#ffffff", 0.18),
          overflow: "hidden",
        }}
      >
        <div style={{width: `${progress * 100}%`, height: "100%", borderRadius: 5, backgroundColor: theme.accentColor}} />
      </div>
    </div>
  );
};
