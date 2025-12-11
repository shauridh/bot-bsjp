# Gunakan Python 3.10 (Versi paling stabil untuk saham/keuangan)
FROM python:3.10-slim

# Set Timezone Jakarta
ENV TZ=Asia/Jakarta
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app
COPY . .

# UPDATE PENTING: Install Git agar bisa download library dari GitHub
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install library
RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
