from django.urls import path
from . import views

urlpatterns = [
    # Main pages
    path('', views.home, name='home'),
    path('upload/', views.upload_document, name='upload_document'),
    path('documents/', views.document_list, name='document_list'),
    path('documents/<int:document_id>/', views.document_detail, name='document_detail'),
    path('documents/<int:document_id>/review/', views.review_fields, name='review_fields'),
    
    # Actions
    path('documents/<int:document_id>/reprocess/', views.reprocess_document, name='reprocess_document'),
    path('documents/<int:document_id>/export/', views.export_fields, name='export_fields'),
    path('documents/<int:document_id>/export-ocr/', views.export_ocr_json, name='export_ocr_json'),
    path('documents/<int:document_id>/download/', views.download_original, name='download_original'),
    
    # System info
    path('gemini-info/', views.gemini_info, name='gemini_info'),
    
    # API endpoints
    path('api/documents/<int:document_id>/status/', views.document_status, name='document_status'),
    path('api/stats/', views.stats_api, name='stats_api'),
] 