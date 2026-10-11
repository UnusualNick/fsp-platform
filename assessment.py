"""Versioned, parameterized assessment forms. Answers never leave the server."""
import random
import secrets
from question_bank import CORE

SPECIALIZATIONS = {'backend': 'Backend-разработка', 'frontend': 'Frontend-разработка', 'data': 'Аналитика данных'}
GRADES = ('Junior', 'Middle', 'Senior')
BLUEPRINT_VERSION = '2026.10.2'
THRESHOLDS = {'Junior': 67, 'Middle': 75, 'Senior': 84}

ANCHORS = {
 'backend': [
  ('Как обеспечить повторяемый запрос создания заказа без двойной записи?', ['Идемпотентный ключ и уникальное ограничение в БД', 'Повторить INSERT при каждом запросе', 'Проверить только локальный кэш', 'Увеличить таймаут']),
  ('Два запроса одновременно списывают остаток. Как защитить инвариант остаток >= 0?', ['Атомарное условное обновление в транзакции', 'Прочитать остаток и затем записать без блокировки', 'Задержать второй запрос на 1 секунду', 'Скрыть ошибку на клиенте'])],
 'frontend': [
  ('Поиск отправляет запросы A, затем B. Ответ A пришёл позже B. Как сохранить актуальную выдачу?', ['Применять ответ только для текущего идентификатора запроса', 'Применять ответы в порядке получения', 'Очищать весь экран после любого ответа', 'Увеличить debounce без контроля ответа']),
  ('Что обеспечивает доступность поля с ошибкой?', ['Связанные label, aria-describedby и текст ошибки', 'Красная рамка без текста', 'Только placeholder', 'Отключение Tab'])],
 'data': [
  ('Как оценить прогноз временного ряда без утечки будущего?', ['Разделить обучение и проверку по времени', 'Случайно перемешать строки всех дат', 'Обучить на тестовой выборке', 'Нормировать по всей выборке до разделения']),
  ('Почему INNER JOIN может увеличить число строк исходной таблицы?', ['Ключ правой таблицы не уникален', 'JOIN всегда удаляет дубликаты', 'Число строк всегда сохраняется', 'NULL автоматически становится нулём'])]
}

ADVANCED_ANCHORS = {
 ('backend','Middle'): [
  ('Сервис фиксирует заказ в PostgreSQL и публикует событие в Kafka. Между этими действиями возможен сбой. Как избежать потери события?', ['Записать заказ и outbox в одной транзакции, отправлять outbox с повторами', 'Сначала отправить событие, затем записать заказ без компенсации', 'Игнорировать ошибку отправки', 'Хранить событие только в памяти']),
  ('Повторный запрос с тем же идемпотентным ключом содержит другое тело. Что должен сделать сервер?', ['Отклонить конфликт по отпечатку тела и сохранённому ключу', 'Создать второй заказ', 'Молча заменить исходный заказ', 'Принять любой последний запрос'])],
 ('backend','Senior'): [
  ('Перевод денег проходит через две независимые БД без общей транзакции. Сеть может разорваться после локального коммита. Как сохранить возможность восстановления?', ['Сага с журналом состояния, идемпотентными шагами и компенсацией', 'Параллельно изменить обе БД без журнала', 'Считать сетевой timeout доказательством отката', 'Повторять оба списания при любом сбое']),
  ('Consumer получил повтор события после коммита БД, но до подтверждения брокеру. Как обеспечить один бизнес-эффект?', ['Атомарно сохранять processed_event_id и бизнес-изменение в одной транзакции', 'Доверять памяти одного consumer', 'Отключить повторную доставку', 'Подтвердить сообщение до записи в БД'])],
 ('frontend','Middle'): [
  ('Компонент запускает запрос при изменении query. Как избежать применения устаревшего результата после нового запроса?', ['Использовать cleanup и идентификатор актуального запроса', 'Применять все ответы без проверки', 'Удалить query из зависимостей эффекта', 'Кэшировать только первый ответ навсегда']),
  ('Список редактируемых строк меняет порядок. Какой key сохраняет связь состояния с записью?', ['Стабильный уникальный id записи', 'Индекс массива', 'Случайное число на каждом рендере', 'Текущее время'])],
 ('frontend','Senior'): [
  ('Optimistic update A и B меняют одну запись. A завершился ошибкой после успеха B. Как безопасно восстановить состояние?', ['Откатить только эффект A с учётом версии, затем сверить с сервером', 'Вернуть весь snapshot до A', 'Стереть запись из кэша навсегда', 'Применить неудачный ответ A поверх B']),
  ('SSR-приложение выводит пользовательский HTML. Как предотвратить stored XSS?', ['Санитизация по allowlist и отказ от опасных HTML-вставок', 'Скрыть script с помощью CSS', 'Экранировать только кавычки в URL', 'Доверять HTML любого авторизованного пользователя'])],
 ('data','Middle'): [
  ('Признак содержит информацию, появившуюся после события, которое модель предсказывает. Что необходимо изменить?', ['Ввести point-in-time join и исключить будущие значения', 'Добавить признак во все выборки', 'Увеличить глубину дерева', 'Перемешать даты']),
  ('В A/B-тесте один пользователь создаёт много сессий. Как корректно оценить дисперсию при рандомизации по пользователю?', ['Считать статистику по пользователю или кластеризовать по нему', 'Считать все сессии независимыми', 'Удалить случайно половину сессий', 'Выбрать только пользователей с успехом'])],
 ('data','Senior'): [
  ('Вы оцениваете новую рекомендательную политику по логам старой. Какие данные нужны для inverse propensity weighting?', ['Вероятность показанного действия старой политики и перекрытие действий', 'Только итоговая конверсия', 'Только самые успешные рекомендации', 'Номер экспериментальной группы без вероятностей']),
  ('Эксперимент непрерывно проверяют и останавливают при p<0.05. Как контролировать ошибку первого рода?', ['Заранее задать горизонт или использовать корректный последовательный тест', 'Продолжать обычный тест до удобного p-value', 'Уменьшать выборку после каждой проверки', 'Удалить все незначимые измерения'])]
}

def generate(spec, grade, seed=None):
 if spec not in SPECIALIZATIONS or grade not in GRADES:
  raise ValueError('Неизвестная специализация или грейд')
 rng = random.Random(seed if seed is not None else secrets.randbits(128))
 depth = GRADES.index(grade) + 1
 qs = []
 def add(prompt, correct, distractors, skill, anchor=False):
  values = [str(correct)]
  for option in distractors:
   candidate = str(option)
   while candidate in values:
    option = float(option) + 1
    candidate = str(int(option)) if option.is_integer() else str(round(option,1))
   values.append(candidate)
  assert len(set(values)) == 4
  rng.shuffle(values)
  qs.append({'id': f'q{len(qs)+1}', 'prompt': prompt, 'options': values, 'answer': values.index(str(correct)), 'skill': skill, 'anchor': anchor})
 for prompt, opts in ADVANCED_ANCHORS.get((spec,grade),ANCHORS[spec]):
  add(prompt, opts[0], opts[1:], 'engineering', True)
 for variant in range(4):
  a = rng.randint(12, 65)*depth
  b = rng.randint(3, 9)
  c = rng.randint(2, 7)
  if spec == 'backend':
   if variant % 2 == 0:
    overhead = depth*7
    correct = ((a+b-1)//b)*c+overhead
    add(f'Сервис обрабатывает {a} независимых запросов. Одновременно выполняются {b}, каждый длится {c} мс. Все запросы готовы в момент 0, следующий пакет стартует после завершения предыдущего. Финальная фиксация занимает ещё {overhead} мс. Через сколько мс завершится весь пакет?', correct, [correct-c, correct+c, a*c+overhead], 'concurrency')
   else:
    duplicates = b*depth
    add(f'В БД {a} заказов. В обработчик поступило {b+c} уникальных новых id и {duplicates} повторных id существующих заказов. INSERT использует UNIQUE(order_id) ON CONFLICT DO NOTHING. Сколько заказов станет в БД?', a+b+c, [a+b+c+duplicates,a,a+b+c-1], 'idempotency')
  elif spec == 'frontend':
   if variant % 2 == 0:
    gap = depth*8
    correct = b*c+(b-1)*gap
    add(f'В CSS Grid {b} колонок шириной {c*10}px с gap {gap}px. Какова общая ширина сетки без padding и border?', b*c*10+(b-1)*gap, [b*c*10+b*gap,b*c*10,b*c*10+(b+1)*gap], 'layout')
   else:
    # Explicit recurrence avoids framework-dependent batching assumptions.
    add(f'Редьюсер начинает со state={a}. Он последовательно применяет {b} действий add({c}), затем одно multiply({depth+1}). Каков итоговый state? Каждое действие работает с результатом предыдущего.', (a+b*c)*(depth+1), [a+b*c*(depth+1),(a+c)*(depth+1),(a+b*c)*(depth+1)+c], 'state')
  else:
   if variant % 2 == 0:
    add(f'Таблица A содержит {a} уникальных ключей. Для {b} из них в B есть по {c} строк, для остальных совпадений нет. Сколько строк вернёт A LEFT JOIN B по ключу?', a-b+b*c, [a+b*c,b*c,a], 'sql')
   else:
    positives=a; true_pos=b*depth; false_pos=c*depth
    correct=round(true_pos/(true_pos+false_pos)*100,1)
    distract=[round(true_pos/positives*100,1), round(false_pos/(true_pos+false_pos)*100,1),100.0]
    # Very rare coincident fractions: use fixed numeric offsets instead.
    if len(set([correct]+distract))<4: distract=[round(correct+1.3,1),round(correct+2.7,1),round(correct+4.1,1)]
    add(f'Классификатор дал TP={true_pos}, FP={false_pos}; всего в выборке {positives} положительных объектов. Чему равна precision в процентах? Округлите до одного знака.', correct,distract,'metrics')
 # Fixed competency coverage; alternate scenario within each family.
 # Appended after the legacy six items so existing active forms remain untouched.
 for skill, variants in CORE[spec].items():
  prompt, correct, *wrong = rng.choice(variants)
  add(prompt, correct, wrong, skill)
 return {'version': BLUEPRINT_VERSION, 'specialization': spec, 'grade': grade, 'questions': qs, 'threshold': THRESHOLDS[grade]}

def public_form(form):
 return {**{k:v for k,v in form.items() if k!='questions'},'questions':[{k:v for k,v in q.items() if k not in ('answer','anchor')} for q in form['questions']]}

def evaluate(form, answers):
 if not isinstance(answers, dict) or set(answers) != {q['id'] for q in form['questions']}:
  raise ValueError('Нужно ответить на каждое задание')
 if any(type(v) is not int or v not in range(4) for v in answers.values()):
  raise ValueError('Недопустимый ответ')
 correct = sum(answers[q['id']]==q['answer'] for q in form['questions'])
 score = round(correct / len(form['questions'])*100,1)
 return {'score':score, 'passed':score>=form['threshold'], 'correct':correct, 'total':len(form['questions']), 'threshold':form['threshold']}
