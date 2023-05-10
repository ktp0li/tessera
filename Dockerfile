FROM python:alpine
LABEL made="with_love"
ENV DB_NAME="postgres" DB_USER="postgres" DB_HOST="postgres" DB_PASS="postgres" DB_PORT="5432"
WORKDIR /app
COPY ./main.py ./requirements.txt /app/
RUN pip install -r requirements.txt
CMD python3 ./main.py