#!/usr/bin/env bash
# Установка и обновление сайта на Ubuntu 22.04+. Запуск на сервере:
#   sudo bash /var/www/kindergarten-site/deploy/deploy.sh
# Первый запуск ставит пакеты и создаёт backend/.env, базу, службу gunicorn и сайт nginx.
# Повторный (после загрузки новой версии) делает копию базы, обновляет зависимости, миграции и статику.
# backend/.env, база, загруженные файлы и настройки nginx (в том числе SSL от certbot) не перезаписываются.
set -euo pipefail

APP=/var/www/kindergarten-site
cd "$APP"

step() { printf '\n== %s\n' "$*"; }
manage() { sudo -u www-data "$APP/venv/bin/python" "$APP/backend/manage.py" "$@"; }

if [ ! -f frontend/dist/index.html ]; then
  echo "Нет frontend/dist/index.html: соберите сайт (npm run build) и загрузите архив заново." >&2
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
  echo "Нужен Python 3.10 или новее (Ubuntu 22.04+)." >&2
  exit 1
fi

step "Системные пакеты"
apt-get update -q
apt-get install -y -q python3-venv nginx certbot python3-certbot-nginx

step "Python-окружение"
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r backend/requirements.txt

step "Настройки и права"
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  secret=$(venv/bin/python -c "import secrets; print(secrets.token_urlsafe(50))")
  sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$secret|" backend/.env
  echo "Создан backend/.env со случайным секретным ключом"
fi
mkdir -p media backups
chmod -R u=rwX,go=rX backend deploy frontend  # архив, собранный в Windows, приносит права 666/777
chown -R www-data:www-data backend media
chmod 600 backend/.env
chmod 700 backups

step "База данных и статика"
if [ -f backend/db.sqlite3 ]; then
  copy="backups/db-$(date +%Y%m%d-%H%M%S).sqlite3"
  venv/bin/python -c "import sqlite3, sys; sqlite3.connect(sys.argv[1]).backup(sqlite3.connect(sys.argv[2]))" \
    backend/db.sqlite3 "$copy"
  echo "Копия базы перед обновлением: $APP/$copy"
fi
manage migrate --noinput
manage setup_site
manage collectstatic --noinput

step "Служба gunicorn"
cp deploy/kindergarten-site.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable kindergarten-site
systemctl restart kindergarten-site

step "nginx"
if [ ! -f /etc/nginx/sites-available/kindergarten-site ]; then
  cp deploy/nginx-kindergarten-site.conf /etc/nginx/sites-available/kindergarten-site
  ln -s /etc/nginx/sites-available/kindergarten-site /etc/nginx/sites-enabled/kindergarten-site
  rm -f /etc/nginx/sites-enabled/default
fi
nginx -t
systemctl reload nginx
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow "Nginx Full" >/dev/null
fi

step "Готово"
systemctl is-active kindergarten-site
echo "Если это первая установка:"
echo "  1) администратор:  sudo -u www-data $APP/venv/bin/python $APP/backend/manage.py createsuperuser"
echo "  2) HTTPS (домен уже должен указывать на этот сервер):"
echo "     sudo certbot --nginx -d botakanym.edu.kz -d www.botakanym.edu.kz"
