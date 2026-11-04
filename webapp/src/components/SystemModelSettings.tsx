import {useEffect, useState} from "react";
import {api, errorText, jsonOptions} from "@/lib/api";
import {Button, Card, Field, Input, ErrorBox} from "@/components/ui";

interface ModelSettings {
  engine: string;
  base_url?: string;
  model?: string;
  key_configured?: boolean;
}
export default function SystemModelSettings() {
  const [settings,setSettings] = useState<ModelSettings>({engine:"codex_cli"});
  const [key,setKey] = useState("");
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [message,setMessage] = useState("");
  useEffect(()=>{api<ModelSettings>("/api/agents/system-model").then(setSettings).catch(e=>setError(errorText(e)));},[]);
  async function save(test = false) {
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await api<ModelSettings>("/api/agents/system-model",jsonOptions("PUT",{...settings,...(key?{api_key:key}:{})}));
      setSettings(saved); setKey("");
      if (test) {
        const result = await api<{engine:string}>("/api/agents/system-model/test",jsonOptions("POST"));
        setMessage("连接测试通过 · "+result.engine);
      } else setMessage("已保存，跟随系统的 Agent 将在下次执行时使用所选服务。");
    } catch(e) {setError(errorText(e));}
    finally {setBusy(false);}
  }
  return <Card>
    <h2>系统默认文本模型</h2>
    <p>选题推荐、文案、编导、素材规划、内容审核和发布文案统一跟随此处选择。Agent 配置中可单独指定服务；配音、生图、视频生成和本地渲染使用各自能力。</p>
    <Field label="默认服务"><select disabled={busy} value={settings.engine} onChange={e=>{setSettings({...settings,engine:e.target.value});setMessage("");}}>
      <option value="codex_cli">Codex CLI · 本机登录</option>
      <option value="kimi_cli">Kimi CLI · 本机登录</option>
      <option value="model_api">模型 API · OpenAI 兼容接口</option>
    </select></Field>
    {settings.engine==="model_api" && <>
      <Field label="API 基础地址"><Input value={settings.base_url||""} placeholder="https://服务地址/v1" onChange={e=>setSettings({...settings,base_url:e.target.value})}/></Field>
      <Field label="模型名称"><Input value={settings.model||""} onChange={e=>setSettings({...settings,model:e.target.value})}/></Field>
      <Field label="API Key"><Input type="password" autoComplete="new-password" value={key} placeholder={settings.key_configured?"已保存，留空保留":"填写服务商密钥，本地无密钥服务可留空"} onChange={e=>setKey(e.target.value)}/></Field>
    </>}
    <p>CLI 需要在当前电脑安装并登录。远程 API 使用自己的密钥与额度。这里配置的是文本接口。</p>
    {error && <ErrorBox>{error}</ErrorBox>}
    {message && <p role="status">{message}</p>}
    <Button disabled={busy} onClick={()=>save()}>保存默认模型</Button>{" "}
    <Button disabled={busy} onClick={()=>save(true)}>{busy?"正在连接…":"保存并测试连接"}</Button>
  </Card>;
}
