'use strict';
(() => {
  const messages = {
    400:'Не удалось прочитать запрос. Обновите страницу и повторите попытку.',
    401:'Срок входа истёк или пароль неверен. Войдите снова. Несохранённые правки оставлены в этой вкладке.',
    403:'Действие не разрешено. Войдите заново и повторите попытку.',
    404:'Запись не найдена. Обновите список заявок.',
    409:'Заявка изменена в другой вкладке. Ваши правки не сохранены. Загрузите актуальные данные.',
    413:'Слишком большой запрос. Сократите текст и повторите попытку.',
    422:'Проверьте заполнение полей и повторите попытку.',
    429:'Слишком много попыток. Подождите 15 минут и попробуйте снова.'
  };
  const codes = {
    invalid_contact:'Укажите корректный email, Telegram @username (5–32 символа) или телефон РФ: +7/8 и 10 цифр.',
    invalid_service:'Выберите услугу из списка.',
    idempotency_conflict:'Этот запрос уже принят с другим содержимым. Измените заявку и отправьте её как новое обращение.',
    consent_required:'Для отправки заявки необходимо согласие на обработку данных.',
    policy_changed:'Документы обновлены. Перезагрузите страницу, ознакомьтесь с ними и подтвердите согласие заново.',
    privacy_unavailable:'Приём заявок временно отключён: документы об обработке данных ещё не опубликованы.'
  };
  class APIError extends Error {
    constructor(message, status=0, code='') {super(message);this.status=status;this.code=code;}
  }
  window.NeuroAPI = {
    async request(route, options = {}, validate = () => true, expectedStatus = 200, timeoutMs = 15000) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch('/api.php?r=' + encodeURIComponent(route), {...options,signal:controller.signal});
        const type = (response.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
        const httpMessage = messages[response.status] || 'Сервис временно недоступен. Повторите попытку позже. Введённые данные не удалены.';
        if (type !== 'application/json') throw new APIError(response.ok ? 'Сервер вернул неожиданный ответ. Сохранение не подтверждено. Повторите попытку позже.' : httpMessage,response.status);
        let data;
        try {data = await response.json();}
        catch (error) {
          if (controller.signal.aborted) throw error;
          throw new APIError('Не удалось проверить ответ сервера. Повторите попытку позже.',response.status);
        }
        if (!response.ok) throw new APIError((Object.hasOwn(codes,data?.error_code) ? codes[data.error_code] : httpMessage),response.status,data?.error_code || '');
        const expected = Array.isArray(expectedStatus) ? expectedStatus.includes(response.status) : response.status === expectedStatus;
        if (!expected || !data || typeof data !== 'object' || !validate(data)) throw new APIError('Не удалось подтвердить операцию. Данные не удалены. Повторите попытку позже.',response.status);
        return data;
      } catch (error) {
        if (error instanceof APIError) throw error;
        if (controller.signal.aborted) throw new APIError('Сервер не ответил вовремя. Данные не удалены. Повторите попытку: повторная отправка той же заявки безопасна.',0,'timeout');
        throw new APIError('Не удалось связаться с сервером. Проверьте соединение и повторите попытку. Данные не удалены.');
      } finally {clearTimeout(timer);}
    }
  };
})();
