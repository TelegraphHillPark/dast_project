# Руководство по настройке и запуску дистрибутива ПО — DAST Analyzer

## 1. Общие сведения

Настоящее руководство описывает порядок развёртывания и запуска системы DAST Analyzer на сервере эксплуатации под управлением операционной системы Ubuntu 22.04 LTS. Все компоненты системы функционируют в виде Docker-контейнеров, управляемых посредством Docker Compose.

---

## 2. Требования к серверу эксплуатации

| Параметр | Минимальные требования |
|---|---|
| Операционная система | Ubuntu 22.04 LTS (64-bit) |
| Процессор | 2 ядра, тактовая частота от 2 ГГц |
| Оперативная память | 4 ГБ |
| Дисковое пространство | 20 ГБ |
| Сетевой интерфейс | Публичный IPv4-адрес |
| Открытые порты | 80/tcp, 443/tcp, 8888/tcp |

---

## 3. Требования к программному обеспечению

На сервере эксплуатации должно быть установлено следующее программное обеспечение:

- Docker Engine версии 24.0 или выше;
- Docker Compose Plugin версии 2.20 или выше;
- Git версии 2.34 или выше.

---

## 4. Установка Docker

```bash
# Загрузка и выполнение официального скрипта установки Docker
curl -fsSL https://get.docker.com | sh

# Включение автоматического запуска Docker при старте системы
systemctl enable --now docker

# Проверка корректности установки
docker --version
docker compose version
```

---

## 5. Подготовка сервера эксплуатации

### 5.1 Создание непривилегированного пользователя

```bash
# Создание пользователя для эксплуатации приложения
adduser deploy
usermod -aG docker deploy

# Переключение на созданного пользователя
su - deploy
```

### 5.2 Клонирование репозитория

```bash
git clone https://github.com/<организация>/<репозиторий>.git /home/deploy/dast
cd /home/deploy/dast
```

---

## 6. Настройка переменных окружения

```bash
cp .env.example .env
nano .env
```

В файле `.env` необходимо указать следующие параметры:

| Параметр | Описание |
|---|---|
| `POSTGRES_PASSWORD` | Пароль к базе данных PostgreSQL |
| `REDIS_PASSWORD` | Пароль к серверу Redis |
| `SECRET_KEY` | Секретный ключ для подписи JWT-токенов (рекомендуется длина 64 символа) |
| `DOMAIN` | Доменное имя или IP-адрес сервера |
| `FRONTEND_URL` | Публичный URL приложения (например: `https://example.com`) |
| `ALLOWED_ORIGINS` | Список разрешённых источников CORS через запятую |
| `GITHUB_CLIENT_ID` | Client ID приложения GitHub OAuth (если используется) |
| `GITHUB_CLIENT_SECRET` | Client Secret приложения GitHub OAuth (если используется) |

Генерация `SECRET_KEY`:

```bash
openssl rand -hex 32
```

**Примечание по переменной `DOMAIN`:**

| Значение | Поведение |
|---|---|
| IP-адрес (например: `1.2.3.4`) | Nginx генерирует самоподписанный сертификат |
| IP-адрес с суффиксом `.nip.io` (например: `1.2.3.4.nip.io`) | Возможно получение сертификата Let's Encrypt |
| Доменное имя (например: `example.com`) | Полноценная конфигурация с сертификатом Let's Encrypt |

---

## 7. Первоначальный запуск системы

```bash
# Сборка и запуск всех контейнеров
docker compose -f docker-compose.prod.yml --env-file .env up -d --build

# Ожидание запуска сервиса backend (30–60 секунд)
docker compose -f docker-compose.prod.yml logs -f backend
```

### 7.1 Применение миграций базы данных

```bash
docker compose -f docker-compose.prod.yml --env-file .env \
    exec backend alembic upgrade head
```

### 7.2 Создание учётной записи администратора

```bash
docker compose -f docker-compose.prod.yml --env-file .env \
    exec backend python -c "
import asyncio
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.core.uuid7 import uuid7_str

async def run():
    async with AsyncSessionLocal() as s:
        s.add(User(
            id=uuid7_str(),
            email='admin@example.com',
            username='admin',
            hashed_password=hash_password('SECURE_PASSWORD'),
            role=UserRole.admin,
            is_active=True
        ))
        await s.commit()
        print('Учётная запись администратора создана.')

asyncio.run(run())
"
```

Значения `admin@example.com` и `SECURE_PASSWORD` необходимо заменить на фактические.

---

## 8. Получение TLS-сертификата Let's Encrypt

Данный раздел применим при использовании доменного имени или адреса `*.nip.io`.

```bash
# Получение сертификата (заменить DOMAIN и EMAIL на фактические значения)
docker compose -f docker-compose.prod.yml --env-file .env \
    run --rm --entrypoint certbot certbot \
    certonly --webroot -w /var/www/certbot \
    -d DOMAIN \
    --email EMAIL \
    --agree-tos --no-eff-email

# Перезапуск nginx для применения сертификата
docker compose -f docker-compose.prod.yml --env-file .env restart nginx
```

**Настройка автоматического обновления сертификата.** Необходимо добавить задание в планировщик cron:

```bash
crontab -e
```

Добавить следующую строку:

```
0 3 * * * cd /home/deploy/dast && docker compose -f docker-compose.prod.yml --env-file .env exec -T certbot certbot renew --webroot -w /var/www/certbot --quiet && docker compose -f docker-compose.prod.yml --env-file .env exec -T nginx nginx -s reload
```

Задание выполняется ежедневно в 03:00. Certbot производит обновление только при наличии менее 30 суток до истечения срока действия сертификата.

---

## 9. Настройка GitHub OAuth (опционально)

Для активации возможности входа через GitHub необходимо:

1. Создать OAuth Application по адресу: `https://github.com/settings/developers → OAuth Apps → New OAuth App`.
2. Указать следующие параметры:
   - **Homepage URL:** `https://DOMAIN`
   - **Authorization callback URL:** `https://DOMAIN/api/auth/oauth/github/callback`
3. Сохранить `Client ID` и `Client Secret`.
4. Прописать значения в `.env`:
   ```
   GITHUB_CLIENT_ID=<значение>
   GITHUB_CLIENT_SECRET=<значение>
   ```
5. Перезапустить контейнер backend.

---

## 10. Проверка работоспособности

После успешного запуска система доступна по следующим адресам:

| Адрес | Описание |
|---|---|
| `https://DOMAIN` | Основной веб-интерфейс |
| `https://DOMAIN/api/docs` | Интерактивная документация REST API (Swagger UI) |
| `https://DOMAIN/health` | Эндпоинт проверки состояния |
| `http://DOMAIN:8888` | Уязвимое веб-приложение DVWA (для тестирования) |

---

## 11. Настройка CI/CD (непрерывная интеграция и развёртывание)

### 11.1 Переменные GitHub Actions Secrets

В репозитории GitHub необходимо настроить следующие секреты (`Settings → Secrets and variables → Actions`):

| Секрет | Описание |
|---|---|
| `VDS_HOST` | IP-адрес сервера эксплуатации |
| `VDS_USER` | Имя пользователя SSH |
| `VDS_SSH_KEY` | Приватный SSH-ключ (полное содержимое файла) |
| `VDS_PORT` | Порт SSH |
| `VDS_DEPLOY_PATH` | Путь к директории проекта на сервере |
| `SONAR_TOKEN` | Токен для SonarCloud SAST |

### 11.2 Автоматическое развёртывание

При отправке изменений в ветку `main` автоматически запускается pipeline, выполняющий:
1. Запуск тестов backend (pytest).
2. Сборку и проверку типов frontend (TypeScript).
3. Статический анализ кода (SonarCloud).
4. Сканирование Docker-образа (Trivy).
5. Развёртывание на сервере эксплуатации по SSH.

### 11.3 Выпуск версионированного дистрибутива

Создание нового релиза выполняется посредством Git-тега:

```bash
git tag v1.0.0
git push origin v1.0.0
```

При создании тега pipeline дополнительно выполняет:
- публикацию Docker-образов в GitHub Container Registry (GHCR);
- создание GitHub Release с автоматически сгенерированными примечаниями к выпуску.

---

## 12. Основные команды управления

```bash
# Просмотр статуса контейнеров
docker compose -f docker-compose.prod.yml ps

# Просмотр журналов конкретного сервиса
docker compose -f docker-compose.prod.yml logs -f <имя_сервиса>

# Перезапуск отдельного сервиса
docker compose -f docker-compose.prod.yml restart <имя_сервиса>

# Остановка всех контейнеров
docker compose -f docker-compose.prod.yml down

# Создание резервной копии базы данных
docker compose -f docker-compose.prod.yml exec db \
    pg_dump -U dast dast > backup_$(date +%Y%m%d_%H%M%S).sql

# Очистка неиспользуемых образов
docker image prune -f
```

---

## 13. Устранение типовых неисправностей

| Симптом | Возможная причина | Действие |
|---|---|---|
| Контейнер backend не запускается | Ошибка подключения к PostgreSQL | Убедиться, что контейнер `db` запущен и принимает соединения (`docker compose logs db`) |
| Ошибка 502 Bad Gateway в браузере | Контейнер backend не отвечает | Проверить журналы: `docker compose logs backend` |
| Предупреждение браузера о сертификате | Используется самоподписанный сертификат | Получить сертификат Let's Encrypt согласно разделу 8 |
| Ошибка применения миграций | БД недоступна или схема повреждена | Проверить переменную `DATABASE_URL` в `.env` |
