FROM python:3.6-alpine

RUN pip install Django

ADD project /opt/project/

WORKDIR /opt/project/

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
