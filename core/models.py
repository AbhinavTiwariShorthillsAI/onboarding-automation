from django.db import models
from django.contrib.auth.models import User
import json


class UploadedDocument(models.Model):
    """Model to store uploaded onboarding documents"""
    
    DOCUMENT_TYPES = [
        ('form', 'Onboarding Form'),
        ('id_proof', 'ID Proof'),
        ('address_proof', 'Address Proof'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]
    
    name = models.CharField(max_length=255, help_text="Original filename")
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='form')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    file_size = models.IntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, null=True, blank=True)
    
    # OCR results
    raw_text = models.TextField(blank=True, help_text="Raw OCR extracted text")
    processing_time = models.FloatField(null=True, blank=True, help_text="Time taken for OCR in seconds")
    error_message = models.TextField(blank=True, help_text="Error message if processing failed")
    
    class Meta:
        ordering = ['-uploaded_at']
        
    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"


class ExtractedFields(models.Model):
    """Model to store extracted and verified field data from documents"""
    
    document = models.OneToOneField(UploadedDocument, on_delete=models.CASCADE, related_name='extracted_fields')
    
    # Personal Information
    full_name = models.CharField(max_length=255, blank=True)
    date_of_birth = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Government IDs
    pan_number = models.CharField(max_length=20, blank=True, help_text="PAN Card Number")
    aadhaar_number = models.CharField(max_length=20, blank=True, help_text="Aadhaar Card Number")
    
    # Address Information
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    
    # Bank Details
    bank_name = models.CharField(max_length=255, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    
    # Additional fields as JSON for flexibility
    additional_fields = models.TextField(blank=True, help_text="JSON data for additional extracted fields")
    
    # Verification status
    is_verified = models.BooleanField(default=False, help_text="Whether the data has been manually verified")
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_additional_fields(self):
        """Return additional fields as a Python dict"""
        if self.additional_fields:
            try:
                return json.loads(self.additional_fields)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_additional_fields(self, data):
        """Set additional fields from a Python dict"""
        self.additional_fields = json.dumps(data)
    
    def to_dict(self):
        """Convert the extracted fields to a dictionary for easy JSON serialization"""
        base_fields = {
            'full_name': self.full_name,
            'date_of_birth': self.date_of_birth,
            'email': self.email,
            'phone_number': self.phone_number,
            'pan_number': self.pan_number,
            'aadhaar_number': self.aadhaar_number,
            'address_line_1': self.address_line_1,
            'address_line_2': self.address_line_2,
            'city': self.city,
            'state': self.state,
            'pincode': self.pincode,
            'bank_name': self.bank_name,
            'account_number': self.account_number,
            'ifsc_code': self.ifsc_code,
            'is_verified': self.is_verified,
        }
        
        # Add additional dynamic fields
        additional = self.get_additional_fields()
        if additional:
            base_fields.update(additional)
            
        # Remove empty values for cleaner output
        return {k: v for k, v in base_fields.items() if v}
    
    def set_all_fields(self, fields_dict):
        """
        Set both standard and additional fields from a dictionary
        """
        # Known model fields
        known_fields = {
            'full_name', 'date_of_birth', 'email', 'phone_number',
            'pan_number', 'aadhaar_number', 'address_line_1', 'address_line_2',
            'city', 'state', 'pincode', 'bank_name', 'account_number', 'ifsc_code'
        }
        
        additional_fields = {}
        
        for field_name, field_value in fields_dict.items():
            if field_name in known_fields and hasattr(self, field_name):
                # Set standard model field
                setattr(self, field_name, field_value)
            else:
                # Store in additional_fields JSON
                additional_fields[field_name] = field_value
        
        # Update additional_fields JSON
        if additional_fields:
            existing_additional = self.get_additional_fields()
            existing_additional.update(additional_fields)
            self.set_additional_fields(existing_additional)
    
    def get_all_fields(self):
        """
        Get all fields including both standard and additional fields
        """
        all_fields = {}
        
        # Add standard fields
        for field in ['full_name', 'date_of_birth', 'email', 'phone_number',
                     'pan_number', 'aadhaar_number', 'address_line_1', 'address_line_2',
                     'city', 'state', 'pincode', 'bank_name', 'account_number', 'ifsc_code']:
            value = getattr(self, field, None)
            if value:
                all_fields[field] = value
        
        # Add additional fields
        additional = self.get_additional_fields()
        if additional:
            all_fields.update(additional)
            
        return all_fields
    
    def get_field_count(self):
        """
        Get total count of extracted fields (both standard and additional)
        """
        standard_count = sum(1 for field in ['full_name', 'date_of_birth', 'email', 'phone_number',
                                           'pan_number', 'aadhaar_number', 'address_line_1', 'address_line_2',
                                           'city', 'state', 'pincode', 'bank_name', 'account_number', 'ifsc_code']
                            if getattr(self, field, None))
        
        additional_count = len(self.get_additional_fields())
        return standard_count + additional_count
    
    class Meta:
        verbose_name = "Extracted Fields"
        verbose_name_plural = "Extracted Fields"
        
    def __str__(self):
        return f"Fields for {self.document.name}"


class ProcessingLog(models.Model):
    """Model to log processing steps and results"""
    
    LOG_LEVELS = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]
    
    document = models.ForeignKey(UploadedDocument, on_delete=models.CASCADE, related_name='logs')
    level = models.CharField(max_length=10, choices=LOG_LEVELS, default='info')
    message = models.TextField()
    step = models.CharField(max_length=100, help_text="Processing step (e.g., 'ocr', 'field_extraction')")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.get_level_display()}: {self.step} - {self.message[:50]}"
