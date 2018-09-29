FROM python:alpine

RUN pip install Django

ADD project /opt/project/

WORKDIR /opt/project/

CMD ["python", "manage.py", "runserver"]
