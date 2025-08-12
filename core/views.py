import os
import time
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.core.files.storage import default_storage
from django.conf import settings
import mimetypes
import re

from .models import UploadedDocument, ExtractedFields, ProcessingLog
from .forms import DocumentUploadForm, ExtractedFieldsForm
from .forms import MultiDocumentUploadForm
from .ocr_utils import extract_text_from_file, detect_file_type
from .parser_utils import FieldExtractor

logger = logging.getLogger(__name__)


def home(request):
    """
    Home page showing recent uploads and quick stats
    """
    recent_documents = UploadedDocument.objects.all()[:5]
    
    stats = {
        'total_documents': UploadedDocument.objects.count(),
        'processed_documents': UploadedDocument.objects.filter(status='completed').count(),
        'pending_documents': UploadedDocument.objects.filter(status__in=['uploaded', 'processing']).count(),
        'error_documents': UploadedDocument.objects.filter(status='error').count(),
    }
    
    context = {
        'recent_documents': recent_documents,
        'stats': stats,
    }
    
    return render(request, 'core/home.html', context)


def upload_document(request):
    """
    Handle document upload and initiate processing
    """
    if request.method == 'POST':
        # If multiple files are posted, prefer the multi form path
        if request.FILES.getlist('files'):
            multi_form = MultiDocumentUploadForm(request.POST, request.FILES)
            if multi_form.is_valid():
                created_docs = []
                files = request.FILES.getlist('files')
                doc_type = multi_form.cleaned_data['document_type']
                name_prefix = multi_form.cleaned_data.get('name_prefix') or ''
                for f in files:
                    try:
                        document = UploadedDocument(
                            document_type=doc_type,
                            file=f,
                        )
                        # Determine name
                        base_name = f.name.rsplit('.', 1)[0]
                        document.name = f"{name_prefix}{base_name}" if name_prefix else base_name
                        document.file_size = f.size
                        # Delay mime_type detection until file is saved to disk
                        document.save()
                        document.mime_type = detect_file_type(document.file.path)
                        document.save(update_fields=['mime_type'])

                        ProcessingLog.objects.create(
                            document=document,
                            level='info',
                            message=f'Document uploaded successfully: {document.name}',
                            step='upload'
                        )
                        created_docs.append(document)
                    except Exception as e:
                        logger.error(f"Error saving uploaded file {f.name}: {e}")
                        messages.error(request, f"Failed to save {f.name}: {e}")

                # Process each created document
                for d in created_docs:
                    try:
                        process_document(d.id)
                    except Exception as e:
                        logger.error(f"Error processing document {d.id}: {e}")
                        messages.warning(request, f'Uploaded {d.name} but processing failed. You can retry later.')

                if len(created_docs) == 1:
                    messages.success(request, f'Uploaded and queued 1 document.')
                    return redirect('document_detail', document_id=created_docs[0].id)
                elif len(created_docs) > 1:
                    messages.success(request, f'Uploaded and queued {len(created_docs)} documents.')
                    return redirect('document_list')
        
        # Fallback to single-file form
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                document = form.save(commit=False)
                if document.file:
                    document.file_size = document.file.size
                document.save()
                document.mime_type = detect_file_type(document.file.path)
                # Auto name
                if not document.name:
                    document.name = document.file.name.rsplit('.', 1)[0]
                document.save()

                ProcessingLog.objects.create(
                    document=document,
                    level='info',
                    message=f'Document uploaded successfully: {document.name}',
                    step='upload'
                )

                messages.success(request, f'Document "{document.name}" uploaded successfully!')
                try:
                    process_document(document.id)
                    return redirect('document_detail', document_id=document.id)
                except Exception as e:
                    logger.error(f"Error processing document {document.id}: {e}")
                    messages.warning(request, 'Document uploaded but processing failed. You can retry later.')
                    return redirect('document_detail', document_id=document.id)
            except Exception as e:
                logger.error(f"Error uploading document: {e}")
                messages.error(request, f'Error uploading document: {str(e)}')
    else:
        form = DocumentUploadForm()
        multi_form = MultiDocumentUploadForm()

    return render(request, 'core/upload_form.html', {'form': form, 'multi_form': multi_form})


def document_list(request):
    """
    List all uploaded documents with filtering
    """
    documents = UploadedDocument.objects.all()
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        documents = documents.filter(status=status_filter)
    
    # Filter by document type
    type_filter = request.GET.get('type')
    if type_filter:
        documents = documents.filter(document_type=type_filter)
    
    context = {
        'documents': documents,
        'status_choices': UploadedDocument.STATUS_CHOICES,
        'type_choices': UploadedDocument.DOCUMENT_TYPES,
        'current_status': status_filter,
        'current_type': type_filter,
    }
    
    return render(request, 'core/document_list.html', context)


def document_detail(request, document_id):
    """
    Show document details and extracted fields
    """
    document = get_object_or_404(UploadedDocument, id=document_id)
    
    # Get extracted fields if they exist
    extracted_fields = None
    try:
        extracted_fields = document.extracted_fields
    except ExtractedFields.DoesNotExist:
        pass
    
    # Get processing logs
    logs = document.logs.all()[:10]  # Last 10 logs
    
    context = {
        'document': document,
        'extracted_fields': extracted_fields,
        'logs': logs,
    }
    
    return render(request, 'core/document_detail.html', context)


def review_fields(request, document_id):
    """
    Allow users to review and edit extracted fields
    """
    try:
        document = UploadedDocument.objects.get(id=document_id)
        
        # Get or create extracted fields
        extracted_fields, created = ExtractedFields.objects.get_or_create(
            document=document
        )
        
        if request.method == 'POST':
            form = ExtractedFieldsForm(request.POST, instance=extracted_fields)
            
            if form.is_valid():
                # Save the standard form fields
                form.save()
                
                # Handle additional dynamic fields from the form
                additional_fields = extracted_fields.get_additional_fields()
                updated_additional = {}
                
                # Process additional fields from POST data
                for key, value in request.POST.items():
                    if key.startswith('additional_'):
                        field_name = key[11:]  # Remove 'additional_' prefix
                        if value.strip():  # Only save non-empty values
                            updated_additional[field_name] = value.strip()
                
                # Merge with existing additional fields
                additional_fields.update(updated_additional)
                extracted_fields.set_additional_fields(additional_fields)
                
                # Mark as verified
                extracted_fields.is_verified = True
                extracted_fields.verified_by = request.user if request.user.is_authenticated else None
                extracted_fields.verified_at = timezone.now()
                extracted_fields.save()
                
                # Update document status
                document.status = 'completed'
                document.save()
                
                # Log the verification
                total_fields = extracted_fields.get_field_count()
                ProcessingLog.objects.create(
                    document=document,
                    level='info',
                    message=f'Fields reviewed and verified by user. Total fields: {total_fields}',
                    step='verification'
                )
                
                messages.success(request, f'Fields have been reviewed and verified successfully! Total fields processed: {total_fields}')
                return redirect('document_detail', document_id=document.id)
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            form = ExtractedFieldsForm(instance=extracted_fields)
        
        context = {
            'document': document,
            'form': form,
            'extracted_fields': extracted_fields,
        }
        
        return render(request, 'core/review_fields.html', context)
        
    except UploadedDocument.DoesNotExist:
        messages.error(request, 'Document not found.')
        return redirect('document_list')


def process_document(document_id):
    """
    Process document: OCR only (no field extraction). Store raw_text and finish.
    """
    import time
    start_time = time.time()
    
    try:
        document = UploadedDocument.objects.get(id=document_id)
        document.status = 'processing'
        document.save()

        ProcessingLog.objects.create(
            document=document,
            level='info',
            message='Starting OCR-only processing with Google Gemini',
            step='start'
        )

        try:
            file_path = document.file.path
            raw_text, mime_type = extract_text_from_file(file_path)

            document.raw_text = raw_text
            document.mime_type = mime_type
            document.processing_time = time.time() - start_time

            ProcessingLog.objects.create(
                document=document,
                level='info',
                message=f'OCR extracted {len(raw_text)} characters in {document.processing_time:.2f}s',
                step='ocr_extraction'
            )
        except Exception as e:
            error_message = str(e)
            document.status = 'error'
            document.error_message = error_message
            document.processing_time = time.time() - start_time
            document.save()
            ProcessingLog.objects.create(
                document=document,
                level='error',
                message=f'OCR failed: {error_message}',
                step='ocr_extraction'
            )
            return

        # Finish without field extraction
        document.status = 'completed'
        document.save()
        ProcessingLog.objects.create(
            document=document,
            level='info',
            message='Processing completed (OCR-only)',
            step='completion'
        )
    except UploadedDocument.DoesNotExist:
        logger.error(f"Document {document_id} not found")
    except Exception as e:
        logger.error(f"Unexpected error processing document {document_id}: {e}")
        try:
            document = UploadedDocument.objects.get(id=document_id)
            document.status = 'error'
            document.error_message = f'Unexpected error: {str(e)}'
            document.processing_time = time.time() - start_time
            document.save()
            ProcessingLog.objects.create(
                document=document,
                level='error',
                message=f'Unexpected processing error: {str(e)}',
                step='error'
            )
        except:
            pass


@require_http_methods(["POST"])
def reprocess_document(request, document_id):
    """
    Reprocess a document (AJAX endpoint)
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        # Reset status
        document.status = 'uploaded'
        document.error_message = ''
        document.save()
        
        # Start processing
        process_document(document_id)
        
        return JsonResponse({
            'success': True,
            'message': 'Document reprocessing started successfully'
        })
        
    except Exception as e:
        logger.error(f"Error reprocessing document {document_id}: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


def export_fields(request, document_id):
    """
    Export JSON. Prefer OCR raw_text JSON; fallback to structured fields only if no JSON is parseable.
    """
    document = get_object_or_404(UploadedDocument, id=document_id)

    # Prefer OCR raw_text JSON (robust parsing)
    export_payload = _try_parse_json_from_text(document.raw_text) if document.raw_text else None

    if export_payload is None:
        # Fallback to structured fields
        if hasattr(document, 'extracted_fields'):
            export_payload = document.extracted_fields.to_dict()
        else:
            export_payload = {}

    response = HttpResponse(
        json.dumps(export_payload, ensure_ascii=False, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="document_{document_id}_fields.json"'
    return response


def export_ocr_json(request, document_id):
    """Export the OCR raw_text as JSON. If parseable JSON is found, return it; otherwise wrap as {"text": raw_text}."""
    document = get_object_or_404(UploadedDocument, id=document_id)
    raw = document.raw_text or ""
    payload = _try_parse_json_from_text(raw)
    if payload is None:
        payload = {"text": raw}
    response = HttpResponse(
        json.dumps(payload, ensure_ascii=False, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="document_{document_id}_ocr.json"'
    return response


def download_original(request, document_id):
    """
    Download the original uploaded file
    """
    document = get_object_or_404(UploadedDocument, id=document_id)
    
    try:
        file_path = document.file.path
        
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type=document.mime_type or 'application/octet-stream')
                response['Content-Disposition'] = f'attachment; filename="{document.file.name}"'
                return response
        else:
            messages.error(request, 'Original file not found.')
            return redirect('document_detail', document_id=document_id)
            
    except Exception as e:
        logger.error(f"Error downloading file for document {document_id}: {e}")
        messages.error(request, f'Error downloading file: {str(e)}')
        return redirect('document_detail', document_id=document_id)


@require_http_methods(["GET"])
def document_status(request, document_id):
    """
    Get document processing status (AJAX endpoint)
    """
    try:
        document = get_object_or_404(UploadedDocument, id=document_id)
        
        data = {
            'status': document.status,
            'error_message': document.error_message,
            'processing_time': document.processing_time,
        }
        
        # If completed, include field count
        if document.status == 'completed':
            try:
                fields = document.extracted_fields
                field_dict = fields.to_dict()
                filled_fields = sum(1 for v in field_dict.values() if v)
                data['extracted_fields_count'] = filled_fields
            except ExtractedFields.DoesNotExist:
                data['extracted_fields_count'] = 0
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


def stats_api(request):
    """
    API endpoint to get dashboard statistics
    """
    from .ocr_utils import get_gemini_usage_info
    
    stats = {
        'total_documents': UploadedDocument.objects.count(),
        'processed_documents': UploadedDocument.objects.filter(status='completed').count(),
        'pending_documents': UploadedDocument.objects.filter(status__in=['uploaded', 'processing']).count(),
        'error_documents': UploadedDocument.objects.filter(status='error').count(),
        'ocr_engine': 'Google Gemini Pro',
        'gemini_info': get_gemini_usage_info()
    }
    
    return JsonResponse(stats)


def gemini_info(request):
    """
    Display Google Gemini API usage information and status
    """
    from .ocr_utils import validate_ocr_requirements, get_gemini_usage_info
    
    # Check if Gemini is properly configured
    is_configured = validate_ocr_requirements()
    usage_info = get_gemini_usage_info()
    
    # Get recent processing stats
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    today_documents = UploadedDocument.objects.filter(uploaded_at__date=today).count()
    yesterday_documents = UploadedDocument.objects.filter(uploaded_at__date=yesterday).count()
    
    recent_errors = ProcessingLog.objects.filter(
        level='error',
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).order_by('-created_at')[:10]
    
    context = {
        'is_configured': is_configured,
        'usage_info': usage_info,
        'today_documents': today_documents,
        'yesterday_documents': yesterday_documents,
        'recent_errors': recent_errors,
        'api_key_configured': bool(getattr(settings, 'GOOGLE_AI_API_KEY', None)),
    }
    
    return render(request, 'core/gemini_info.html', context)
    