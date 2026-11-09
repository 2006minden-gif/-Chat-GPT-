'use strict';
(() => {
  const params=new URLSearchParams(location.hash.slice(1));
  let token=params.get('token') || '';
  // The capability never appears in server/access logs, subsequent URLs or Referer.
  history.replaceState(null,'',location.pathname);
  const form=document.querySelector('#owner-setup-form');
  const message=document.querySelector('#setup-message');
  if(!/^[a-f0-9]{64}$/.test(token)) {
    message.textContent='Откройте персональную ссылку первого входа, полученную от помощника.';
    return;
  }
  message.textContent='Пароль сохраняется на сервере только в виде защищённого хеша.';
  form.hidden=false;
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    const password=form.elements.password.value,repeat=form.elements.repeat.value;
    const bytes=new TextEncoder().encode(password).length;
    if(password!==repeat || bytes<12 || bytes>72) {message.textContent='Пароли должны совпадать; длина от 12 до 72 байт.';return;}
    const button=form.querySelector('button');button.disabled=true;
    try {
      const response=await fetch('/owner-setup.php',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,password,repeat})});
      const result=await response.json();
      if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Не удалось создать кабинет. Повторите позже.');
      if(result.ok!==true || result.url!=='/studio.php')throw new Error('Не удалось проверить ответ сервера.');
      token='';form.reset();form.hidden=true;
      message.textContent='Кабинет создан. Перенаправляем на вход…';
      location.replace('/studio.php');
    } catch(error) {
      message.textContent=error instanceof SyntaxError?'Сервис временно недоступен. Повторите позже.':error.message;
      button.disabled=false;
    }
  });
})();
