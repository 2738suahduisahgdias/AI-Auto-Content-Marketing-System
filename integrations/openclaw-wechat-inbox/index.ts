import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { handleInbound } from "./handler.mjs";
export default definePluginEntry({
  id: "yingxu-wechat-inbox", name: "Yingxu local WeChat inbox",
  register(api) { api.on("before_dispatch", handleInbound, { priority: 100 }); }
});
