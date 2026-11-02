import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
const run = promisify(execFile);
const bridge = fileURLToPath(new URL('../../workers/wechat_inbox_bridge.py', import.meta.url));
export async function handleInbound(event, ctx, deps = {}) {
  const env = deps.env || process.env;
  const channel = event.channel || ctx.channelId;
  const sender = event.senderId || ctx.senderId;
  if (channel !== 'openclaw-weixin' || !env.CONTENT_AGENT_WECHAT_SENDER_ID || sender !== env.CONTENT_AGENT_WECHAT_SENDER_ID || event.isGroup) return;
  const failed = { handled: true, text: '保存失败：本地工作台未确认入库，请启动客户端并重试；不要将此消息视为已保存。' };
  const msgid = event.messageId || ctx.messageId;
  if (!msgid || typeof event.content !== 'string' || !event.content.trim()) return failed;
  try {
    const payload = {msgid: 'openclaw-weixin:' + msgid, message_type: 'text', text: event.content};
    const {stdout} = await (deps.run || run)(bridge, [JSON.stringify(payload)], {env, timeout: 25000, maxBuffer: 256 * 1024});
    const result = JSON.parse(stdout.trim());
    if (['saved', 'duplicate'].includes(result.status) && result.id && result.ingest_status === 'saved')
      return {handled: true, text: '已保存到待分类'};
    return failed;
  } catch { return failed; }
}
