FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /workspace/app/streamlit

COPY app/streamlit/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/streamlit ./ 
COPY app/streamlit/container-entrypoint.sh /usr/local/bin/container-entrypoint.sh

RUN chmod +x /usr/local/bin/container-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/container-entrypoint.sh"]
