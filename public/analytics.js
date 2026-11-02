'use strict';
(()=>{
 if(window.neuroAnalytics)return;
 const counter=114024456;
 const paths=new Set(['/','/index.php','/services.php','/catalog.php','/portfolio.php','/reviews.php','/portfolio-case.php','/privacy.php','/consent.php','/sitemap.php']);
 const settingsPage=location.pathname==='/analytics.php';
 if(!paths.has(location.pathname)&&!settingsPage)return;
 const query=new URLSearchParams(location.search),allowed=location.pathname==='/services.php'?['service']:['case'];
 if(!settingsPage&&Array.from(query).some(([k,v])=>!allowed.includes(k)||!/^[a-z0-9_-]{1,120}$/.test(v)))return;
 let localDenied=false;
 function optedOut(){return localDenied||document.cookie.split(';').some(x=>x.trim()==='neuro_analytics_block=1')||status?.choice==='deny';}
 function eraseMetrikaCookies(){for(const entry of document.cookie.split(';')){const name=entry.trim().split('=')[0];if(!/^_ym_/.test(name))continue;for(const domain of ['',location.hostname,'.'+location.hostname])document.cookie=name+'=; Max-Age=0; Path=/'+(domain?'; Domain='+domain:'')+'; SameSite=Lax'+(location.protocol==='https:'?'; Secure':'');}}
 function cleanUrl(value){try{const u=new URL(value,location.origin);return ['http:','https:'].includes(u.protocol)?u.origin+u.pathname:'';}catch{return '';}}
 function mask(root=document){
  for(const node of root.querySelectorAll('form,input,textarea,select,[contenteditable],#brief,#brief-result,#ai-chat')){node.classList.add('ym-hide-content','ym-disable-keys','ym-disable-clickmap');if(node.tagName==='FORM')node.classList.add('ym-disable-submit');}
  for(const a of root.querySelectorAll('a[href]')){try{const u=new URL(a.href,location.origin);if(u.search||['mailto:','tel:'].includes(u.protocol))a.classList.add('ym-disable-tracklink','ym-hide-content','ym-disable-clickmap');}catch{a.classList.add('ym-disable-tracklink');}}
 }
 let running=false,starting=false,sdkLoaded=false,status=null,observer=null,barrier=false;const workers=new Set(),sockets=new Set();
 function privateUrl(value){try{const u=new URL(value,location.origin);if(!paths.has(u.pathname))return true;const keys=u.pathname==='/services.php'?['service']:['case'];if(Array.from(u.searchParams).some(([k,v])=>!keys.includes(k)||!/^[a-z0-9_-]{1,120}$/.test(v)))return true;return !!u.hash&&!['#services','#process','#faq','#contact','#brief','#guide-contact','#'].includes(u.hash);}catch{return true;}}
 function safeReferrer(){try{const u=new URL(document.referrer);if(u.origin!==location.origin)return u.origin+'/';return privateUrl(u.href)?'':cleanUrl(u.href);}catch{return '';}}
 function restrictAnalytics(){if(barrier)return;barrier=true;const meta=document.createElement('meta');meta.httpEquiv='Content-Security-Policy';meta.content="connect-src 'self'; img-src 'self' data:; script-src 'self'; worker-src 'none'; child-src 'self'";document.head.append(meta);for(const w of workers)w.terminate();for(const s of sockets)s.close();workers.clear();sockets.clear();}
 function guardWorkers(){if(window.Worker){const Original=window.Worker;window.Worker=new Proxy(Original,{construct(target,args){const w=Reflect.construct(target,args);if(running&&(String(args[0]).startsWith('blob:')||/mc\.yandex\./.test(String(args[0]))))workers.add(w);return w;}});}if(window.WebSocket){const Original=window.WebSocket;window.WebSocket=new Proxy(Original,{construct(target,args){const socket=Reflect.construct(target,args);if(/mc\.yandex\./.test(String(args[0])))sockets.add(socket);return socket;}});}}
 async function eligible(){try{const r=await fetch('/analytics-status.php',{credentials:'same-origin',cache:'no-store'});if(!r.ok)return null;return await r.json();}catch{return null;}}
 async function start(){
  if(running||starting||settingsPage||privateUrl(location.href)||optedOut())return;starting=true;try{
  // Recheck on the same origin: Strict session cookies may have been absent on the initial external navigation.
  status=await eligible();if(!status?.approved||!status.eligible||status.counter!==counter||optedOut()||barrier)return;
  mask();observer=new MutationObserver(()=>mask());observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['href']});
  running=true;sdkLoaded=true;guardWorkers();window.dataLayer=window.dataLayer||[];
  (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments);};m[i].l=1*new Date();for(let j=0;j<document.scripts.length;j++)if(document.scripts[j].src===r)return;k=e.createElement(t);a=e.getElementsByTagName(t)[0];k.async=1;k.src=r;a.parentNode.insertBefore(k,a);})(window,document,'script','https://mc.yandex.ru/metrika/tag.js?id=114024456','ym');
  window.ym(counter,'init',{ssr:true,webvisor:true,clickmap:true,ecommerce:'dataLayer',referrer:safeReferrer(),url:cleanUrl(location.href),accurateTrackBounce:true,trackLinks:true});
 }finally{starting=false;}
 }
 function stop(){if(running||sdkLoaded)restrictAnalytics();if(running&&typeof window.ym==='function'){try{window.ym(counter,'destruct');}catch{}}observer?.disconnect();running=false;eraseMetrikaCookies();}
 if(!settingsPage&&privateUrl(location.href))return;
 if('BroadcastChannel' in window){const channel=new BroadcastChannel('neuro-analytics');channel.onmessage=async e=>{if(e.data==='deny'){localDenied=true;stop();eraseMetrikaCookies();}};}
 addEventListener('hashchange',()=>{if(running&&privateUrl(location.href))stop();});
 for(const key of ['pushState','replaceState']){const original=history[key];history[key]=function(...args){if(running&&args[2]&&privateUrl(new URL(args[2],location.href).href))stop();return Reflect.apply(original,this,args);};}

 // No consent UI and no fabricated grant: an absent receipt remains absent.
 window.neuroAnalytics={isRunning:()=>running};
 async function refresh(){if(!running)return;const next=await eligible();if(!next?.approved||!next.eligible||next.choice==='deny'){localDenied=true;stop();eraseMetrikaCookies();}}
 addEventListener('focus',refresh);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});setInterval(refresh,15000);
 (async()=>{status=await eligible();if(status?.approved&&status.eligible&&!optedOut())await start();})();
})();
