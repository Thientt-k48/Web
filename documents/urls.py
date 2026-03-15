from django.urls import path
from .views import DocumentListView, DocumentUploadView, DocumentDeleteView, DocumentCancelView, DocumentProcessView

urlpatterns = [
    path('', DocumentListView.as_view(), name='doc-list'),          # /api/docs
    path('upload/', DocumentUploadView.as_view(), name='document-upload'), # /api/docs/upload
    path('delete/<str:pk>/', DocumentDeleteView.as_view(), name='doc-delete'), # /api/docs/<id>delete
    path('process/<str:doc_id>/', DocumentProcessView.as_view(), name='doc-process'),
    path('cancel/<str:pk>/', DocumentCancelView.as_view(), name='doc-cancel'),
]