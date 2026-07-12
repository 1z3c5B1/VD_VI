# VD AI Project — API-режим

## Что это
Веб-сервер на FastAPI для генерации изображений (FLUX), видео (мультикадровый морфинг) и чата с ИИ (OpenAI/DeepSeek/Claude/Gemini). Всё бесплатно, через Pollinations.ai API.

## Запуск локально
```bash
cd "C:\Users\Вадим\Desktop\VD AI"
pip install -r requirements.txt
python run.py
```
Сайт: http://localhost:8000

## Деплой на Render (бесплатно, работает без ПК)
1. Создать репозиторий на GitHub и залить туда проект
2. Зайти на https://render.com → New Web Service
3. Подключить GitHub репозиторий
4. Render сам найдёт `render.yaml` и настроит всё
5. Готово! Сервер будет работать 24/7

## API Endpoints
- `POST /api/register` — регистрация
- `POST /api/login` — вход
- `GET /api/me` — проверка токена
- `POST /api/chat` — чат с ИИ (модели: openai, deepseek, claude, gemini)
- `POST /api/generate/image` — генерация изображения (FLUX)
- `POST /api/generate/video` — генерация видео (мультикадровый морфинг)
- `GET /api/health` — проверка сервера

## Ключи
- Pollinations API: `sk_TxyHaOVGAzdSY8FIk1bRoAN6dA47TBuO` (в `backend/config.py`)
- Чат и изображения — бесплатно
- Видео — бесплатно (морфинг из FLUX-картинок)

## Структура
```
backend/          # FastAPI сервер + auth + модели
frontend/         # HTML + CSS + JS (дизайн, 4 вкладки)
outputs/          # сгенерированные файлы
users.db          # SQLite с пользователями (создаётся автоматически)
render.yaml       # конфиг для деплоя на Render
.gitignore
requirements.txt
