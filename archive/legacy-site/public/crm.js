'use strict';
const $ = s => document.querySelector(s);
let csrf = '', leads = [], selected = null, selectedVersion = null;
let draft = null,trashSupported=false,folder=location.hash==='#trash'?'trash':'active',removal=null;
const isLead = d => d && Number.isSafeInteger(d.id) && d.id>0 && Number.isInteger(d.version) && d.version>0 &&
  ['name','contact','service','idea','status','notes','next_step'].every(k=>typeof d[k]==='string') && Number.isFinite(d.created);
async function api(path, options = {}, {silentUnauthorized=false} = {}) {
  let validate;
  if(path==='leads') validate=d=>Array.isArray(d)&&d.every(isLead);
  else if(path==='session') validate=d=>typeof d.csrf==='string'&&Array.isArray(d.statuses)&&d.statuses.every(s=>typeof s==='string');
  else if(path==='login') validate=d=>typeof d.csrf==='string'&&d.csrf.length>0;
  else validate=d=>d.ok===true && (!path.startsWith('leads/')||Number.isInteger(d.version));
  try {
    return await NeuroAPI.request(path,{...options,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...options.headers}},validate);
  } catch(error) {
    if(error.status===401) {showLogin();$('#message').textContent=silentUnauthorized?'':error.message;}
    throw error;
  }
}
function showLogin() {
  document.dispatchEvent(new CustomEvent('neuro:owner-logout'));
  if($('#editor').open) {
    const original=leads.find(l=>l.id===selected);
    if(original)draft={...original,version:selectedVersion,status:$('#edit-status').value,notes:$('#notes').value,next_step:$('#next-step').value};
  }
  $('#dashboard').hidden=true;$('#logout').hidden=true;$('#login-panel').hidden=false;$('#editor').close();
  $('#lead-removal').close();removal=null;$('#lead-removal-description').textContent='';
  leads=[];$('#lead-list').replaceChildren();$('#stats').replaceChildren();
}
function el(tag, text, cls) { const node = document.createElement(tag); if(text !== undefined) node.textContent = text; if(cls) node.className=cls; return node; }
function render() {
  const active=leads.filter(l=>l.status!=='В корзине');$('#lead-trash-count').textContent=String(leads.length-active.length);$('#lead-active').setAttribute('aria-pressed',String(folder==='active'));$('#lead-trash').setAttribute('aria-pressed',String(folder==='trash'));$('#lead-trash-note').hidden=folder!=='trash';
  const stats = [['Всего заявок',active.length],['Новые',active.filter(l=>l.status==='Новая').length],['В работе',active.filter(l=>l.status==='В работе').length],['Завершены',active.filter(l=>l.status==='Завершена').length]];
  $('#stats').replaceChildren(...stats.map(([label,count])=>{ const card=el('div',undefined,'stat'); card.append(el('strong',count),el('span',label));return card; }));
  const q=$('#search').value.toLocaleLowerCase();
  const items=leads.filter(l=>(folder==='trash'?l.status==='В корзине':l.status!=='В корзине')&&(!$('#filter').value||l.status===$('#filter').value)&&[l.name,l.contact,l.idea,l.service].some(v=>v.toLocaleLowerCase().includes(q)));
  $('#lead-list').replaceChildren(...items.map(l=>{const card=el('article',undefined,'lead'), info=el('div'), side=el('div',undefined,'lead-side');card.dataset.leadId=String(l.id);info.append(el('h3',l.name),el('p',l.contact),el('p',l.service+' · '+new Date(l.created*1000).toLocaleDateString('ru-RU'))); if(l.next_step)info.append(el('p','Далее: '+l.next_step)); side.append(el('span',l.status,'badge'));const action=(title,run,cls='')=>{const b=el('button',title,cls);b.type='button';b.onclick=run;side.append(b);};if(folder==='trash'){action('Восстановить',()=>removalDialog(l,'restore'));action('Удалить навсегда',()=>removalDialog(l,'purge'),'lead-danger');}else{action('Открыть →',()=>openLead(l));if(trashSupported)action('Удалить',()=>removalDialog(l,'trash'),'lead-danger');}card.append(info,side);return card;}));
  if(!items.length)$('#lead-list').append(el('p',folder==='trash'?'Корзина пуста или нет заявок по выбранному фильтру.':active.length?'Ничего не найдено. Измените поиск или статус.':'Пока нет заявок. Новые обращения с сайта появятся здесь.','empty'));
}
function openLead(lead) {selected=lead.id;selectedVersion=lead.version;$('#reload-current').hidden=true;$('#client-name').textContent=lead.name;$('#client-contact').textContent=lead.contact+' · '+lead.service;$('#client-consent').textContent=lead.consent===1 ? 'Согласие: '+new Date(lead.consent_at*1000).toLocaleString('ru-RU')+' · версия '+lead.policy_version : 'Согласие не зафиксировано (историческая запись).';$('#client-idea').textContent=lead.idea;$('#edit-status').value=lead.status;$('#notes').value=lead.notes;$('#next-step').value=lead.next_step;$('#edit-message').textContent='';$('#editor').showModal();}
async function load() {leads=await api('leads');render();}
async function enter({initial=false} = {}) {const data=await api('session',{}, {silentUnauthorized:initial});csrf=data.csrf;trashSupported=data.trash_supported===true;$('#lead-folders').hidden=!trashSupported;document.dispatchEvent(new CustomEvent('neuro:owner-session',{detail:{csrf}}));for(const selector of ['#filter','#edit-status']){const target=$(selector);target.replaceChildren();if(selector==='#filter')target.append(new Option('Все статусы',''));data.statuses.forEach(s=>target.append(new Option(s,s)));}await load();$('#login-panel').hidden=true;$('#dashboard').hidden=false;$('#logout').hidden=false;$('#message').textContent='';if(draft){const saved=draft;draft=null;openLead(saved);$('#edit-message').textContent='Черновик восстановлен в этой вкладке. Проверьте его перед сохранением; версия будет проверена сервером.';}}
$('#login-form').onsubmit=async e=>{e.preventDefault();const button=e.currentTarget.querySelector('button');button.disabled=true;try{await api('login',{method:'POST',body:JSON.stringify({password:$('#password').value})});$('#password').value='';await enter();}catch(err){$('#message').textContent=err.message;}finally{button.disabled=false;}};
$('#logout').onclick=async()=>{try{await api('logout',{method:'POST'});csrf='';draft=null;showLogin();}catch(e){$('#message').textContent=e.message;}};
$('#refresh').onclick=()=>load().catch(e=>$('#message').textContent=e.message);
$('#search').oninput=render;$('#filter').onchange=render;$('#close-editor').onclick=()=>$('#editor').close();
$('#edit-form').onsubmit=async e=>{e.preventDefault();$('#save').disabled=true;try{await api('leads/'+selected,{method:'PATCH',body:JSON.stringify({version:selectedVersion,status:$('#edit-status').value,notes:$('#notes').value,next_step:$('#next-step').value})});await load();$('#editor').close();draft=null;}catch(err){$('#edit-message').textContent=err.message;if(err.status===409)$('#reload-current').hidden=false;}finally{$('#save').disabled=false;}};
enter({initial:true}).catch(e=>{if(e.status!==401)$('#message').textContent=e.message;});

$('#reload-current').onclick=async()=>{
  if(!confirm('Загрузить актуальную версию? Несохранённые правки в этом окне будут заменены.'))return;
  try {await load();const lead=leads.find(l=>l.id===selected);if(!lead)throw new Error('Заявка больше недоступна.');openLead(lead);}
  catch(error){$('#edit-message').textContent=error.message;}
};

function setFolder(){folder=location.hash==='#trash'?'trash':'active';$('#filter').value='';render();}
$('#lead-active').onclick=()=>{location.hash='leads';};$('#lead-trash').onclick=()=>{location.hash='trash';};window.addEventListener('hashchange',setFolder);
function removalDialog(lead,action){
 removal={lead,action};$('#lead-removal-confirm').checked=false;$('#lead-removal-message').textContent='';$('#lead-removal-title').textContent=action==='purge'?'Удалить заявку навсегда?':action==='restore'?'Восстановить заявку?':'Переместить заявку в корзину?';
 $('#lead-removal-description').textContent='Заявка: '+lead.name+'. '+(action==='purge'?'Это необратимо. Удаляется только эта заявка без связанных рабочих записей. Заказы, документы и платежи не удаляются.':action==='restore'?'Заявка вернётся в список с прежним статусом.':'Заявка исчезнет из основного списка. Найти и восстановить её можно кнопкой «Корзина» над списком. Связанные заказы и документы сохраняются.');$('#lead-removal-submit').textContent=action==='purge'?'Удалить навсегда':action==='restore'?'Восстановить':'В корзину';$('#lead-removal').showModal();
}
$('#lead-removal-cancel').onclick=()=>$('#lead-removal').close();
$('#lead-removal-form').onsubmit=async e=>{e.preventDefault();if(!removal||!$('#lead-removal-confirm').checked||$('#lead-removal-submit').disabled)return;const {lead,action}=removal;$('#lead-removal-submit').disabled=true;try{await api('leads/'+lead.id+'/'+action,{method:'POST',body:JSON.stringify({version:lead.version,confirm:true,confirm_permanent:action==='purge'})});$('#lead-removal').close();await load();$('#message').textContent=action==='trash'?'Заявка перемещена в корзину.':action==='restore'?'Заявка восстановлена.':'Заявка удалена навсегда.';}catch(error){$('#lead-removal-message').textContent=error.message;}finally{$('#lead-removal-submit').disabled=false;}};
