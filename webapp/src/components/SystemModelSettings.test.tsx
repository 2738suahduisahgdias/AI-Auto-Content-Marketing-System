import {render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {beforeEach, expect, it, vi} from "vitest";
import SystemModelSettings from "./SystemModelSettings";
const request = vi.hoisted(()=>vi.fn());
vi.mock("@/lib/api",()=>({
  api:request,
  errorText:(e:Error)=>e.message,
  jsonOptions:(method:string,payload:unknown)=>({method,body:JSON.stringify(payload)}),
}));
beforeEach(()=>{
  request.mockReset();
  request.mockImplementation(async(path:string,options?:RequestInit)=>{
    if(path.endsWith("/test")) return {ok:true,engine:"model_api"};
    if(options?.method==="PUT") return {...JSON.parse(String(options.body)),key_configured:true};
    return {engine:"codex_cli"};
  });
});
it("saves the actual global provider and tests the saved API configuration",async()=>{
  const user=userEvent.setup();
  render(<SystemModelSettings/>);
  await waitFor(()=>expect(request).toHaveBeenCalledWith("/api/agents/system-model"));
  await user.selectOptions(screen.getByRole("combobox"),"kimi_cli");
  await user.click(screen.getByRole("button",{name:"保存默认模型"}));
  await waitFor(()=>expect(request).toHaveBeenCalledWith("/api/agents/system-model",expect.objectContaining({body:expect.stringContaining('"engine":"kimi_cli"')})));
  await user.selectOptions(screen.getByRole("combobox"),"model_api");
  await user.type(screen.getByPlaceholderText("https://服务地址/v1"),"https://example.test/v1");
  await user.type(screen.getByLabelText("模型名称"),"api-model");
  await user.type(screen.getByLabelText("API Key"),"local-test-key");
  await user.click(screen.getByRole("button",{name:"保存并测试连接"}));
  await screen.findByText("连接测试通过 · model_api");
  expect(request).toHaveBeenCalledWith("/api/agents/system-model",expect.objectContaining({body:expect.stringContaining('"model":"api-model"')}));
  expect(request).toHaveBeenCalledWith("/api/agents/system-model/test",expect.anything());
});
