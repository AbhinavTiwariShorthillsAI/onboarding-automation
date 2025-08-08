from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import UploadedDocument, ExtractedFields, ProcessingLog


@admin.register(UploadedDocument)
class UploadedDocumentAdmin(admin.ModelAdmin):
    list_display = ['name', 'document_type', 'status', 'file_size_display', 'uploaded_at', 'view_link']
    list_filter = ['status', 'document_type', 'uploaded_at']
    search_fields = ['name', 'file']
    readonly_fields = ['uploaded_at', 'updated_at', 'file_size', 'mime_type', 'processing_time']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'document_type', 'file', 'status')
        }),
        ('File Information', {
            'fields': ('file_size', 'mime_type'),
            'classes': ('collapse',)
        }),
        ('Processing Information', {
            'fields': ('raw_text', 'processing_time', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('uploaded_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def file_size_display(self, obj):
        if obj.file_size:
            # Convert to MB for display
            size_mb = obj.file_size / (1024 * 1024)
            return f"{size_mb:.2f} MB"
        return "Unknown"
    file_size_display.short_description = "File Size"
    
    def view_link(self, obj):
        url = reverse('document_detail', args=[obj.id])
        return format_html('<a href="{}" target="_blank">View</a>', url)
    view_link.short_description = "Actions"


@admin.register(ExtractedFields)
class ExtractedFieldsAdmin(admin.ModelAdmin):
    list_display = ['document_name', 'full_name', 'email', 'phone_number', 'is_verified', 'created_at']
    list_filter = ['is_verified', 'created_at', 'verified_at']
    search_fields = ['full_name', 'email', 'phone_number', 'pan_number', 'aadhaar_number']
    readonly_fields = ['created_at', 'updated_at', 'verified_at']
    
    fieldsets = (
        ('Document', {
            'fields': ('document',)
        }),
        ('Personal Information', {
            'fields': ('full_name', 'date_of_birth', 'email', 'phone_number')
        }),
        ('Government IDs', {
            'fields': ('pan_number', 'aadhaar_number')
        }),
        ('Address Information', {
            'fields': ('address_line_1', 'address_line_2', 'city', 'state', 'pincode')
        }),
        ('Bank Details', {
            'fields': ('bank_name', 'account_number', 'ifsc_code')
        }),
        ('Additional Data', {
            'fields': ('additional_fields',),
            'classes': ('collapse',)
        }),
        ('Verification', {
            'fields': ('is_verified', 'verified_by', 'verified_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def document_name(self, obj):
        return obj.document.name
    document_name.short_description = "Document"
    document_name.admin_order_field = 'document__name'


@admin.register(ProcessingLog)
class ProcessingLogAdmin(admin.ModelAdmin):
    list_display = ['document_name', 'level', 'step', 'message_short', 'created_at']
    list_filter = ['level', 'step', 'created_at']
    search_fields = ['document__name', 'message', 'step']
    readonly_fields = ['created_at']
    
    def document_name(self, obj):
        return obj.document.name
    document_name.short_description = "Document"
    document_name.admin_order_field = 'document__name'
    
    def message_short(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_short.short_description = "Message"
    
    def has_add_permission(self, request):
        # Logs are created automatically, don't allow manual creation
        return False


# Customize admin site headers
admin.site.site_header = "Onboarding Automation Admin"
admin.site.site_title = "Onboarding Admin"
admin.site.index_title = "Document Processing Management"
