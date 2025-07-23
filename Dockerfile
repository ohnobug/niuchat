FROM python:3.10-slim-bullseye

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

EXPOSE 9000

CMD sh -c "python try_connect.py && python try_init_db.py && gunicorn main:app --workers $((1 * $(nproc) + 1)) --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:9000"
