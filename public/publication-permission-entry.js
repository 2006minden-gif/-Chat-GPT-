'use strict';
(async()=>{try{const r=await fetch('/customer-api.php?r=session'),s=await r.json();if(!r.ok||!s.authenticated)throw Error('Войдите в клиентский кабинет.');await window.ndPublicationPermissions(document.querySelector('#permission-content'),'customer',s.csrf);}catch(e){document.querySelector('#permission-message').textContent=e.message;}})();
