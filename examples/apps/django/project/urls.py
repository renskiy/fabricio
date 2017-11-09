from django.conf.urls import url
from django.http import HttpResponse, HttpRequest


def hello_world(request: HttpRequest):
    return HttpResponse('Hello World')


urlpatterns = [
    url('', hello_world),
]
