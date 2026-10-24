
'use strict';
document.querySelector('#year').textContent = new Date().getFullYear();
document.querySelectorAll('[data-service]').forEach(link => {
  link.addEventListener('click', () => { document.querySelector('#service').value = link.dataset.service; });
});
let pendingSnapshot = null, pendingKey = null, submitting = false, privacy = null;
const briefForm = document.querySelector('#brief-form');
async function loadPrivacy() {
  try {
    privacy = await NeuroAPI.request('privacy',{},d=>typeof d.enabled==='boolean'&&typeof d.version==='string'&&d.url==='/privacy.php');
    if(!privacy.enabled)throw new Error('Приём заявок временно отключён: документы об обработке данных ещё не опубликованы.');
    document.querySelector('#consent').disabled=false;
    briefForm.querySelector('button[type="submit"]').disabled=false;
    document.querySelector('#privacy-status').textContent='';
  } catch(error) {document.querySelector('#privacy-status').textContent=error.message;}
}
loadPrivacy();
function briefPayload(form) {
  const payload = Object.fromEntries(new FormData(form));
  payload.consent = document.querySelector('#consent').checked;
  payload.policy_version = privacy.version;
  return payload;
}
briefForm.addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  if (submitting || !privacy?.enabled || !form.reportValidity()) return;
  submitting = true;
  const button = form.querySelector('button[type="submit"]');
  const status = document.querySelector('#form-status');
  button.disabled = true;
  status.textContent = 'Сохраняем заявку…';
  try {
    const payload = briefPayload(form);
    const snapshot = JSON.stringify(payload);
    if (snapshot !== pendingSnapshot) {
      pendingSnapshot = snapshot;
      pendingKey = Array.from(crypto.getRandomValues(new Uint8Array(32)), b => b.toString(16).padStart(2,'0')).join('');
    }
    payload.idempotency_key = pendingKey;
    await NeuroAPI.request('leads', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)},
      data => data.ok === true && Number.isSafeInteger(data.lead_id) && data.lead_id > 0, 201);
    if (JSON.stringify(briefPayload(form)) === snapshot) {
      form.reset();
      status.textContent = 'Заявка сохранена! Свяжемся с вами по указанному контакту.';
    } else {
      status.textContent = 'Отправленная заявка сохранена. Новые правки остались в форме и ещё не отправлены.';
    }
    pendingSnapshot = null; pendingKey = null;
  } catch (error) {
    status.textContent = error.message;
    if(error.code==='policy_changed' || error.code==='privacy_unavailable') {
      document.querySelector('#consent').checked=false;document.querySelector('#consent').disabled=true;
      privacy=null;await loadPrivacy();
    }
  } finally { button.disabled = !privacy?.enabled; submitting = false; }
});
