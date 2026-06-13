from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('video_feed', views.video_feed, name='video_feed'),
    path('prediction_data', views.prediction_data, name='prediction_data'),
    path('toggle_camera', views.toggle_camera, name='toggle_camera'),
    path('toggle_voice', views.toggle_voice, name='toggle_voice'),
    path('capture_screenshot', views.capture_screenshot, name='capture_screenshot'),
    path('speak', views.speak, name='speak'),
]
