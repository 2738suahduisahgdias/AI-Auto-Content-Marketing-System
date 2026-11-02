import type {Caption} from "@remotion/captions";
import React from "react";
import {Sequence, useVideoConfig} from "remotion";
import {BasicCaptions} from "./basic-captions";
import {SmartScene} from "./content";
import {SceneFade} from "./effects";
import {Narration, type AudioSegment} from "./narration";

export type TalkingHeadScene = {
  id: string;
  name: string;
  start_seconds: number;
  end_seconds: number;
  asset_type: "own" | "screen_record" | "stock" | "ai_image" | "ai_video";
  description: string;
  media?: {kind: "video" | "image"; src: string} | null;
  type?: "hook" | "key_point" | "metric" | "process" | "comparison" | "timeline" | "architecture" | "map" | "media" | "quote" | "cta";
  narration?: string;
  headline?: string;
  keywords?: string[];
  locations?: string[];
  data?: {metric?: {value: number; unit: string; direction: "up" | "down"} | null; items: string[]};
  visualBeats?: {at: number; offset_seconds: number; action: string}[];
  source_start_seconds?: number;
  source_end_seconds?: number;
};

export type TalkingHeadAppearance = {
  background: string;
  sceneBackground: string;
  textColor: string;
  accentColor: string;
  titleBackground: string;
  sceneLabelBackground: string;
  captionBackground: string;
  captionColor: string;
  eyebrow?: string;
  variant?: "founder" | "enterprise" | "tech" | "warm" | "promo" | "map";
};

export type TalkingHeadProps = {
  title: string;
  scenes: TalkingHeadScene[];
  audio?: string;
  backgroundMusic?: string;
  backgroundMusicSegments?: AudioSegment[];
  outputWidth?: number;
  outputHeight?: number;
  audioSegments?: AudioSegment[];
  captions: Caption[];
  durationSeconds: number;
  appearance?: Partial<TalkingHeadAppearance>;
  preview?: boolean;
  presentationMode?: "legacy" | "project";
  sceneRenderer?: React.ComponentType<{scene: TalkingHeadScene; appearance: TalkingHeadAppearance}>;
  storyboard?: {schema_version: string; engine_version: string; seed: number};
};

const defaultAppearance: TalkingHeadAppearance = {
  background: "#10251e",
  sceneBackground: "linear-gradient(145deg, #173d2e 0%, #0c1f19 70%)",
  textColor: "#f5f8f3",
  accentColor: "#d7f277",
  titleBackground: "rgba(9, 27, 21, 0.84)",
  sceneLabelBackground: "rgba(8, 25, 19, 0.76)",
  captionBackground: "rgba(64, 64, 64, 0.75)",
  captionColor: "#ffffff",
};

const SceneLayer: React.FC<{scene: TalkingHeadScene; appearance: TalkingHeadAppearance; renderer?: TalkingHeadProps["sceneRenderer"]}> = ({scene, appearance, renderer: Renderer}) => (
  <div style={{position: "absolute", inset: 0, background: appearance.background}}>
    {Renderer && !scene.media ? <Renderer scene={scene} appearance={appearance}/> : <SmartScene scene={scene} theme={appearance} />}
  </div>
);

export const VideoComposition: React.FC<TalkingHeadProps> = ({
  title,
  scenes,
  audio,
  audioSegments,
  backgroundMusic,
  backgroundMusicSegments,
  captions,
  appearance,
  sceneRenderer,
  presentationMode = "legacy",
}) => {
  const {fps, width, height} = useVideoConfig();
  const theme = {...defaultAppearance, ...appearance};
  return (
    <div style={{position: "absolute", inset: 0, background: theme.background}}>
      <Narration audio={audio} audioSegments={audioSegments} />
      <Narration audio={backgroundMusic} audioSegments={backgroundMusicSegments} volume={0.18} />
      {scenes.map((scene) => (
        <Sequence
          key={scene.id}
          name={scene.name}
          from={Math.max(0, Math.round(scene.start_seconds * fps))}
          durationInFrames={Math.max(1, Math.round((scene.end_seconds - scene.start_seconds) * fps))}
          premountFor={fps}
        >
          {(presentationMode === "project" || (sceneRenderer && !scene.media)) ? <SceneLayer scene={scene} appearance={theme} renderer={sceneRenderer}/> :
          <SceneFade durationSeconds={scene.end_seconds - scene.start_seconds}>
            <SceneLayer scene={scene} appearance={theme} renderer={sceneRenderer} />
          </SceneFade>}
        </Sequence>
      ))}
      {presentationMode !== "project" && !sceneRenderer && <div
        style={{
          position: "absolute",
          top: 86,
          left: 70,
          right: 70,
          padding: "26px 30px",
          borderRadius: 20,
          background: theme.titleBackground,
          color: theme.textColor,
          fontFamily: "Arial, PingFang SC, Microsoft YaHei, sans-serif",
        }}
      >
        <div style={{color: theme.accentColor, fontSize: 26, letterSpacing: 3, marginBottom: 12}}>
          {theme.eyebrow || "AI 落地实战"}
        </div>
        <div style={{fontSize: 44, fontWeight: 700, lineHeight: 1.35, textWrap: "balance", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden"}}>
          {title}
        </div>
      </div>}
      <BasicCaptions
        width={Math.min(width - 80, 1200)}
        style={{position: "absolute", bottom: Math.round(height * 0.06), left:"50%", transform:"translateX(-50%)"}}
        captions={captions}
        captionBackground={theme.captionBackground}
        captionColor={theme.captionColor}
      />
    </div>
  );
};
