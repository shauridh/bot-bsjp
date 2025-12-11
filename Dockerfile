# Ganti dari 3.9-slim ke 3.11-slim
FROM python:3.11-slim

# Set Timezone Jakarta
ENV TZ=Asia/Jakarta
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app
COPY . .

# Upgrade pip dulu biar pembacaan library lebih pintar
RUN pip install --upgrade pip

# Install library
RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
