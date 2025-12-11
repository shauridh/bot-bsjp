# Gunakan Python 3.10 (Versi Stabil)
FROM python:3.10-slim

# Set Timezone Jakarta
ENV TZ=Asia/Jakarta
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app
COPY . .

# Upgrade pip
RUN pip install --upgrade pip

# Install library
RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
