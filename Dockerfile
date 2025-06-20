# Usa imagem com Python 3.12 para evitar problemas com pacotes como pandas
FROM python:3.12-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia os arquivos de dependência para o container
COPY requirements.txt .

# Instala dependências do sistema necessárias para compilar numpy, pandas etc.
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && apt-get remove -y build-essential gcc g++ \
    && apt-get autoremove -y \
    && apt-get clean

# Copia o restante da aplicação para o container
COPY . .

# Expõe a porta usada pela aplicação
EXPOSE 8000

# Comando para iniciar sua aplicação
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
