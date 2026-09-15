# FlowVault

ระบบจัดการไฟล์ภายในองค์กรด้วย Flask และ MariaDB โดยไฟล์งานอยู่บน Linux host ในโฟลเดอร์จริงเสมอ ส่วน Docker ใช้รัน MariaDB เท่านั้น

## โครงสร้างการทำงาน

```text
Nginx / Caddy (HTTPS)
        |
Gunicorn + Flask (Linux host)
        |---- /srv/flowvault/storage       ไฟล์และ Folder งาน
        |---- /srv/flowvault/recycle-bin   รายการที่ลบชั่วคราว
        |
Docker: MariaDB only (127.0.0.1:13306)
```

ไม่มี service Flask, Recycle Bin หรือพื้นที่ไฟล์อยู่ใน Docker ดังนั้นการ rebuild/recreate MariaDB container จะไม่ย้ายหรือลบไฟล์ใน `storage`

## สิทธิ์ไฟล์

ทุกบัญชีใช้โครงสร้าง Folder กลางเดียวกันใน `FILE_STORAGE_DIR` สิทธิ์ถูกบังคับที่ server ด้วย Permission Tier:

| Tier | สิทธิ์ |
| --- | --- |
| T1 | R, C, N, M, D |
| T2 | R, C, N, M |
| T3 | R, C |
| T4 | R |

R = Preview, C = Download, N = สร้าง/แชร์, M = rename/move/บันทึกทับ และ D = ลบ

## Recycle Bin

- การลบไฟล์หรือ Folder จะย้ายไป `RECYCLE_BIN_DIR` บน host
- กู้คืนได้ภายใน 15 วันโดย `super_admin` หรือ `department_admin`
- systemd timer ลบรายการที่หมดอายุทุกชั่วโมง
- ไฟล์ใน Recycle Bin อยู่นอก `storage` จึงไม่ปรากฏในหน้า My files

## Deploy บน Linux

ตัวอย่างนี้ใช้ project ที่ `/opt/flowvault` และไฟล์งานที่ `/srv/flowvault` เปลี่ยน path ได้ แต่ต้องแก้ให้ตรงกันใน `.env` และ unit files

### 1. ติดตั้ง prerequisites

ต้องมี Docker Engine + Docker Compose plugin, Python 3.12, Nginx หรือ Caddy และสิทธิ์ sudo

```bash
sudo mkdir -p /opt/flowvault /srv/flowvault/storage /srv/flowvault/recycle-bin
sudo useradd --system --home /opt/flowvault --shell /usr/sbin/nologin flowvault
sudo chown -R flowvault:flowvault /opt/flowvault /srv/flowvault
cd /opt/flowvault
```

คัดลอก source code ของโครงการลง `/opt/flowvault` ก่อนทำขั้นตอนถัดไป

### 2. สร้าง environment และตั้งค่า

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
```

แก้ `.env` ให้มีค่าจริง โดยเฉพาะ secret, password และ path ของ host:

```env
FLASK_SECRET_KEY=replace-with-a-long-random-secret
MARIADB_ROOT_PASSWORD=replace-with-a-long-unique-database-password
DB_NAME=db
DB_HOST=127.0.0.1
DB_PORT=13306
ADMIN_EMAILS=admin@example.com

# โฟลเดอร์บน Linux host ไม่ใช่ Docker volume
FILE_STORAGE_DIR=/srv/flowvault/storage
RECYCLE_BIN_DIR=/srv/flowvault/recycle-bin

SESSION_COOKIE_SECURE=1
TRUSTED_PROXY_COUNT=1
```

สร้าง secret ได้ด้วย `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` ห้าม commit `.env` หรือไฟล์ที่มี password/OTP

### 3. เริ่ม MariaDB ด้วย Docker

```bash
docker compose up -d mariadb
docker compose ps
```

MariaDB รับการเชื่อมต่อเฉพาะ `127.0.0.1:13306` และข้อมูล database อยู่ใน Docker volume `mariadb_data` ส่วน `mariadb.sql` จะ import เฉพาะการสร้าง volume ใหม่เท่านั้น

### 4. เปิด Flask เป็น systemd service

ตรวจ path ในไฟล์ใต้ `deploy/` ให้ตรงกับตำแหน่งติดตั้ง แล้วติดตั้ง service:

```bash
sudo cp deploy/flowvault.service /etc/systemd/system/
sudo cp deploy/flowvault-recycle-purge.service /etc/systemd/system/
sudo cp deploy/flowvault-recycle-purge.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now flowvault.service
sudo systemctl enable --now flowvault-recycle-purge.timer
sudo systemctl status flowvault.service
```

Flask จะฟังที่ `127.0.0.1:8000` ผ่าน Gunicorn ไม่เปิดสู่ internet โดยตรง

### 5. ตั้ง Nginx และ HTTPS

ตัวอย่าง Nginx:

```nginx
server {
    listen 80;
    server_name files.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

เปิด HTTPS ด้วย Certbot หรือ Caddy ก่อนใช้งานจริง เพราะ production ใช้ secure session cookie

## ใช้งานและตรวจสอบ

```bash
# Flask service
sudo systemctl status flowvault.service
sudo journalctl -u flowvault.service -f

# Recycle Bin scheduler
systemctl list-timers flowvault-recycle-purge.timer
sudo systemctl start flowvault-recycle-purge.service

# Database container
docker compose ps
docker compose logs --tail=100 mariadb
```

หลังแก้ Python/template:

```bash
sudo systemctl restart flowvault.service
```

## พัฒนาบนเครื่อง

Docker ใช้เฉพาะ database และ Flask รันจาก virtual environment:

```powershell
docker compose up -d mariadb
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

ตั้ง `.env` สำหรับ Windows ให้เป็น:

```env
DB_HOST=127.0.0.1
DB_PORT=13306
FILE_STORAGE_DIR=C:/path/to/FlowVault/storage
RECYCLE_BIN_DIR=C:/path/to/FlowVault/recycle-bin
SESSION_COOKIE_SECURE=0
```

## ตัวแปรสำคัญ

| Variable | ความหมาย |
| --- | --- |
| `FILE_STORAGE_DIR` | โฟลเดอร์กลางที่เก็บไฟล์และ Folder งานจริง |
| `RECYCLE_BIN_DIR` | โฟลเดอร์ที่เก็บรายการลบชั่วคราว 15 วัน |
| `DB_HOST` / `DB_PORT` | MariaDB; ใช้ `127.0.0.1:13306` เมื่อ Docker อยู่เครื่องเดียวกัน |
| `MARIADB_ROOT_PASSWORD` | รหัสผ่าน MariaDB; ต้องเป็น secret |
| `FLASK_SECRET_KEY` | secret สำหรับ session และการเข้ารหัสข้อมูล SMTP |
| `SESSION_COOKIE_SECURE` | `1` สำหรับ HTTPS production, `0` สำหรับ local HTTP |
| `TRUSTED_PROXY_COUNT` | `1` เมื่อมี Nginx/Caddy หนึ่งชั้นอยู่หน้า Gunicorn |

`FOLDER_ROOT` และ `RECYCLE_BIN_PATH` ยังรองรับสำหรับการตั้งค่าเดิม แต่ deployment ใหม่ควรใช้ `FILE_STORAGE_DIR` และ `RECYCLE_BIN_DIR`

## Backup

ต้อง backup ทั้ง storage บน host และ MariaDB:

```bash
tar -C /srv/flowvault -czf flowvault-files-$(date +%F).tar.gz storage recycle-bin
docker compose exec -T mariadb sh -c 'mariadb-dump -uroot -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"' > flowvault-db-$(date +%F).sql
```

อย่าลบ `/srv/flowvault/storage`, `/srv/flowvault/recycle-bin` หรือ Docker volume `mariadb_data` หากยังต้องการข้อมูลเดิม
