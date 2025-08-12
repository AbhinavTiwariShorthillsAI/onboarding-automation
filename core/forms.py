from django import forms
from django.core.validators import FileExtensionValidator
from .models import UploadedDocument, ExtractedFields


class DocumentUploadForm(forms.ModelForm):
    """
    Form for uploading onboarding documents
    """
    
    class Meta:
        model = UploadedDocument
        fields = ['name', 'document_type', 'file']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Customize form fields
        self.fields['name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter document name (optional - will use filename if empty)'
        })
        self.fields['name'].required = False
        
        self.fields['document_type'].widget.attrs.update({
            'class': 'form-select'
        })
        
        self.fields['file'].widget.attrs.update({
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png'
        })
        
        # Add file validation
        self.fields['file'].validators = [
            FileExtensionValidator(
                allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'],
                message='Only PDF, JPG, JPEG, and PNG files are allowed.'
            )
        ]
        
        # Add help texts
        self.fields['file'].help_text = 'Upload PDF or image files (JPG, PNG). Max size: 10MB'
        self.fields['document_type'].help_text = 'Select the type of document being uploaded'
    
    def clean_file(self):
        """
        Validate uploaded file
        """
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size (10MB limit)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('File size cannot exceed 10MB.')
            
            # Check file extension
            allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png']
            file_extension = file.name.split('.')[-1].lower()
            
            if file_extension not in allowed_extensions:
                raise forms.ValidationError(
                    f'File type "{file_extension}" is not supported. '
                    f'Allowed types: {", ".join(allowed_extensions)}'
                )
        
        return file
    
    def clean_name(self):
        """
        Auto-generate name from filename if not provided
        """
        name = self.cleaned_data.get('name')
        file = self.cleaned_data.get('file')
        
        if not name and file:
            # Use filename without extension as name
            name = file.name.rsplit('.', 1)[0]
        
        return name


class ExtractedFieldsForm(forms.ModelForm):
    """
    Form for editing extracted fields
    """
    
    class Meta:
        model = ExtractedFields
        fields = [
            'full_name', 'date_of_birth', 'email', 'phone_number',
            'pan_number', 'aadhaar_number', 'address_line_1', 'address_line_2',
            'city', 'state', 'pincode', 'bank_name', 'account_number', 'ifsc_code'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Group fields for better organization
        personal_fields = ['full_name', 'date_of_birth', 'email', 'phone_number']
        id_fields = ['pan_number', 'aadhaar_number']
        address_fields = ['address_line_1', 'address_line_2', 'city', 'state', 'pincode']
        bank_fields = ['bank_name', 'account_number', 'ifsc_code']
        
        # Apply common styling to all fields
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
            field.required = False  # Make all fields optional for flexibility
            
        # Customize specific fields
        self.fields['full_name'].widget.attrs.update({
            'placeholder': 'Enter full name as per documents'
        })
        
        self.fields['date_of_birth'].widget.attrs.update({
            'placeholder': 'DD/MM/YYYY or DD-MM-YYYY',
            'pattern': r'[0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4}'
        })
        
        self.fields['email'].widget.attrs.update({
            'placeholder': 'Enter email address',
            'type': 'email'
        })
        
        self.fields['phone_number'].widget.attrs.update({
            'placeholder': 'Enter 10-digit mobile number',
            'pattern': r'[6-9][0-9]{9}'
        })
        
        self.fields['pan_number'].widget.attrs.update({
            'placeholder': 'ABCDE1234F',
            'pattern': r'[A-Z]{5}[0-9]{4}[A-Z]{1}',
            'style': 'text-transform: uppercase;'
        })
        
        self.fields['aadhaar_number'].widget.attrs.update({
            'placeholder': '1234 5678 9012',
            'pattern': r'[0-9]{4}[\s]?[0-9]{4}[\s]?[0-9]{4}'
        })
        
        self.fields['pincode'].widget.attrs.update({
            'placeholder': '123456',
            'pattern': r'[1-9][0-9]{5}'
        })
        
        self.fields['ifsc_code'].widget.attrs.update({
            'placeholder': 'SBIN0001234',
            'pattern': r'[A-Z]{4}0[A-Z0-9]{6}',
            'style': 'text-transform: uppercase;'
        })
        
        self.fields['account_number'].widget.attrs.update({
            'placeholder': 'Bank account number'
        })
        
        # Add help texts
        self.fields['pan_number'].help_text = '10-character PAN number (e.g., ABCDE1234F)'
        self.fields['aadhaar_number'].help_text = '12-digit Aadhaar number'
        self.fields['phone_number'].help_text = '10-digit mobile number starting with 6-9'
        self.fields['ifsc_code'].help_text = '11-character IFSC code'
        self.fields['date_of_birth'].help_text = 'Date in DD/MM/YYYY format'
    
    def clean_pan_number(self):
        """
        Validate PAN number format
        """
        pan = self.cleaned_data.get('pan_number')
        if pan:
            pan = pan.upper().replace(' ', '')
            import re
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan):
                raise forms.ValidationError('Invalid PAN format. Use format: ABCDE1234F')
            return pan
        return pan
    
    def clean_aadhaar_number(self):
        """
        Validate Aadhaar number format
        """
        aadhaar = self.cleaned_data.get('aadhaar_number')
        if aadhaar:
            import re
            # Remove spaces and hyphens
            clean_aadhaar = re.sub(r'[\s-]', '', aadhaar)
            if not re.match(r'^[0-9]{12}$', clean_aadhaar):
                raise forms.ValidationError('Invalid Aadhaar format. Must be 12 digits.')
            return clean_aadhaar
        return aadhaar
    
    def clean_phone_number(self):
        """
        Validate phone number format
        """
        phone = self.cleaned_data.get('phone_number')
        if phone:
            import re
            # Remove all non-digit characters
            clean_phone = re.sub(r'\D', '', phone)
            
            # Check for +91 prefix and remove it
            if clean_phone.startswith('91') and len(clean_phone) == 12:
                clean_phone = clean_phone[2:]
            
            if not re.match(r'^[6-9][0-9]{9}$', clean_phone):
                raise forms.ValidationError('Invalid phone number. Must be 10 digits starting with 6-9.')
            return clean_phone
        return phone
    
    def clean_email(self):
        """
        Validate email format
        """
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
            return email
        return email
    
    def clean_ifsc_code(self):
        """
        Validate IFSC code format
        """
        ifsc = self.cleaned_data.get('ifsc_code')
        if ifsc:
            ifsc = ifsc.upper().replace(' ', '')
            import re
            if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc):
                raise forms.ValidationError('Invalid IFSC format. Use format: SBIN0001234')
            return ifsc
        return ifsc
    
    def clean_pincode(self):
        """
        Validate pincode format
        """
        pincode = self.cleaned_data.get('pincode')
        if pincode:
            import re
            clean_pincode = re.sub(r'\D', '', pincode)
            if not re.match(r'^[1-9][0-9]{5}$', clean_pincode):
                raise forms.ValidationError('Invalid pincode. Must be 6 digits, cannot start with 0.')
            return clean_pincode
        return pincode
    
    def clean_date_of_birth(self):
        """
        Validate and normalize date of birth
        """
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            import re
            from datetime import datetime
            
            # Try to parse different date formats
            date_patterns = [
                (r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$', '%d/%m/%Y'),  # DD/MM/YYYY
                (r'^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$', '%Y/%m/%d'),  # YYYY/MM/DD
            ]
            
            for pattern, format_str in date_patterns:
                if re.match(pattern, dob):
                    try:
                        # Validate the date
                        if format_str == '%d/%m/%Y':
                            day, month, year = re.match(pattern, dob).groups()
                            datetime.strptime(f"{day}/{month}/{year}", format_str)
                        else:
                            datetime.strptime(dob, format_str)
                        return dob
                    except ValueError:
                        continue
            
            raise forms.ValidationError('Invalid date format. Use DD/MM/YYYY or YYYY/MM/DD.')
        return dob 


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiDocumentUploadForm(forms.Form):
    """Plain form to upload one or more files with shared metadata."""
    files = forms.FileField(
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png'
        }),
        help_text='Upload one or more PDF/JPG/PNG files (10MB per file limit)'
    )
    document_type = forms.ChoiceField(
        choices=UploadedDocument.DOCUMENT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Select the type for all selected files'
    )
    name_prefix = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional prefix for document names'
        })
    )

    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
    MAX_SIZE_BYTES = 10 * 1024 * 1024

    def clean(self):
        cleaned = super().clean()
        files = self.files.getlist('files') if self.files else []
        if not files:
            raise forms.ValidationError('Please select at least one file to upload.')

        # Validate each file
        errors = []
        for f in files:
            # Size
            if f.size > self.MAX_SIZE_BYTES:
                errors.append(f'{f.name}: exceeds 10MB limit')
            # Extension
            ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
            if ext not in self.ALLOWED_EXTENSIONS:
                errors.append(f'{f.name}: unsupported type "{ext}"')
        if errors:
            raise forms.ValidationError(errors)
        return cleaned 