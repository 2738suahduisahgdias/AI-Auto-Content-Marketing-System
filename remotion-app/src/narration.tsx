import {Audio} from "@remotion/media";
import React from "react";
import {Sequence, staticFile, useVideoConfig} from "remotion";

export type AudioSegment = {
  src: string;
  start_seconds: number;
  end_seconds: number;
  timeline_start_seconds: number;
};

const mediaSource = (src: string) => /^(https?:|data:|blob:)/.test(src) ? src : staticFile(src);

export const Narration: React.FC<{audio?: string; audioSegments?: AudioSegment[]; volume?: number}> = ({audio, audioSegments, volume = 1}) => {
  const {fps} = useVideoConfig();
  if (audioSegments?.length) {
    return <>
      {audioSegments.map((segment, index) => (
        <Sequence
          key={`${segment.timeline_start_seconds}-${index}`}
          from={Math.max(0, Math.round(segment.timeline_start_seconds * fps))}
          durationInFrames={Math.max(1, Math.round((segment.end_seconds - segment.start_seconds) * fps))}
          premountFor={fps}
          name={`口播片段 ${index + 1}`}
        >
          <Audio
            src={mediaSource(segment.src)}
            trimBefore={Math.max(0, Math.round(segment.start_seconds * fps))}
            durationInFrames={Math.max(1, Math.round((segment.end_seconds - segment.start_seconds) * fps))}
            premountFor={fps}
          />
        </Sequence>
      ))}
    </>;
  }
  return audio ? <Audio src={mediaSource(audio)} volume={volume} premountFor={fps} /> : null;
};
