# Gunakan Python 3.12-slim (Ringan & Support Library Terbaru)
FROM python:3.12-slim

# Set Timezone Server ke Jakarta (Backup)
ENV TZ=Asia/Jakarta
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# WAJIB: Agar log muncul real-time di Coolify tanpa delay
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

# Upgrade pip
RUN pip install --upgrade pip

# Install library
RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
