import { Badge, Field, Input, Textarea } from "@/components/ui";
import type { Json } from "@/lib/types";

interface Props {
  definition: Json;
  value: unknown;
  disabled: boolean;
  active: boolean;
  assetName?: string;
  error?: string;
  sourceId: string;
  onChange: (value: unknown) => void;
  onUpload: (file?: File) => void;
}

export function PlatformField({ definition, value, disabled, active, assetName, error, sourceId, onChange, onUpload }: Props) {
  const name = definition.name as string;
  const maximum = definition.max_length as number | null;
  const label = `${definition.label}${definition.required ? "（必填）" : ""}${maximum ? ` · 最多 ${maximum} 字` : ""}`;
  const meta = <div className="platform-field-meta"><Badge tone={definition.sync_status === "connected" ? "green" : "orange"}>{definition.sync_status === "connected" ? "已接入写入" : "仅保存，预览需接入"}</Badge>{definition.verification === "unverified" && <Badge tone="orange">限制待账号核验</Badge>}{definition.description && <p>{definition.description}</p>}{!active && <p>需先满足 {definition.depends_on?.field} = {String(definition.depends_on?.equals)}</p>}{error && <p className="platform-field-error" role="alert">{error}</p>}</div>;
  if (definition.control === "source") {
    return <div className="platform-source-field"><strong>{definition.label}</strong><span>{sourceId}</span>{meta}</div>;
  }
  const common = { disabled: disabled || !active, maxLength: maximum || undefined };
  if (definition.control === "boolean") {
    return <div className="platform-field"><div className="publishing-options"><label><input type="checkbox" checked={Boolean(value)} disabled={common.disabled} onChange={event => onChange(event.target.checked)} />{label} · {value ? "已开启" : "已关闭"}</label></div>{meta}</div>;
  }
  return <div className="platform-field">
    <Field label={label}>
      {definition.control === "select" ? <select value={String(value ?? "")} disabled={common.disabled} onChange={event => onChange(event.target.value)}><option value="">不设置</option>{definition.options.map((option: string) => <option key={option} value={option}>{option}</option>)}</select>
        : definition.control === "datetime" ? <Input type="datetime-local" value={String(value ?? "")} disabled={common.disabled} onChange={event => onChange(event.target.value)} />
        : definition.control === "asset" ? <><Input type="file" accept=".png,.jpg,.jpeg,.webp" disabled={common.disabled} onChange={event => onUpload(event.target.files?.[0])} /><span className={`publishing-cover-name${definition.required && !value ? " is-missing" : ""}`}>{assetName || (value ? "已关联图片资产" : definition.required ? "尚未上传图片" : "未设置图片")}</span></>
        : ["textarea", "json"].includes(definition.control) ? <Textarea className={["body", "description"].includes(name) ? "publishing-body" : ""} value={String(value ?? "")} disabled={common.disabled} maxLength={common.maxLength} onChange={event => onChange(event.target.value)} />
        : <Input type={definition.control === "url" ? "url" : "text"} value={String(value ?? "")} disabled={common.disabled} maxLength={common.maxLength} onChange={event => onChange(event.target.value)} />}
    </Field>
    {meta}
  </div>;
}
