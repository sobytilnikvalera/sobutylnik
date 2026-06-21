# Собутыльник — Архитектура Telegram-бота

## Стек технологий
- Python 3.11
- aiogram 3.x (Telegram Bot Framework)
- SQLite (через aiosqlite) — лёгкая встроенная БД
- geopy — расчёт расстояний между координатами
- APScheduler — автоматическое истечение объявлений

## Схема базы данных

### Таблица `users`
| Поле | Тип | Описание |
|------|-----|---------|
| id | INTEGER PK | Telegram user_id |
| username | TEXT | @username в Telegram |
| first_name | TEXT | Имя |
| age | INTEGER | Возраст (опционально) |
| bio | TEXT | О себе |
| rating | REAL | Средний рейтинг (0-5) |
| reviews_count | INTEGER | Кол-во отзывов |
| created_at | DATETIME | Дата регистрации |
| is_banned | INTEGER | Бан флаг |

### Таблица `listings` (объявления)
| Поле | Тип | Описание |
|------|-----|---------|
| id | INTEGER PK | ID объявления |
| user_id | INTEGER FK | Автор |
| title | TEXT | Заголовок (напр. "Виски + пиво") |
| description | TEXT | Описание |
| drinks | TEXT | Что есть из выпивки |
| snacks | TEXT | Что есть из закуски |
| latitude | REAL | Широта |
| longitude | REAL | Долгота |
| location_name | TEXT | Название места (опционально) |
| max_people | INTEGER | Макс. кол-во человек |
| status | TEXT | active / closed / expired |
| created_at | DATETIME | Дата создания |
| expires_at | DATETIME | Дата истечения (по умолчанию +4 часа) |

### Таблица `join_requests` (отклики)
| Поле | Тип | Описание |
|------|-----|---------|
| id | INTEGER PK | ID отклика |
| listing_id | INTEGER FK | ID объявления |
| from_user_id | INTEGER FK | Кто откликнулся |
| message | TEXT | Сообщение при отклике |
| status | TEXT | pending / accepted / rejected |
| created_at | DATETIME | Дата отклика |

### Таблица `meetings` (встречи)
| Поле | Тип | Описание |
|------|-----|---------|
| id | INTEGER PK | ID встречи |
| listing_id | INTEGER FK | ID объявления |
| host_id | INTEGER FK | Хозяин (автор объявления) |
| guest_id | INTEGER FK | Гость |
| status | TEXT | active / completed / cancelled |
| created_at | DATETIME | Дата создания |
| completed_at | DATETIME | Дата завершения |

### Таблица `reviews` (отзывы — НЕРЕДАКТИРУЕМЫЕ)
| Поле | Тип | Описание |
|------|-----|---------|
| id | INTEGER PK | ID отзыва |
| meeting_id | INTEGER FK | ID встречи |
| from_user_id | INTEGER FK | Кто оставил |
| to_user_id | INTEGER FK | О ком отзыв |
| rating | INTEGER | Оценка 1-5 |
| text | TEXT | Текст отзыва |
| created_at | DATETIME | Дата — НЕЛЬЗЯ изменить после записи |

## Основные сценарии (FSM состояния)

### Создание объявления
1. /post → ввод заголовка → описание → что пить → закуска → геолокация → подтверждение

### Поиск объявлений
1. /find → отправка геолокации → список объявлений в радиусе 5 км → просмотр → отклик

### Завершение встречи и отзывы
1. /meetings → выбор встречи → /complete → обе стороны оставляют отзыв (обязательно)

## Команды бота
- /start — регистрация / главное меню
- /profile — мой профиль
- /post — создать объявление
- /mylistings — мои объявления
- /find — найти собутыльника рядом
- /meetings — мои встречи
- /reviews — мои отзывы
- /help — помощь
