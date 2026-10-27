import type {Caption} from '@remotion/captions';
import React from 'react';
import {
	Interactive,
	useCurrentFrame,
	useVideoConfig,
	type InteractiveTransformProps,
	type InteractivitySchema,
	type SequenceProps,
} from 'remotion';

type BasicCaptionsProps = InteractiveTransformProps &
	Pick<SequenceProps, 'width'> & {
		readonly captions: Caption[];
	};

const defaultWidth = 900;

const basicCaptionsSchema = {
	...Interactive.captionsSchema,
	width: {
		type: 'number',
		min: 1,
		step: 1,
		default: undefined,
		description: 'Caption area width',
		hiddenFromList: false,
	},
} as const satisfies InteractivitySchema;

const BasicCaptionsContent: React.FC<BasicCaptionsProps> = ({
	captions,
	style,
	width = defaultWidth,
}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const currentTimeMs = (frame / fps) * 1000;
	const page = captions.find(
		(candidate) =>
			currentTimeMs >= candidate.startMs &&
			currentTimeMs < candidate.endMs,
	);

	return (
		<div
			style={{
				alignItems: 'center',
				display: 'flex',
				justifyContent: 'center',
				width,
				...style,
			}}
		>
			{page ? (
				<div
					style={{
						backgroundColor: 'rgba(64, 64, 64, 0.75)',
						color: '#ffffff',
						fontFamily: 'Arial, Helvetica, sans-serif',
						fontSize: 42,
						fontWeight: 400,
						lineHeight: 1.35,
							maxWidth: 860,
						padding: '14px 22px',
						textAlign: 'center',
						textWrap: 'balance',
						whiteSpace: 'pre-wrap',
					}}
				>
					{page.text.trim()}
				</div>
			) : null}
		</div>
	);
};

export const BasicCaptions = Interactive.create({
	Component: BasicCaptionsContent,
	componentName: '<BasicCaptions>',
	schema: basicCaptionsSchema,
});
