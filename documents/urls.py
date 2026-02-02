from django.urls import path
from .views import DocumentListView, DocumentUploadView, DocumentDeleteView

urlpatterns = [
    path('', DocumentListView.as_view(), name='doc-list'),          # /api/docs
    path('upload', DocumentUploadView.as_view(), name='doc-upload'), # /api/docs/upload
    path('delete/<int:pk>/', DocumentDeleteView.as_view(), name='doc-delete'), # /api/docs/<id>delete
]