# Gunakan Python 3.11 (Paling stabil untuk library keuangan)
FROM python:3.11-slim

# Set Timezone Jakarta
ENV TZ=Asia/Jakarta
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# 1. Install alat download (curl & unzip)
RUN apt-get update && apt-get install -y curl unzip && rm -rf /var/lib/apt/lists/*

# 2. Upgrade pip
RUN pip install --upgrade pip

# 3. Copy requirements dan install dependencies dasar dulu
COPY requirements.txt .
RUN pip install -r requirements.txt

# 4. INSTALASI PANDAS_TA MANUAL (JURUS ANTI GAGAL)
# Download file ZIP development dari GitHub
RUN curl -L https://github.com/twopirllc/pandas-ta/archive/development.zip -o pandas_ta.zip

# Unzip file
RUN unzip pandas_ta.zip

# Install library dari folder hasil unzip
RUN pip install ./pandas-ta-development

# Bersihkan file sampah
RUN rm pandas_ta.zip && rm -rf pandas-ta-development

# 5. Copy sisa kode bot (bot.py)
COPY . .

CMD ["python", "bot.py"]
