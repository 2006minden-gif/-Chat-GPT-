'use strict';
(() => {
  const form=document.querySelector('#max-settings-form');
  const status=document.querySelector('#max-status');
  const pairing=document.querySelector('#max-pairing');
  async function call(method='GET',body=null) {
    const response=await fetch('/api.php?r=notifications/max',{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},...(body?{body:JSON.stringify(body)}:{})});
    let data;try{data=await response.json();}catch(e){throw new Error('Сервис временно недоступен. Повторите позже.');}
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Не удалось выполнить действие.');
    return data;
  }
  async function refresh(){
    if(document.querySelector('#dashboard').hidden)return;
    try{const data=await call();
      status.textContent=data.connected?'MAX подключён. Ожидают отправки: '+data.pending+(data.error_code?'. Доставка задержана — повторим автоматически.':'.'):data.pair_received?'Получено ваше сообщение в MAX. Нажмите «Подтвердить и проверить».':data.configured?'Ожидаем привязку вашего личного чата с ботом.':'MAX пока не подключён.';
      document.querySelector('#max-confirm').hidden=!data.pair_received;
      document.querySelector('#max-retry').hidden=!data.connected;
      document.querySelector('#max-disable').hidden=!data.connected;
      if(data.connected){pairing.hidden=true;document.querySelector('#max-command').textContent='';}
    }catch(e){status.textContent=e.message;}
  }
  form.addEventListener('submit',async event=>{
    event.preventDefault();const token=document.querySelector('#max-token');const button=form.querySelector('button');button.disabled=true;
    try{const result=await call('POST',{action:'connect',token:token.value.trim()});
      token.value='';
      if(!/^\/connect [a-f0-9]{32}$/.test(result.command)||!/^https:\/\/max\.ru\/[A-Za-z0-9_]+$/.test(result.bot_url))throw new Error('Не удалось проверить ответ подключения.');
      document.querySelector('#max-command').textContent=result.command;document.querySelector('#max-bot-link').href=result.bot_url;pairing.hidden=false;await refresh();
    }catch(e){token.value='';status.textContent=e.message;}finally{button.disabled=false;}
  });
  for(const [id,action] of [['max-confirm','confirm'],['max-retry','retry'],['max-disable','disable']])document.querySelector('#'+id).addEventListener('click',async event=>{
    if(action==='disable'&&!confirm('Отключить уведомления в MAX? Заявки продолжат сохраняться в кабинете.'))return;
    const button=event.currentTarget;button.disabled=true;
    try{await call('POST',{action});await refresh();}catch(e){status.textContent=e.message;}finally{button.disabled=false;}
  });
  document.querySelector('#max-refresh').addEventListener('click',refresh);
  new MutationObserver(()=>{if(!document.querySelector('#dashboard').hidden)refresh();}).observe(document.querySelector('#dashboard'),{attributes:true,attributeFilter:['hidden']});
  // Remove sensitive setup text when the session is hidden/logged out.
  new MutationObserver(()=>{if(document.querySelector('#dashboard').hidden){document.querySelector('#max-token').value='';document.querySelector('#max-command').textContent='';pairing.hidden=true;}}).observe(document.querySelector('#dashboard'),{attributes:true,attributeFilter:['hidden']});
  setInterval(refresh,15000);
})();
