FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

# sentence-transformers pulls in torch, and on Linux pip defaults to the CUDA
# build (torch itself is ~500MB, plus several hundred MB more of bundled
# nvidia-cu* packages) — massive and pointless for a CPU-only reranker.
# Installing the CPU-only wheel first (from PyTorch's own index) means the
# later `pip install -r requirements.txt` just sees the constraint already
# satisfied and skips it.
RUN pip install --no-cache-dir --default-timeout=180 --retries 10 torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir --default-timeout=180 --retries 10 -r requirements.txt

COPY . .

# SQLite database lives here; mounted as a volume in docker-compose so data
# survives container restarts/rebuilds.
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
