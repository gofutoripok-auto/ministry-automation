FROM --platform=linux/amd64 python:3.13-slim
WORKDIR /app
COPY . /app
RUN pip install -r --no-cache-dir requirements.txt
EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
