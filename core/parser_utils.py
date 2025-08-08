import re
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class FieldExtractor:
    """
    Enhanced class to extract ALL fields from raw OCR text, both predefined and dynamic
    """
    
    def __init__(self):
        # Define regex patterns for known fields
        self.patterns = {
            'pan': [
                r'[A-Z]{5}[0-9]{4}[A-Z]{1}',  # Standard PAN format
                r'PAN[:\s]*([A-Z]{5}[0-9]{4}[A-Z]{1})',  # PAN with prefix
                r'Permanent Account Number[:\s]*([A-Z]{5}[0-9]{4}[A-Z]{1})',
            ],
            'aadhaar': [
                r'\b[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}\b',  # 12 digit Aadhaar
                r'Aadhaar[:\s]*([0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4})',
                r'UID[:\s]*([0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4})',
            ],
            'email': [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Standard email
                r'Email[:\s]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
                r'E-mail[:\s]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
            ],
            'phone': [
                r'\+91[\s-]?[6-9][0-9]{9}',  # Indian mobile with +91
                r'\b[6-9][0-9]{9}\b',  # 10 digit Indian mobile
                r'Mobile[:\s]*(\+91[\s-]?[6-9][0-9]{9})',
                r'Phone[:\s]*(\+91[\s-]?[6-9][0-9]{9})',
                r'Contact[:\s]*(\+91[\s-]?[6-9][0-9]{9})',
                r'Mobile[:\s]*([6-9][0-9]{9})',
                r'Phone[:\s]*([6-9][0-9]{9})',
            ],
            'dob': [
                r'\b([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4})\b',  # DD/MM/YYYY or DD-MM-YYYY
                r'\b([0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})\b',  # YYYY/MM/DD or YYYY-MM-DD
                r'Date of Birth[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4})',
                r'DOB[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4})',
                r'Born[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4})',
            ],
            'ifsc': [
                r'\b[A-Z]{4}0[A-Z0-9]{6}\b',  # Standard IFSC format
                r'IFSC[:\s]*([A-Z]{4}0[A-Z0-9]{6})',
                r'IFSC Code[:\s]*([A-Z]{4}0[A-Z0-9]{6})',
            ],
            'account_number': [
                r'Account[:\s]*([0-9]{9,18})',  # Account number 9-18 digits
                r'A/C[:\s]*([0-9]{9,18})',
                r'Account Number[:\s]*([0-9]{9,18})',
            ],
            'pincode': [
                r'\b[1-9][0-9]{5}\b',  # 6 digit pincode
                r'PIN[:\s]*([1-9][0-9]{5})',
                r'Pincode[:\s]*([1-9][0-9]{5})',
                r'Postal Code[:\s]*([1-9][0-9]{5})',
            ],
            'passport': [
                r'[A-Z][0-9]{7}',  # Indian passport format
                r'Passport[:\s]*([A-Z][0-9]{7})',
                r'Passport Number[:\s]*([A-Z][0-9]{7})',
            ],
            'driving_license': [
                r'[A-Z]{2}[0-9]{2}[0-9]{11}',  # Indian DL format
                r'DL[:\s]*([A-Z]{2}[0-9]{2}[0-9]{11})',
                r'Driving License[:\s]*([A-Z]{2}[0-9]{2}[0-9]{11})',
            ],
            'employee_id': [
                r'Employee ID[:\s]*([A-Z0-9]{4,15})',
                r'EMP ID[:\s]*([A-Z0-9]{4,15})',
                r'Staff ID[:\s]*([A-Z0-9]{4,15})',
            ]
        }
        
        # Enhanced name patterns
        self.name_patterns = [
            r'Name[:\s]*([A-Za-z\s]{2,50})',
            r'Full Name[:\s]*([A-Za-z\s]{2,50})',
            r'Candidate Name[:\s]*([A-Za-z\s]{2,50})',
            r'Employee Name[:\s]*([A-Za-z\s]{2,50})',
            r'Father\'?s Name[:\s]*([A-Za-z\s]{2,50})',
            r'Mother\'?s Name[:\s]*([A-Za-z\s]{2,50})',
            r'Spouse Name[:\s]*([A-Za-z\s]{2,50})',
            r'Guardian Name[:\s]*([A-Za-z\s]{2,50})',
        ]
        
        # Enhanced address patterns
        self.address_patterns = [
            r'Address[:\s]*([A-Za-z0-9\s,.-]{10,200})',
            r'Permanent Address[:\s]*([A-Za-z0-9\s,.-]{10,200})',
            r'Current Address[:\s]*([A-Za-z0-9\s,.-]{10,200})',
            r'Residential Address[:\s]*([A-Za-z0-9\s,.-]{10,200})',
            r'Correspondence Address[:\s]*([A-Za-z0-9\s,.-]{10,200})',
        ]
        
        # Enhanced bank patterns
        self.bank_patterns = [
            r'Bank Name[:\s]*([A-Za-z\s&]{2,50})',
            r'Bank[:\s]*([A-Za-z\s&]{2,50})',
            r'Branch[:\s]*([A-Za-z\s]{2,50})',
            r'Branch Name[:\s]*([A-Za-z\s]{2,50})',
        ]
        
        # Generic field patterns for dynamic extraction
        self.dynamic_patterns = [
            r'([A-Za-z\s\']{2,30})[:\s]*([A-Za-z0-9\s,.-]{1,100})',  # General field: value pattern
            r'([A-Za-z\s]{2,20})\s*:\s*([^\n]{1,100})',  # Field: Value pattern
            r'([A-Za-z\s]{2,20})\s*-\s*([^\n]{1,100})',  # Field - Value pattern
        ]
    
    def extract_field(self, text, field_type):
        """
        Extract a specific field type from text
        """
        if field_type not in self.patterns:
            return None
        
        # Clean the text
        text = self.clean_text_for_extraction(text)
        
        # Try each pattern for the field type
        for pattern in self.patterns[field_type]:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Return the first match, cleaned
                match = matches[0] if isinstance(matches[0], str) else matches[0][0] if matches[0] else None
                if match:
                    return self.clean_field_value(match, field_type)
        
        return None
    
    def extract_name(self, text):
        """
        Extract name using specific name patterns
        """
        text = self.clean_text_for_extraction(text)
        
        for pattern in self.name_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                name = matches[0].strip()
                # Validate name (should contain only letters and spaces)
                if re.match(r'^[A-Za-z\s]{2,50}$', name):
                    return self.clean_name(name)
        
        # Fallback: try to find name at the beginning of common sections
        lines = text.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if len(line) > 3 and len(line) < 50 and re.match(r'^[A-Za-z\s]+$', line):
                # Check if it's likely a name (not common words)
                if not any(word.lower() in line.lower() for word in ['form', 'application', 'document', 'page']):
                    return self.clean_name(line)
        
        return None
    
    def extract_address(self, text):
        """
        Extract address using specific address patterns
        """
        text = self.clean_text_for_extraction(text)
        
        for pattern in self.address_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            if matches:
                address = matches[0].strip()
                # Clean and validate address
                cleaned_address = self.clean_address(address)
                if len(cleaned_address) > 10:  # Minimum address length
                    return cleaned_address
        
        return None
    
    def extract_bank_name(self, text):
        """
        Extract bank name using specific bank patterns
        """
        text = self.clean_text_for_extraction(text)
        
        for pattern in self.bank_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                bank_name = matches[0].strip()
                # Validate bank name
                if len(bank_name) > 2 and len(bank_name) < 50:
                    return self.clean_bank_name(bank_name)
        
        return None
    
    def extract_dynamic_fields(self, text):
        """
        Extract ALL fields dynamically from text using pattern matching
        """
        logger.info("Starting dynamic field extraction")
        
        dynamic_fields = {}
        
        # Clean text for better pattern matching
        clean_text = self.clean_text_for_extraction(text)
        lines = clean_text.split('\n')
        
        # Extract from line-by-line analysis
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
                
            # Try different dynamic patterns
            for pattern in self.dynamic_patterns:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    if len(match.groups()) >= 2:
                        field_name = match.group(1).strip()
                        field_value = match.group(2).strip()
                        
                        # Clean and validate the extracted field
                        if self.is_valid_dynamic_field(field_name, field_value):
                            # Normalize field name
                            normalized_name = self.normalize_field_name(field_name)
                            
                            # Only add if not empty and meaningful
                            if normalized_name and field_value and len(field_value.strip()) > 1:
                                dynamic_fields[normalized_name] = field_value.strip()
        
        # Extract structured information like tables
        table_data = self.extract_table_data(text)
        if table_data:
            dynamic_fields.update(table_data)
        
        # Extract education and professional details
        education_fields = self.extract_education_fields(text)
        if education_fields:
            dynamic_fields.update(education_fields)
            
        professional_fields = self.extract_professional_fields(text)
        if professional_fields:
            dynamic_fields.update(professional_fields)
        
        logger.info(f"Extracted {len(dynamic_fields)} dynamic fields")
        return dynamic_fields
    
    def extract_table_data(self, text):
        """
        Extract structured data that might be in table format
        """
        table_fields = {}
        
        # Look for common table-like patterns
        table_patterns = [
            r'(\w+)\s+:\s*([^\n]+)',  # Field : Value
            r'(\w+)\s+([A-Za-z0-9\s]{1,50})\s*\|',  # Table with pipes
            r'(\w+)\s*\|\s*([^\|]+)',  # Pipe separated
        ]
        
        for pattern in table_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if len(match.groups()) >= 2:
                    key = self.normalize_field_name(match.group(1))
                    value = match.group(2).strip()
                    if key and value and len(value) > 1:
                        table_fields[key] = value
        
        return table_fields
    
    def extract_education_fields(self, text):
        """
        Extract education-related fields
        """
        education_fields = {}
        
        education_patterns = {
            'qualification': [
                r'Qualification[:\s]*([A-Za-z\s.]{2,50})',
                r'Education[:\s]*([A-Za-z\s.]{2,50})',
                r'Degree[:\s]*([A-Za-z\s.]{2,50})',
            ],
            'university': [
                r'University[:\s]*([A-Za-z\s]{2,100})',
                r'College[:\s]*([A-Za-z\s]{2,100})',
                r'Institute[:\s]*([A-Za-z\s]{2,100})',
            ],
            'year_of_passing': [
                r'Year of Passing[:\s]*([0-9]{4})',
                r'Passing Year[:\s]*([0-9]{4})',
                r'Graduation Year[:\s]*([0-9]{4})',
            ],
            'percentage': [
                r'Percentage[:\s]*([0-9]{1,3}\.?[0-9]*)',
                r'Marks[:\s]*([0-9]{1,3}\.?[0-9]*)',
                r'CGPA[:\s]*([0-9]{1,2}\.?[0-9]*)',
            ]
        }
        
        for field_type, patterns in education_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    education_fields[field_type] = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    break
        
        return education_fields
    
    def extract_professional_fields(self, text):
        """
        Extract professional/employment-related fields
        """
        professional_fields = {}
        
        professional_patterns = {
            'designation': [
                r'Designation[:\s]*([A-Za-z\s]{2,50})',
                r'Position[:\s]*([A-Za-z\s]{2,50})',
                r'Job Title[:\s]*([A-Za-z\s]{2,50})',
                r'Role[:\s]*([A-Za-z\s]{2,50})',
            ],
            'department': [
                r'Department[:\s]*([A-Za-z\s]{2,50})',
                r'Division[:\s]*([A-Za-z\s]{2,50})',
                r'Team[:\s]*([A-Za-z\s]{2,50})',
            ],
            'joining_date': [
                r'Joining Date[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4})',
                r'Date of Joining[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4})',
                r'Start Date[:\s]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4})',
            ],
            'reporting_manager': [
                r'Reporting Manager[:\s]*([A-Za-z\s]{2,50})',
                r'Manager[:\s]*([A-Za-z\s]{2,50})',
                r'Supervisor[:\s]*([A-Za-z\s]{2,50})',
            ],
            'salary': [
                r'Salary[:\s]*([0-9,]{1,15})',
                r'CTC[:\s]*([0-9,]{1,15})',
                r'Annual Package[:\s]*([0-9,]{1,15})',
            ]
        }
        
        for field_type, patterns in professional_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    professional_fields[field_type] = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    break
        
        return professional_fields
    
    def normalize_field_name(self, field_name):
        """
        Normalize field names for consistency
        """
        if not field_name:
            return None
            
        # Clean the field name
        normalized = field_name.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove special chars
        normalized = re.sub(r'\s+', '_', normalized)  # Replace spaces with underscores
        
        # Skip very short or very long field names
        if len(normalized) < 2 or len(normalized) > 50:
            return None
            
        # Skip common words that aren't field names
        skip_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'page', 'form', 'document', 'application', 'submit', 'date', 'time', 'please',
            'fill', 'enter', 'write', 'sign', 'signature', 'print', 'clear', 'block',
            'letters', 'capital', 'small', 'tick', 'mark', 'yes', 'no', 'male', 'female'
        }
        
        if normalized in skip_words:
            return None
            
        return normalized
    
    def is_valid_dynamic_field(self, field_name, field_value):
        """
        Validate if a dynamically extracted field is meaningful
        """
        if not field_name or not field_value:
            return False
            
        # Check field name validity
        if len(field_name.strip()) < 2 or len(field_name.strip()) > 50:
            return False
            
        # Check field value validity
        field_value = field_value.strip()
        if len(field_value) < 1 or len(field_value) > 200:
            return False
            
        # Skip if field value is just punctuation or numbers
        if re.match(r'^[^\w]*$', field_value):
            return False
            
        # Skip if field name contains too many numbers
        if len(re.findall(r'\d', field_name)) > len(field_name) / 2:
            return False
            
        return True

    def extract_all_fields(self, text):
        """
        Extract ALL supported fields from text - both predefined and dynamic
        """
        logger.info("Starting comprehensive field extraction from text")
        
        all_extracted_fields = {}
        
        # Extract predefined fields using existing patterns
        for field_type in self.patterns.keys():
            value = self.extract_field(text, field_type)
            if value:
                all_extracted_fields[field_type] = value
                logger.info(f"Extracted predefined {field_type}: {value}")
        
        # Extract predefined name fields
        name = self.extract_name(text)
        if name:
            all_extracted_fields['full_name'] = name
            logger.info(f"Extracted name: {name}")
        
        # Extract predefined address fields
        address = self.extract_address(text)
        if address:
            # Try to split address into components
            address_parts = self.parse_address(address)
            all_extracted_fields.update(address_parts)
            logger.info(f"Extracted address: {address}")
        
        # Extract predefined bank name
        bank_name = self.extract_bank_name(text)
        if bank_name:
            all_extracted_fields['bank_name'] = bank_name
            logger.info(f"Extracted bank name: {bank_name}")
        
        # Extract ALL dynamic fields
        dynamic_fields = self.extract_dynamic_fields(text)
        
        # Merge dynamic fields with predefined fields (predefined takes precedence)
        for key, value in dynamic_fields.items():
            if key not in all_extracted_fields:  # Don't override predefined fields
                all_extracted_fields[key] = value
        
        # Convert field names to match model fields where possible
        field_mapping = {
            'dob': 'date_of_birth',
            'phone': 'phone_number',
            'aadhaar': 'aadhaar_number',
            'pan': 'pan_number',
        }
        
        # Apply field mapping
        mapped_fields = {}
        for key, value in all_extracted_fields.items():
            mapped_key = field_mapping.get(key, key)
            mapped_fields[mapped_key] = value
        
        logger.info(f"Extracted {len(mapped_fields)} total fields (predefined + dynamic)")
        return mapped_fields
    
    def clean_text_for_extraction(self, text):
        """
        Clean text to improve extraction accuracy
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters that might interfere
        text = re.sub(r'[|_]+', ' ', text)
        
        return text.strip()
    
    def clean_field_value(self, value, field_type):
        """
        Clean extracted field value based on field type
        """
        if not value:
            return None
        
        value = value.strip()
        
        if field_type == 'pan':
            return value.upper().replace(' ', '')
        
        elif field_type == 'aadhaar':
            # Remove spaces and hyphens
            return re.sub(r'[\s-]', '', value)
        
        elif field_type == 'email':
            return value.lower()
        
        elif field_type == 'phone':
            # Remove all non-digit characters except +
            return re.sub(r'[^\d+]', '', value)
        
        elif field_type == 'ifsc':
            return value.upper().replace(' ', '')
        
        elif field_type == 'pincode':
            return re.sub(r'\D', '', value)
        
        elif field_type == 'account_number':
            return re.sub(r'\D', '', value)
        
        return value
    
    def clean_name(self, name):
        """
        Clean extracted name
        """
        if not name:
            return None
        
        # Remove extra spaces and title case
        name = ' '.join(name.split())
        name = name.title()
        
        # Remove common prefixes/suffixes
        prefixes = ['Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.']
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
        
        return name
    
    def clean_address(self, address):
        """
        Clean extracted address
        """
        if not address:
            return None
        
        # Remove excessive whitespace and newlines
        address = re.sub(r'\s+', ' ', address)
        address = address.strip()
        
        return address
    
    def clean_bank_name(self, bank_name):
        """
        Clean extracted bank name
        """
        if not bank_name:
            return None
        
        # Title case and clean
        bank_name = bank_name.title().strip()
        
        return bank_name
    
    def parse_address(self, address):
        """
        Try to parse address into components
        """
        address_parts = {}
        
        if not address:
            return address_parts
        
        # Split by commas or newlines
        parts = re.split(r'[,\n]', address)
        parts = [part.strip() for part in parts if part.strip()]
        
        if len(parts) >= 1:
            address_parts['address_line_1'] = parts[0]
        
        if len(parts) >= 2:
            address_parts['address_line_2'] = parts[1]
        
        # Try to extract city, state, pincode from last parts
        if parts:
            last_part = parts[-1]
            
            # Extract pincode from last part
            pincode_match = re.search(r'\b([1-9][0-9]{5})\b', last_part)
            if pincode_match:
                address_parts['pincode'] = pincode_match.group(1)
                # Remove pincode from the part
                last_part = last_part.replace(pincode_match.group(0), '').strip()
            
            # Remaining could be city/state
            if last_part:
                remaining_parts = last_part.split()
                if len(remaining_parts) >= 2:
                    address_parts['city'] = remaining_parts[0]
                    address_parts['state'] = ' '.join(remaining_parts[1:])
                elif len(remaining_parts) == 1:
                    address_parts['city'] = remaining_parts[0]
        
        return address_parts
    
    def validate_extracted_fields(self, fields):
        """
        Validate extracted fields for common errors
        """
        validated_fields = {}
        
        for field, value in fields.items():
            if self.validate_field(field, value):
                validated_fields[field] = value
            else:
                logger.warning(f"Field {field} failed validation: {value}")
        
        return validated_fields
    
    def validate_field(self, field_name, value):
        """
        Validate individual field values
        """
        if not value:
            return False
        
        if field_name == 'pan_number':
            return bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', value))
        
        elif field_name == 'aadhaar_number':
            # Check if it's 12 digits
            clean_aadhaar = re.sub(r'\D', '', value)
            return len(clean_aadhaar) == 12
        
        elif field_name == 'email':
            return bool(re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$', value))
        
        elif field_name == 'phone_number':
            # Check if it's a valid Indian mobile number
            clean_phone = re.sub(r'\D', '', value)
            return len(clean_phone) in [10, 12] and clean_phone.startswith(('6', '7', '8', '9'))
        
        elif field_name == 'ifsc_code':
            return bool(re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', value))
        
        elif field_name == 'pincode':
            return bool(re.match(r'^[1-9][0-9]{5}$', value))
        
        elif field_name == 'account_number':
            return len(value) >= 9 and len(value) <= 18 and value.isdigit()
        
        # For other fields, basic validation
        elif field_name in ['full_name', 'bank_name']:
            return len(value) >= 2 and len(value) <= 100
        
        return True 