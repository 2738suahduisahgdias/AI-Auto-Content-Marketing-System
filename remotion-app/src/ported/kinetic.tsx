// Ported from AleBrito124356/remotion-video-templates (MIT License)
// https://github.com/AleBrito124356/remotion-video-templates
// KineticText adapted to the shared TalkingHeadProps contract: each scene shows
// its name as a per-character staggered kinetic line inside its own time window.
import React from "react";
import {interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {Backdrop, SceneFade} from "../effects";
import {Narration} from "../narration";
import {HeaderCard, SceneSequences, useTheme} from "../templates";
import {TalkingHeadProps, TalkingHeadScene} from "../VideoComposition";

const fontFamily = "Arial, PingFang SC, Microsoft YaHei, sans-serif";

const SNAPPY = {mass: 0.6, stiffness: 180, damping: 20};
const STAGGER = 4;

const KineticLine: React.FC<{
  text: string;
  emphasis: boolean;
  textColor: string;
  emphasisColor: string;
}> = ({text, emphasis, textColor, emphasisColor}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const chars = Array.from(text.trim()).filter((char) => char.trim());
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        gap: emphasis ? 16 : 12,
        maxWidth: "86%",
      }}
    >
      {chars.map((char, index) => {
        const enter = spring({frame, fps, config: SNAPPY, delay: index * STAGGER});
        const y = interpolate(enter, [0, 1], [46, 0]);
        const scale = emphasis ? interpolate(enter, [0, 1], [0.7, 1]) : interpolate(enter, [0, 1], [0.9, 1]);
        return (
          <span
            key={index}
            style={{
              fontFamily,
              fontWeight: emphasis ? 800 : 700,
              fontSize: emphasis ? 120 : 72,
              lineHeight: 1.1,
              color: emphasis ? emphasisColor : textColor,
              opacity: enter,
              transform: `translateY(${y}px) scale(${scale})`,
              display: "inline-block",
            }}
          >
            {char}
          </span>
        );
      })}
    </div>
  );
};

const KineticScene: React.FC<{
  scene: TalkingHeadScene;
  textColor: string;
  emphasisColor: string;
}> = ({scene, textColor, emphasisColor}) => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      alignItems: "center",
      gap: 46,
      padding: "240px 70px 400px",
    }}
  >
    <KineticLine text={scene.name} emphasis textColor={textColor} emphasisColor={emphasisColor} />
    {scene.description ? <KineticLine text={scene.description} emphasis={false} textColor={textColor} emphasisColor={emphasisColor} /> : null}
  </div>
);

export const KineticTextComposition: React.FC<TalkingHeadProps> = ({
  title,
  scenes,
  audio,
  audioSegments,
  appearance,
}) => {
  const theme = useTheme(appearance);
  return (
    <div style={{position: "absolute", inset: 0, fontFamily}}>
      <Backdrop theme={theme} />
      <Narration audio={audio} audioSegments={audioSegments} />
      <SceneSequences scenes={scenes}>
        {(scene) => (
          <SceneFade durationSeconds={scene.end_seconds - scene.start_seconds}>
            <KineticScene scene={scene} textColor={theme.textColor} emphasisColor={theme.accentColor} />
          </SceneFade>
        )}
      </SceneSequences>
      <HeaderCard eyebrow="观点陈述" title={title} theme={theme} />
    </div>
  );
};
