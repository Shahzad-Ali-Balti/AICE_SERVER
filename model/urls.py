from django.urls import path
from .views import HumeAudioUploadView

urlpatterns = [
    path('hume/', HumeAudioUploadView.as_view(), name='upload-audio'),
]
