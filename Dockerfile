# Gunakan Python 3.11 (Stabil & Kompatibel)
FROM python:3.11-slim

# Set Timezone Jakarta
ENV TZ=Asia/Jakarta
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app
COPY . .

# Upgrade pip
RUN pip install --upgrade pip

# Install library dari requirements.txt
RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
