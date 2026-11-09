'use strict';
(() => {
  let csrf='',generation=0;
  const $=s=>document.querySelector(s);
  const messages={409:'Аккаунт изменён. Обновите список и повторите действие.',401:'Войдите в CRM заново.',403:'Действие не разрешено. Обновите страницу.',422:'Проверьте поля. Активировать можно только подтверждённый аккаунт действующего клиента.',429:'Слишком много запросов. Повторите позже.'};
  async function api(route,body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
    try{
      const r=await fetch('/customer-api.php?r='+encodeURIComponent(route),{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});
      if((r.headers.get('Content-Type')||'').split(';')[0].trim().toLowerCase()!=='application/json')throw new Error('Ответ сервера не подтверждён. Повторите позже.');
      const d=await r.json();if(!r.ok)throw new Error(d.error_code==='payment_required'?'Нужен заказ этого клиента с проверенным бумажным договором и подтверждённым поступлением.':messages[r.status]||'Клиентские аккаунты временно недоступны.');
      if(!d||typeof d!=='object'||(route==='settings'?typeof d.enabled!=='boolean':d.ok!==true)||!(route==='owner/invite'?[200,202].includes(r.status):r.status===200))throw new Error('Операция не подтверждена сервером.');
      return d;
    }catch(e){if(e.name==='AbortError'||e instanceof TypeError||e instanceof SyntaxError)throw new Error('Не удалось связаться с сервером. Данные формы сохранены; повторите позже.');throw e;}
    finally{clearTimeout(timer);}
  }
  async function load(){
    const current=generation,d=await api('owner/accounts');
    if(current!==generation)return;
    if(!Array.isArray(d.accounts)||!d.accounts.every(a=>Number.isSafeInteger(a.id)&&Number.isInteger(a.version)&&typeof a.email==='string'&&typeof a.name==='string'&&['active','invited','disabled'].includes(a.status)))throw new Error('Некорректный ответ сервера.');
    $('#customer-accounts').replaceChildren();
    for(const a of d.accounts){
      const card=document.createElement('article');card.className='lead';const info=document.createElement('p');info.textContent=a.name+' · '+a.email+' · '+({active:'Активен',invited:'Ожидает подтверждения',disabled:'Отключён'})[a.status]+' · ID клиента: '+a.customer_id+' · Почта: '+(({mail_accepted:'SMTP принял письмо',mail_failed:'отправка не подтверждена — повторите приглашение'})[a.mail_status]||'нет данных');card.append(info);
      for(const [action,title] of a.status==='disabled'?[['enable','Включить']]:[['disable','Отключить'],['revoke_sessions','Завершить сеансы']]){
        const b=document.createElement('button');b.className='header-cta';b.textContent=title;b.onclick=async()=>{if(!confirm(title+' для выбранного аккаунта?'))return;b.disabled=true;try{const result=await api('owner/lifecycle',{account_id:a.id,version:a.version,action});if(!Number.isInteger(result.version))throw new Error('Изменение не подтверждено.');await load();$('#accounts-message').textContent='Изменение сохранено.';}catch(e){$('#accounts-message').textContent=e.message;b.disabled=false;}};card.append(b);
      }$('#customer-accounts').append(card);
    }
  }
  document.addEventListener('neuro:owner-session',async e=>{const current=++generation;csrf=e.detail.csrf;try{const s=await api('settings');if(current!==generation||!s.enabled)return;if(s.paid_invitation_required===true){$('#invite-customer').required=true;$('#invite-order').required=true;$('#invite-name').hidden=true;document.querySelector('label[for=invite-name]').hidden=true;}$('#customer-management').hidden=false;await load();}catch(e){if(current===generation)$('#accounts-message').textContent=e.message;}});
  document.addEventListener('neuro:owner-logout',()=>{generation++;csrf='';$('#customer-management').hidden=true;$('#customer-accounts').replaceChildren();$('#accounts-message').textContent='';$('#customer-invite-form').reset();});
  $('#accounts-refresh').onclick=()=>load().catch(e=>$('#accounts-message').textContent=e.message);
  $('#customer-invite-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,b=form.querySelector('button'),value=$('#invite-customer').value,body={email:$('#invite-email').value};if($('#invite-order').value)body.order_id=Number($('#invite-order').value);if(value){body.customer_id=Number(value);if(!Number.isSafeInteger(body.customer_id)||body.customer_id<1){$('#accounts-message').textContent='Укажите корректный ID клиента.';return;}}else{body.name=$('#invite-name').value;if(!body.name.trim()){$('#accounts-message').textContent='Укажите имя нового клиента.';return;}}b.disabled=true;try{const result=await api('owner/invite',body);await load();$('#accounts-message').textContent=result.message||'Запрос обработан. SMTP-приём не доказывает получение письма клиентом.';await load();}catch(error){$('#accounts-message').textContent=error.message;}finally{b.disabled=false;}};
})();
