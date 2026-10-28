import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { AlertCircle, LoaderCircle, X } from "lucide-react";
import { twMerge } from "tailwind-merge";
import { clsx } from "clsx";

export const cn = (...values: Parameters<typeof clsx>) => twMerge(clsx(...values));

export function Button({ className, variant = "default", size = "default", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "danger" | "ghost"; size?: "default" | "small" }) {
  return <button className={cn("button", `button-${variant}`, size === "small" && "button-small", className)} {...props} />;
}

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cn("card", className)} {...props} />;
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "green" | "orange" | "red" | "blue" }) {
  return <span className={cn("badge", `badge-${tone}`)}>{children}</span>;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="field"><span className="field-label">{label}</span>{children}{hint && <small>{hint}</small>}</label>;
}

export const Input = ({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) => <input className={cn("input", className)} {...props} />;
export const Textarea = ({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea className={cn("textarea", className)} {...props} />;

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode }) {
  return <header className="page-header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description && <p className="page-description">{description}</p>}</div>{actions && <div className="page-actions">{actions}</div>}</header>;
}

export function Empty({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <div className="empty"><strong>{title}</strong>{description && <p>{description}</p>}{action}</div>;
}

export function ErrorBox({ children }: { children: ReactNode }) {
  return <div className="error-box" role="alert"><AlertCircle size={18} /><div>{children}</div></div>;
}

export function Busy({ label = "正在读取真实数据…" }: { label?: string }) {
  return <div className="busy"><LoaderCircle className="spin" size={18} />{label}</div>;
}

export function Modal({ open, onOpenChange, title, description, children, wide = false }: { open: boolean; onOpenChange: (open: boolean) => void; title: string; description?: string; children: ReactNode; wide?: boolean }) {
  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="modal-overlay" /><Dialog.Content className={cn("modal", wide && "modal-wide")}><div className="modal-head"><div><Dialog.Title>{title}</Dialog.Title>{description && <Dialog.Description>{description}</Dialog.Description>}</div><Dialog.Close className="icon-button" aria-label="关闭"><X size={18} /></Dialog.Close></div><div className="modal-body">{children}</div></Dialog.Content></Dialog.Portal></Dialog.Root>;
}

export function Progress({ value }: { value: number }) {
  return <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value * 100)}><span style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }} /></div>;
}
