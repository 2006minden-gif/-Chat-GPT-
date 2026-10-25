(() => {
  'use strict';
  const tool = document.getElementById('brief-tool');
  if (!tool) return;
  const form = document.getElementById('service-brief');
  const service = document.getElementById('brief-service');
  const goal = document.getElementById('brief-goal');
  const result = document.getElementById('brief-result');
  const summary = document.getElementById('brief-summary');
  const telegram = document.getElementById('telegram-brief');
  const status = document.getElementById('brief-status');
  const groups = [...document.querySelectorAll('[data-options]')];
  const invalidate = () => { result.hidden = true; summary.value = ''; telegram.href = 'https://t.me/minden2006'; status.textContent = ''; };
  const select = (key) => {
    if (![...service.options].some(option => option.value === key)) return;
    service.value = key;
    groups.forEach(group => {
      group.hidden = group.dataset.options !== key;
      group.querySelectorAll('input').forEach(input => { input.disabled = group.hidden; });
    });
    invalidate();
  };
  tool.hidden = false;
  const requested = new URLSearchParams(location.search).get('service');
  select([...service.options].some(option => option.value === requested) ? requested : service.value);
  service.addEventListener('change', () => select(service.value));
  form.addEventListener('input', invalidate);
  document.querySelectorAll('.choose-service').forEach(link => link.addEventListener('click', () => { select(link.dataset.service); goal.focus({preventScroll: true}); }));
  form.addEventListener('submit', event => {
    event.preventDefault();
    const cleanGoal = goal.value.trim();
    if (!cleanGoal) { status.textContent = 'Коротко опишите задачу проекта.'; goal.focus(); return; }
    const selected = [...form.querySelectorAll('input[name="feature"]:checked:not(:disabled)')].map(input => input.value);
    const text = ['Здравствуйте! Хочу обсудить проект с НейроДело.', '', 'Направление: ' + service.selectedOptions[0].textContent, 'Задача: ' + cleanGoal, 'Пожелания: ' + (selected.length ? selected.join('; ') : 'обсудим вместе'), '', 'Прошу уточнить состав работ, стоимость и сроки.'].join('\n');
    summary.value = text;
    telegram.href = 'https://t.me/minden2006?text=' + encodeURIComponent(text);
    result.hidden = false;
    status.textContent = 'Бриф подготовлен в этой вкладке. Ничего не отправлено.';
    summary.focus();
  });
  document.getElementById('copy-brief').addEventListener('click', async () => {
    const text = summary.value;
    if (!text || result.hidden) return;
    try {
      if (!navigator.clipboard || !window.isSecureContext) throw new Error('clipboard_unavailable');
      await navigator.clipboard.writeText(text);
      status.textContent = summary.value === text && !result.hidden ? 'Бриф скопирован. Вставьте его в сообщение в Telegram.' : 'Скопирован предыдущий вариант. Подготовьте новый бриф после изменений.';
    } catch {
      summary.focus(); summary.select();
      status.textContent = 'Автоматическое копирование недоступно. Выделите текст и скопируйте его вручную.';
    }
  });
})();
