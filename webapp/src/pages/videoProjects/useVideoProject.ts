import { useCallback, useEffect, useRef, useState } from "react";
import { api, jsonOptions } from "../../lib/api";
import type { Task } from "../../lib/types";
import { readContentDraft, writeContentDraft } from "../../lib/contentDraft";
import { useApp } from "../../AppContext";

export type ProjectType = "original" | "benchmark";

export interface ProjectFile {
  id: number;
  kind: string;
  original_name: string;
  url: string;
  download_url?: string;
  media_info: Record<string, any>;
}

export interface ProjectShot {
  id: string;
  title: string;
  text: string;
  desc: string;
  duration: number;
  source: string;
  fileId?: number;
  referenceFileId?: number;
  narrationFileId?: number;
  uploadedFileIds?: number[];
  aiCandidateFileIds?: number[];
  keyframe_file_id?: number;
  start_seconds?: number;
  end_seconds?: number;
  original_start_seconds?: number;
  original_end_seconds?: number;
  source_start_seconds?: number;
  visual_observation?: string;
  audio_source?: "original" | "replace" | "mute";
  confirmed?: boolean;
  duration_choice?: "original" | "new";
  trim_start?: number;
  fill_method?: "freeze" | "loop";
  [key: string]: any;
}

export interface ProjectSnapshot {
  workflow_stage: number;
  manuscript: { title: string; text: string; prompt?: string; versions?: { text: string; created_at?: string }[] };
  direction?: string;
  target_platforms?: string[];
  aspect?: string;
  usage_boundary?: string;
  voiceFileId?: number;
  voiceDuration?: number;
  transcript?: { words: { text: string; start: number; end: number }[]; status?: string };
  transcriptStale?: boolean;
  bgmFileId?: number;
  musicAdaptedFileId?: number;
  musicConfirmed?: boolean;
  musicConflict?: "original" | "replace" | "mix";
  musicConflictResolved?: boolean;
  musicDirection?: string;
  style?: string;
  previousStyle?: string;
  directorPlan?: Record<string, any>;
  shots: ProjectShot[];
  storyboardHistory?: ProjectShot[][];
  sampleFileId?: number;
  sampleFileIds?: number[];
  sampleApprovedFileId?: number;
  sampleApprovedFileIds?: number[];
  finalFileId?: number;
  finalApprovedFileId?: number;
  benchmark_report?: Record<string, any>;
  benchmark_notes?: string;
  transcript_runs?: number;
  [key: string]: any;
}

export const stageNames = {
  original: ["文案创作", "旁白与时长", "确定音乐", "生产画面", "合成验收"],
  benchmark: ["提供参考", "拆解报告", "逐镜替换", "替换音乐", "合成验收"],
} as const;

export function projectType(task?: Task): ProjectType {
  return task?.source?.project_type === "benchmark" ? "benchmark" : "original";
}

export function fileDuration(file?: ProjectFile) {
  const duration = Number(file?.media_info?.duration_seconds);
  return Number.isFinite(duration) && duration > 0 ? duration : undefined;
}

export function fileAudioPresent(file?: ProjectFile) {
  const streams = file?.media_info?.streams;
  return Array.isArray(streams) && streams.some(stream => stream.codec_type === "audio");
}

export function shotAvailableDuration(shot: ProjectShot, files: ProjectFile[]) {
  const file = files.find(item => item.id === shot.fileId);
  const duration = fileDuration(file);
  return duration === undefined ? undefined : Math.max(0, duration - Number(shot.trim_start || 0));
}

export function effectiveShotDuration(shot: ProjectShot, files: ProjectFile[]) {
  if (shot.duration_choice === "new") return shotAvailableDuration(shot, files);
  return Number(shot.duration);
}

export function shotReady(shot: ProjectShot, files: ProjectFile[]) {
  if (!shot.fileId || !shot.audio_source || !shot.duration_choice) return false;
  if (shot.audio_source === "replace" && !shot.narrationFileId) return false;
  const available = shotAvailableDuration(shot, files);
  const duration = effectiveShotDuration(shot, files);
  if (available === undefined || duration === undefined || !(duration > 0)) return false;
  if (shot.duration_choice === "original" && available + 0.05 < duration && !shot.fill_method) return false;
  return true;
}

export function sampleApproved(snapshot: ProjectSnapshot) {
  const sampleIds = snapshot.sampleFileIds?.length ? snapshot.sampleFileIds : snapshot.sampleFileId ? [snapshot.sampleFileId] : [];
  const approvedIds = snapshot.sampleApprovedFileIds?.length ? snapshot.sampleApprovedFileIds : snapshot.sampleApprovedFileId ? [snapshot.sampleApprovedFileId] : [];
  return sampleIds.length > 0 && sampleIds.every(id => approvedIds.includes(id));
}

export function useProjectTask(id?: string) {
  const { resources } = useApp();
  const listed = (resources?.core.tasks || []).find((item: Task) => item.content_id === id) as Task | undefined;
  const [loaded, setLoaded] = useState<Task>();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setLoaded(undefined);
    setFailed(false);
    if (!id || listed) return;
    let active = true;
    void api<Task>(`/api/tasks/${id}`).then(result => {
      if (active) setLoaded(result);
    }).catch(() => {
      if (active) setFailed(true);
    });
    return () => { active = false; };
  }, [id, listed]);
  return { task: listed || loaded, loading: Boolean(id && !listed && !loaded && !failed) };
}

export function initialSnapshot(task: Task): ProjectSnapshot {
  const current = task.source?.yingxu?.snapshot || {};
  return {
    workflow_stage: current.workflow_stage ?? 0,
    manuscript: current.manuscript || { title: task.title, text: task.scripts?.master || task.scripts?.douyin || "", versions: [] },
    direction: current.direction ?? task.source?.direction ?? "",
    target_platforms: current.target_platforms ?? task.source?.target_platforms ?? [],
    aspect: current.aspect ?? task.source?.aspect ?? "",
    usage_boundary: current.usage_boundary ?? task.source?.usage_boundary ?? "",
    format: current.format ?? ((current.aspect ?? task.source?.aspect) === "1920x1080" ? "1920 × 1080 · 横屏" : "1080 × 1920 · 竖屏"),
    rhythm: current.rhythm ?? "旁白驱动",
    shots: current.shots || [],
    ...current,
  };
}

export function useVideoProject(task: Task) {
  const { refresh } = useApp();
  const backupKey = `video-project:${task.content_id}`;
  const [snapshot, setSnapshot] = useState<ProjectSnapshot>(() => readContentDraft(backupKey, initialSnapshot(task)));
  const [revision, setRevision] = useState(Number(task.source?.yingxu?.revision || 0));
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const current = useRef(snapshot);
  const currentRevision = useRef(revision);
  current.current = snapshot;
  currentRevision.current = revision;

  const update = useCallback((patch: Partial<ProjectSnapshot> | ((value: ProjectSnapshot) => ProjectSnapshot)) => {
    setSnapshot(previous => {
      const next = typeof patch === "function" ? patch(previous) : { ...previous, ...patch };
      writeContentDraft(backupKey, next);
      return next;
    });
    setDirty(true);
  }, [backupKey]);

  const adoptTask = useCallback((result: Task) => {
    const next = initialSnapshot(result);
    const nextRevision = Number(result.source?.yingxu?.revision || 0);
    current.current = next;
    currentRevision.current = nextRevision;
    setSnapshot(next);
    setRevision(nextRevision);
    setDirty(false);
    writeContentDraft(backupKey, next);
  }, [backupKey]);

  const save = useCallback(async (override?: ProjectSnapshot) => {
    if (saving) throw new Error("正在保存，请稍后重试");
    setSaving(true);
    setMessage("");
    const pending = override || current.current;
    try {
      const result = await api<Task>(`/api/tasks/${task.content_id}/yingxu`, jsonOptions("PUT", {
        revision: currentRevision.current,
        snapshot: pending,
      }));
      const nextRevision = Number(result.source?.yingxu?.revision || currentRevision.current + 1);
      setRevision(nextRevision);
      currentRevision.current = nextRevision;
      current.current = pending;
      setSnapshot(pending);
      setDirty(false);
      setMessage(`已保存到原任务 · 版本 ${nextRevision}`);
      await refresh();
      return result;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
      throw error;
    } finally {
      setSaving(false);
    }
  }, [refresh, saving, task.content_id]);

  useEffect(() => {
    if (!dirty || saving) return;
    const timer = window.setTimeout(() => {
      void save().catch(() => undefined);
    }, 1400);
    return () => window.clearTimeout(timer);
  }, [snapshot, dirty, saving, save]);

  return { snapshot, update, adoptTask, save, saving, dirty, message, setMessage, revision };
}
