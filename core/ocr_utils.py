import os
import cv2
import google.generativeai as genai
import magic
from PIL import Image
from pdf2image import convert_from_path
import tempfile
import logging
import base64
import io
import json
from django.conf import settings
import re

logger = logging.getLogger(__name__)

# Configure Google AI
try:
    genai.configure(api_key=settings.GOOGLE_AI_API_KEY)
    # Use the requested Gemini model with enhanced capabilities
    model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-pro')
    model = genai.GenerativeModel(model_name)
    logger.info(f"Google AI configured with model: {model_name}")
except Exception as e:
    logger.error(f"Failed to configure Google AI: {e}")
    model = None


def detect_file_type(file_path):
    """
    Detect the MIME type of a file using python-magic
    """
    try:
        mime = magic.from_file(file_path, mime=True)
        return mime
    except Exception as e:
        logger.error(f"Error detecting file type: {e}")
        # Fallback to file extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        elif ext == '.png':
            return 'image/png'
        elif ext == '.pdf':
            return 'application/pdf'
        else:
            return 'unknown'


def preprocess_image(image):
    """
    Preprocess image to improve OCR accuracy (optional for Gemini, but can help)
    """
    try:
        # Convert PIL Image to OpenCV format
        import numpy as np
        open_cv_image = np.array(image)
        
        # Convert RGB to BGR for OpenCV
        if len(open_cv_image.shape) == 3:
            open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)
        
        # Convert to grayscale
        if len(open_cv_image.shape) == 3:
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = open_cv_image
        
        # Apply denoising
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Apply thresholding to get binary image
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Convert back to PIL Image
        processed_image = Image.fromarray(thresh)
        return processed_image
        
    except Exception as e:
        logger.warning(f"Image preprocessing failed, using original: {e}")
        return image


def _try_parse_json_from_text(text: str):
    """Best-effort JSON parsing from model output that may include prose/fences."""
    if not text:
        return None
    s = text.strip()
    candidates = []
    # fenced block
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s, re.IGNORECASE)
    if m:
        candidates.append(m.group(1).strip())
    # largest object
    m = re.search(r"\{[\s\S]*\}", s)
    if m:
        candidates.append(m.group(0))
    # largest array
    m = re.search(r"\[[\s\S]*\]", s)
    if m:
        candidates.append(m.group(0))
    # raw
    candidates.append(s)

    def normalize_quotes(t):
        return t.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")

    for cand in candidates:
        try:
            return json.loads(normalize_quotes(cand))
        except Exception:
            continue
    return None


def extract_text_with_gemini(image):
    """
    Extract JSON from an image using Google Gemini Pro Vision.
    The model is instructed to return JSON only (no prose, no code fences).
    """
    if not model:
        raise Exception("Google AI model not configured. Please check your API key.")
    
    try:
        prompt = (
            "You are an OCR and information extraction engine. "
            "Read the document image and return a SINGLE valid JSON object only. "
            "Do NOT include markdown code fences or any commentary. "
            "If there are multiple sections or pages, merge them into a single JSON object. "
            "Preserve all numbers/IDs as strings. Use arrays for lists and tables. "
            "If a field is unreadable, use null. Keys should be concise and snake_case."
        )
        
        response = model.generate_content(
            [prompt, image],
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                top_p=0.8,
                top_k=40,
                max_output_tokens=8192
            ),
        )
        
        if response.text:
            # Return as-is (already JSON). Avoid cleanup to preserve JSON structure
            logger.info(f"Successfully extracted JSON using Gemini: {len(response.text)} chars")
            return response.text
        else:
            logger.warning("Gemini returned empty response")
            return "{}"
            
    except Exception as e:
        error_msg = str(e)
        if "504" in error_msg or "Deadline Exceeded" in error_msg:
            logger.error(f"Gemini API timeout (504): {error_msg}")
            simple_prompt = (
                "Return ONLY a valid JSON object representing all readable text and fields. "
                "No markdown, no explanations."
            )
            try:
                response = model.generate_content(
                    [simple_prompt, image],
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=4096
                    ),
                )
                if response.text:
                    return response.text
            except Exception as fallback_error:
                logger.error(f"Fallback extraction failed: {fallback_error}")
        
        logger.error(f"Error extracting JSON with Gemini: {error_msg}")
        raise Exception(f"OCR processing failed: {error_msg}")


def extract_text_from_image(image_path):
    """
    Extract JSON from an image file using Google Gemini Pro Vision
    """
    try:
        image = Image.open(image_path)
        logger.info(f"Processing image: {image_path}, size: {image.size}, mode: {image.mode}")
        json_text = extract_text_with_gemini(image)
        # Ensure we return a JSON string downstream
        payload = _try_parse_json_from_text(json_text)
        if payload is None:
            payload = {"text": (json_text or "").strip()}
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error extracting text from image: {e}")
        raise


def _merge_json_objects(base_obj, new_obj):
    """Shallow merge two dicts: prefer existing non-empty values; merge dicts recursively; extend arrays."""
    if not isinstance(base_obj, dict) or not isinstance(new_obj, dict):
        return base_obj
    for k, v in new_obj.items():
        if k not in base_obj or base_obj[k] in (None, "", []):
            base_obj[k] = v
        else:
            if isinstance(base_obj[k], dict) and isinstance(v, dict):
                _merge_json_objects(base_obj[k], v)
            elif isinstance(base_obj[k], list) and isinstance(v, list):
                base_obj[k].extend(v)
            # else keep existing
    return base_obj


def extract_text_from_pdf(pdf_path):
    """
    Extract JSON from a PDF by converting to images and merging page-level JSON into one object.
    """
    try:
        logger.info(f"Converting PDF to images: {pdf_path}")
        images = convert_from_path(pdf_path, dpi=300)
        merged = {}
        for i, image in enumerate(images):
            logger.info(f"Processing page {i+1} of {len(images)} for JSON extraction")
            try:
                page_json_text = extract_text_with_gemini(image)
                obj = _try_parse_json_from_text(page_json_text)
                if isinstance(obj, dict):
                    merged = _merge_json_objects(merged, obj)
                elif obj is not None:
                    merged.setdefault("pages", []).append(obj)
                else:
                    merged.setdefault("pages", []).append({"text": (page_json_text or "").strip()})
            except Exception as e:
                logger.error(f"Error processing page {i+1}: {e}")
                merged.setdefault("errors", []).append({"page": i+1, "error": str(e)})
        return json.dumps(merged, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        raise


def clean_extracted_text(text):
    """
    Clean and normalize extracted text (not used for JSON mode)
    """
    if not text:
        return ""
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]
    cleaned_text = '\n'.join(lines)
    import re
    cleaned_text = re.sub(r' +', ' ', cleaned_text)
    return cleaned_text


def extract_text_from_file(file_path):
    """
    Main function to extract content from any supported file type using Google Gemini Pro
    Returns (text, mime_type). In JSON mode, text is a JSON string.
    """
    logger.info(f"Starting text extraction from: {file_path}")
    if not model:
        raise Exception("Google AI not configured. Please set GOOGLE_AI_API_KEY in your environment variables.")
    mime_type = detect_file_type(file_path)
    logger.info(f"Detected file type: {mime_type}")
    try:
        if mime_type.startswith('image/'):
            text = extract_text_from_image(file_path)
        elif mime_type == 'application/pdf':
            text = extract_text_from_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file type: {mime_type}")
        logger.info(f"Successfully extracted content ({len(text)} chars) using Gemini")
        return text, mime_type
    except Exception as e:
        logger.error(f"Failed to extract text: {e}")
        raise


def get_ocr_confidence(image_path):
    """
    Estimate OCR confidence by presence/size of extracted JSON
    """
    try:
        text = extract_text_from_image(image_path)
        if not text or len(text.strip()) < 10:
            return 50
        elif len(text.strip()) < 100:
            return 75
        else:
            return 90
    except Exception as e:
        logger.error(f"Error estimating OCR confidence: {e}")
        return 0


def validate_ocr_requirements():
    """
    Validate that Google AI dependencies are properly configured
    """
    try:
        if not settings.GOOGLE_AI_API_KEY or settings.GOOGLE_AI_API_KEY == 'your_google_ai_api_key_here':
            logger.error("Google AI API key not configured")
            return False
        if not model:
            logger.error("Google AI model not initialized")
            return False
        logger.info("Google AI configured successfully")
        return True
    except Exception as e:
        logger.error(f"Google AI validation failed: {e}")
        return False


def get_gemini_usage_info():
    """
    Get information about Gemini API usage and pricing
    """
    return {
        'model': getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-pro'),
        'pricing_info': {
            'gemini-1.5-flash': 'Free tier: 15 requests per minute, 1500 requests per day',
            'gemini-1.5-pro': 'Free tier: 2 requests per minute, 50 requests per day',
            'gemini-2.0-flash-exp': 'Pro subscription: Higher rate limits, enhanced accuracy',
            'gemini-2.5-pro': 'Pro subscription: Latest model with improved document understanding',
        },
        'api_limits': 'Check https://ai.google.dev/pricing for current limits',
        'note': 'OCR processing uses your Gemini 2.5 Pro subscription. Monitor usage in Google AI Studio.',
        'features': [
            'Enhanced document understanding',
            'Better handling of complex layouts',
            'Improved field extraction accuracy',
            'Advanced table and form processing',
            'Multi-language document support'
        ]
    } 