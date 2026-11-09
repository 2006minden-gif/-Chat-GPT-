'use strict';
(() => {
  const $ = s => document.querySelector(s), view=document.body.dataset.view;
  // Tokens only arrive in the fragment, never in server/access-log query strings or persistent browser storage.
  let token=new URLSearchParams(location.hash.slice(1)).get('token') || '';
  if(location.hash)history.replaceState(null,'',location.pathname+location.search);
  let csrf='', policyVersion='', ready=false;
  const errors={
    invalid_email:'Укажите корректный email.',weak_password:'Пароль: от 12 символов, буквы и цифры, не более 72 байт.',password_mismatch:'Пароли не совпадают.',
    consent_required:'Прочитайте документы и подтвердите согласие.',policy_changed:'Документы обновлены. Обновите страницу, прочитайте их и подтвердите согласие заново.',
    login_failed:'Не удалось войти. Проверьте email, пароль и подтверждение email.',invalid_token:'Ссылка недействительна, уже использована или срок её действия истёк. Запросите новую.',
    csrf_invalid:'Срок действия формы истёк. Обновите страницу и повторите действие.',session_expired:'Войдите в кабинет заново.',rate_limited:'Слишком много попыток. Повторите через 15 минут.',
    registration_unavailable:'Кабинет временно недоступен. Регистрация пока закрыта.'
  };
  async function api(route,body) {
    const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),20000);
    try {
      const r=await fetch('/customer-api.php?r='+encodeURIComponent(route),{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal,credentials:'same-origin'});
      if((r.headers.get('Content-Type')||'').split(';')[0].trim().toLowerCase()!=='application/json')throw new Error('Не удалось подтвердить ответ сервера. Повторите попытку позже.');
      let d;try{d=await r.json();}catch{throw new Error('Не удалось проверить ответ сервера. Повторите попытку позже.');}
      if(!r.ok){const e=new Error(errors[d?.error_code]||(r.status===429?errors.rate_limited:'Сервис временно недоступен. Введённые данные сохранены в этой форме.'));e.status=r.status;throw e;}
      const valid=d&&typeof d==='object'&&(route==='settings'?(typeof d.enabled==='boolean'&&typeof d.policy?.version==='string'):
        d.ok===true&&(route!=='session'||(typeof d.authenticated==='boolean'&&/^[a-f0-9]{64}$/.test(d.csrf)&&(!d.authenticated||(typeof d.account?.name==='string'&&typeof d.account?.email==='string'))))&&(route!=='login'||/^[a-f0-9]{64}$/.test(d.csrf)));
      const status=route==='register'||route==='forgot'||route==='resend'?202:200;
      if(!valid||r.status!==status)throw new Error('Операция не подтверждена сервером. Повторите попытку позже.');
      return d;
    } catch(e){if(e instanceof TypeError||e.name==='AbortError')throw new Error('Нет ответа от сервера. Данные оставлены в форме; повторите попытку позже.');throw e;}
    finally{clearTimeout(timer);}
  }
  function home(s){$('#customer-home').hidden=false;$('#customer-form').hidden=true;$('.customer-nav').hidden=true;$('#page-title').textContent='Ваш кабинет.';$('#customer-identity').textContent=s.account.name+' · '+s.account.email;}
  async function init(){
    try{
      const settings=await api('settings');policyVersion=settings.policy.version;
      if(view==='register'&&settings.registration_enabled===false){$('#availability').textContent='Публичная регистрация закрыта. Доступ выдаётся приглашением после подтверждения оплаты.';return;}
      if(!settings.enabled){$('#availability').textContent=errors.registration_unavailable;return;}
      let session;try{session=await api('session');}catch(e){if(e.status===401||e.status===403){$('#availability').textContent=e.message;return;}throw e;}
      csrf=session.csrf;
      if(session.authenticated&&view==='login'){home(session);$('#availability').textContent='Защищённый вход выполнен.';return;}
      if(['invite','reset','verify'].includes(view)&&!/^[a-f0-9]{64}$/.test(token)){$('#availability').textContent=errors.invalid_token;return;}
      ready=true;$('#auth-fields').disabled=false;
      $('#availability').textContent=session.needs_consent?'Документы обновлены. Подтвердите согласие и войдите заново.':view==='verify'?'Нажмите кнопку, чтобы подтвердить email.':view==='invite'?'Создайте пароль и подтвердите согласие, чтобы завершить регистрацию.':'';
    }catch(e){$('#availability').textContent=e.message;}
  }
  const toggle=$('#toggle-password');if(toggle)toggle.onclick=()=>{const field=$('#customer-password'),visible=field.type==='password';field.type=visible?'text':'password';toggle.textContent=visible?'Скрыть':'Показать';toggle.setAttribute('aria-pressed',String(visible));};
  $('#customer-form').onsubmit=async e=>{
    e.preventDefault();if(!ready)return;const form=e.currentTarget;if(!form.reportValidity())return;
    const d={};for(const name of ['name','email','password','password_confirmation']){const field=form.elements.namedItem(name);if(field)d[name]=field.value;}
    const consent=$('#customer-consent');if(consent){d.consent=consent.checked;d.policy_version=policyVersion;}
    if(token)d.token=token;
    $('#customer-message').textContent='';
    if(d.password_confirmation!==undefined&&d.password!==d.password_confirmation){$('#customer-message').textContent=errors.password_mismatch;return;}
    if(view!=='login'&&d.password!==undefined&&(new TextEncoder().encode(d.password).length>72||d.password.length<12||!/[\p{L}]/u.test(d.password)||!/[\p{N}]/u.test(d.password))){$('#customer-message').textContent=errors.weak_password;return;}
    ready=false;$('#auth-fields').disabled=true;$('#customer-submit').textContent='Подождите…';
    try{
      const result=await api(view,d);
      if(view==='login'){csrf=result.csrf;home(await api('session'));$('#customer-message').textContent='';}
      else if(['register','forgot','resend'].includes(view)){$('#customer-message').textContent='Если действие доступно для этого адреса, письмо будет отправлено. Проверьте почту и «Спам». При отсутствии письма повторите запрос позже.';}
      else{token='';$('#customer-form').hidden=true;$('#customer-message').textContent=view==='reset'?'Пароль обновлён. Войдите с новым паролем.':'Email подтверждён. Теперь можно войти в кабинет.';}
      for(const name of ['password','password_confirmation']){const field=form.elements.namedItem(name);if(field)field.value='';}
    }catch(error){$('#customer-message').textContent=error.message;}
    finally{ready=true;$('#auth-fields').disabled=false;$('#customer-submit').textContent=$('#page-title').textContent.replace(/\.$/,'')+' →';}
  };
  $('#customer-logout').onclick=async()=>{const b=$('#customer-logout');b.disabled=true;try{await api('logout',{});location.assign('/customer.php');}catch(e){$('#customer-message').textContent=e.message;b.disabled=false;}};
  init();
})();
