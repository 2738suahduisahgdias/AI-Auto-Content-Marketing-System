import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button, Modal } from "@/components/ui";
import { api } from "@/lib/api";

export function SetupPrompt() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (window.localStorage.getItem("content-agent-setup-dismissed")) return;
    let active = true;
    api<{ first_run: boolean }>("/api/accounts/setup").then(data => {
      if (active && data.first_run) setOpen(true);
    }).catch(() => undefined);
    return () => { active = false; };
  }, []);
  function dismiss() {
    window.localStorage.setItem("content-agent-setup-dismissed", "1");
    setOpen(false);
  }
  return <Modal open={open} onOpenChange={next => { if (!next) dismiss(); }} title="先完成首次接入" description="基础工作台已经可以访问。按向导检查本机环境，再登录需要使用的平台。"><div className="setup-prompt"><p>你不需要一次配置所有 AI 能力。建议先启动基础环境，再逐个完成抖音、小红书、视频号或公众号登录。</p><ul><li>检查 macOS 或 Windows 依赖</li><li>本人完成扫码、短信和二次验证</li><li>账号凭据只保留在本机，不上传 GitHub</li></ul><div className="button-row"><Button onClick={dismiss}>稍后设置</Button><Link className="button button-primary" to="/setup" onClick={dismiss}>进入接入向导</Link></div></div></Modal>;
}
