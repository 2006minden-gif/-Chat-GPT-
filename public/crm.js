'use strict';
const $ = s => document.querySelector(s);
let csrf = '', leads = [], selected = null, selectedVersion = null;
let draft = null;
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
  if($('#editor').open) {
    const original=leads.find(l=>l.id===selected);
    if(original)draft={...original,version:selectedVersion,status:$('#edit-status').value,notes:$('#notes').value,next_step:$('#next-step').value};
  }
  $('#dashboard').hidden=true;$('#logout').hidden=true;$('#login-panel').hidden=false;$('#editor').close();
  leads=[];$('#lead-list').replaceChildren();$('#stats').replaceChildren();
}
function el(tag, text, cls) { const node = document.createElement(tag); if(text !== undefined) node.textContent = text; if(cls) node.className=cls; return node; }
function render() {
  const stats = [['Всего заявок',leads.length],['Новые',leads.filter(l=>l.status==='Новая').length],['В работе',leads.filter(l=>l.status==='В работе').length],['Завершены',leads.filter(l=>l.status==='Завершена').length]];
  $('#stats').replaceChildren(...stats.map(([label,count])=>{ const card=el('div',undefined,'stat'); card.append(el('strong',count),el('span',label));return card; }));
  const q=$('#search').value.toLocaleLowerCase();
  const items=leads.filter(l=>(!$('#filter').value||l.status===$('#filter').value)&&[l.name,l.contact,l.idea,l.service].some(v=>v.toLocaleLowerCase().includes(q)));
  $('#lead-list').replaceChildren(...items.map(l=>{const card=el('article',undefined,'lead'), info=el('div'), side=el('div',undefined,'lead-side');info.append(el('h3',l.name),el('p',l.contact),el('p',l.service+' · '+new Date(l.created*1000).toLocaleDateString('ru-RU'))); if(l.next_step)info.append(el('p','Далее: '+l.next_step)); const button=el('button','Открыть →');button.onclick=()=>openLead(l);side.append(el('span',l.status,'badge'),button);card.append(info,side);return card;}));
  if(!items.length)$('#lead-list').append(el('p',leads.length?'Ничего не найдено. Измените поиск или статус.':'Пока нет заявок. Новые обращения с сайта появятся здесь.','empty'));
}
function openLead(lead) {selected=lead.id;selectedVersion=lead.version;$('#reload-current').hidden=true;$('#client-name').textContent=lead.name;$('#client-contact').textContent=lead.contact+' · '+lead.service;$('#client-consent').textContent=lead.consent===1 ? 'Согласие: '+new Date(lead.consent_at*1000).toLocaleString('ru-RU')+' · версия '+lead.policy_version : 'Согласие не зафиксировано (историческая запись).';$('#client-idea').textContent=lead.idea;$('#edit-status').value=lead.status;$('#notes').value=lead.notes;$('#next-step').value=lead.next_step;$('#edit-message').textContent='';$('#editor').showModal();}
async function load() {leads=await api('leads');render();}
async function enter({initial=false} = {}) {const data=await api('session',{}, {silentUnauthorized:initial});csrf=data.csrf;for(const selector of ['#filter','#edit-status']){const target=$(selector);target.replaceChildren();if(selector==='#filter')target.append(new Option('Все статусы',''));data.statuses.forEach(s=>target.append(new Option(s,s)));}await load();$('#login-panel').hidden=true;$('#dashboard').hidden=false;$('#logout').hidden=false;$('#message').textContent='';if(draft){const saved=draft;draft=null;openLead(saved);$('#edit-message').textContent='Черновик восстановлен в этой вкладке. Проверьте его перед сохранением; версия будет проверена сервером.';}}
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
