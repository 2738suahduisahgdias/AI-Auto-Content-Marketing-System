import { CalculateMetadataFunction, Composition } from "remotion";
import { MyComposition } from "./Composition";
import { TalkingHeadProps, VideoComposition } from "./VideoComposition";

const calculateMetadata: CalculateMetadataFunction<TalkingHeadProps> = ({ props }) => {
  return {
    durationInFrames: Math.max(1, Math.ceil(props.durationSeconds * 30)),
  };
};

const studioProps: TalkingHeadProps = {
  title: "真实任务，完整交付",
  durationSeconds: 6,
  scenes: [
    {
      id: "studio-1",
      name: "镜头01 真实任务",
      start_seconds: 0,
      end_seconds: 3,
      asset_type: "own",
      description: "先选一个真实业务任务，而不是堆砌 AI 概念",
    },
    {
      id: "studio-2",
      name: "镜头02 人工验收",
      start_seconds: 3,
      end_seconds: 6,
      asset_type: "screen_record",
      description: "过程可检查，结果由人确认",
    },
  ],
  captions: [
    { text: "先选一个真实业务任务", startMs: 0, endMs: 2800, timestampMs: null, confidence: null },
    { text: "过程可检查，结果由人确认", startMs: 3000, endMs: 5800, timestampMs: null, confidence: null },
  ],
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <MyComposition />
      <Composition
        id="TalkingHead"
        component={VideoComposition}
        durationInFrames={180}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={studioProps}
        calculateMetadata={calculateMetadata}
      />
    </>
  );
};
