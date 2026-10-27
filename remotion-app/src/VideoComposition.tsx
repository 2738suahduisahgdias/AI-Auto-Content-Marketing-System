import type {Caption} from "@remotion/captions";
import {Audio, Video} from "@remotion/media";
import React from "react";
import {
  CanvasImage,
  Easing,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {BasicCaptions} from "./basic-captions";

export type TalkingHeadScene = {
  id: string;
  name: string;
  start_seconds: number;
  end_seconds: number;
  asset_type: "own" | "screen_record" | "stock" | "ai_image" | "ai_video";
  description: string;
  media?: {kind: "video" | "image"; src: string} | null;
};

export type TalkingHeadProps = {
  title: string;
  scenes: TalkingHeadScene[];
  audio?: string;
  captions: Caption[];
  durationSeconds: number;
};

const SceneLayer: React.FC<{scene: TalkingHeadScene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const opacity = interpolate(frame, [0, Math.max(1, fps / 2)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const scale = interpolate(frame, [0, 4 * fps], [1, 1.035], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    output: "perceptual-scale",
  });
  const mediaStyle: React.CSSProperties = {
    position: "absolute",
    width: "100%",
    height: "100%",
    opacity,
    scale,
  };

  return (
    <div style={{position: "absolute", inset: 0, background: "#10251e"}}>
      {scene.media?.kind === "video" ? (
        <Video
          name={scene.name}
          src={staticFile(scene.media.src)}
          premountFor={fps}
          objectFit="cover"
          style={mediaStyle}
        />
      ) : scene.media?.kind === "image" ? (
        <CanvasImage
          name={scene.name}
          src={staticFile(scene.media.src)}
          premountFor={fps}
          style={{...mediaStyle, objectFit: "cover"}}
        />
      ) : (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "210px 100px 430px",
            background: "linear-gradient(145deg, #173d2e 0%, #0c1f19 70%)",
            opacity,
          }}
        >
          <div
            style={{
              color: "#f3f8ed",
              fontFamily: "Arial, PingFang SC, Microsoft YaHei, sans-serif",
              fontSize: 58,
              fontWeight: 650,
              lineHeight: 1.45,
              textAlign: "center",
              textWrap: "balance",
              display: "-webkit-box",
              WebkitLineClamp: 4,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {scene.description || scene.name}
          </div>
        </div>
      )}
      <div
        style={{
          position: "absolute",
          left: 70,
          right: 70,
          bottom: 330,
          padding: "22px 28px",
          background: "rgba(8, 25, 19, 0.76)",
          borderLeft: "8px solid #d7f277",
          color: "#f4f7f2",
          fontFamily: "Arial, PingFang SC, Microsoft YaHei, sans-serif",
          fontSize: 34,
          lineHeight: 1.4,
        }}
      >
        {scene.name}
      </div>
    </div>
  );
};

export const VideoComposition: React.FC<TalkingHeadProps> = ({
  title,
  scenes,
  audio,
  captions,
}) => {
  const {fps} = useVideoConfig();
  return (
    <div style={{position: "absolute", inset: 0, background: "#10251e"}}>
      {audio ? <Audio src={staticFile(audio)} premountFor={fps} /> : null}
      {scenes.map((scene) => (
        <Sequence
          key={scene.id}
          name={scene.name}
          from={Math.max(0, Math.round(scene.start_seconds * fps))}
          durationInFrames={Math.max(1, Math.round((scene.end_seconds - scene.start_seconds) * fps))}
          premountFor={fps}
        >
          <SceneLayer scene={scene} />
        </Sequence>
      ))}
      <div
        style={{
          position: "absolute",
          top: 86,
          left: 70,
          right: 70,
          padding: "26px 30px",
          borderRadius: 20,
          background: "rgba(9, 27, 21, 0.84)",
          color: "#f5f8f3",
          fontFamily: "Arial, PingFang SC, Microsoft YaHei, sans-serif",
        }}
      >
        <div style={{color: "#d7f277", fontSize: 26, letterSpacing: 3, marginBottom: 12}}>
          AI 落地实战
        </div>
        <div style={{fontSize: 44, fontWeight: 700, lineHeight: 1.35, textWrap: "balance", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden"}}>
          {title}
        </div>
      </div>
      <BasicCaptions
        width={900}
        style={{position: "absolute", bottom: 150, translate: "90px 0px"}}
        captions={captions}
      />
    </div>
  );
};
