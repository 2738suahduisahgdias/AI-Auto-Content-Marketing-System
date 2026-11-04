// Pinned to the shipped Remotion renderer API; fail closed if interception is unavailable.
export function allowRenderRequest(raw,origin,depth=0){
 if(depth>2)return false;
 try{
  const u=new URL(raw);
  if(u.protocol==='data:')return true;
  if(u.protocol==='blob:')return u.origin===origin;
  if(u.origin!==origin||!['http:','https:'].includes(u.protocol))return false;
  if(u.pathname.startsWith('/proxy')){const src=u.searchParams.get('src');return Boolean(src)&&allowRenderRequest(src,origin,depth+1)}
  return true;
 }catch{return false}
}
export function isolateRenderBrowser(browser){
 const original=browser.newPage.bind(browser);
 browser.newPage=async(...args)=>{
  const page=await original(...args);const client=page._client();let origin='';
  client.on('Runtime.exceptionThrown', event => console.error('PAGE_EXCEPTION', JSON.stringify(event.exceptionDetails)));
  const goto=page.goto.bind(page);
  page.goto=async options=>{
   const target=new URL(options.url);
   if(!['127.0.0.1','localhost','[::1]'].includes(target.hostname))throw Error('Render entry must be local');
   origin=target.origin;
   return goto(options);
  };
  client.on('Fetch.requestPaused',event=>{
   const allowed=allowRenderRequest(event.request.url,origin);
   client.send(allowed?'Fetch.continueRequest':'Fetch.failRequest',allowed?{requestId:event.requestId}:{requestId:event.requestId,errorReason:'BlockedByClient'}).catch(()=>{});
  });
  await client.send('Network.enable');
  await client.send('Network.setBlockedURLs',{urls:['ws://*','wss://*','file://*']});
  await client.send('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
  return page;
 };
 return browser;
}
