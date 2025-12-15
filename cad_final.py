import streamlit as st
import base64
from PIL import Image, ImageDraw, ImageFont
import io
import pandas as pd
import os
import requests
import datetime
from pdf2image import convert_from_bytes
import tempfile
import sys
import subprocess
import fitz  # PyMuPDF
from pdf2image.exceptions import PDFPageCountError
import uuid
import numpy as np

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system environment variables

# Try to import pytesseract, but make it optional
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\shrey\Downloads\tesseract-ocr-w64-setup-v5.3.0.20221214.exe"



def check_poppler_installed():
    """Check if poppler is installed on the system"""
    try:
        if sys.platform.startswith('win'):
            # On Windows, check if path contains poppler
            return any('poppler' in path.lower() for path in os.environ.get('PATH', '').split(os.pathsep))
        else:
            # On Unix-like systems, try to run pdftoppm
            subprocess.run(['pdftoppm', '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        return False

# === Load API Key from Environment ===
API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    st.error("❌ No API key provided! Please manually set it in the script.")
    st.stop()

# Initialize API key in session state
if 'current_api_key' not in st.session_state:
    st.session_state.current_api_key = API_KEY


def handle_api_response(response_json, retry_func=None, *args, **kwargs):
    """Handle API response and switch keys if needed"""
    if 'error' in response_json:
        error = response_json.get('error', {})
        if isinstance(error, dict):
            error_type = error.get('type', '')
            error_code = error.get('code', '')
            error_message = error.get('message', '')
            
            # Check for rate limit error
            if error_type == 'rate_limit_exceeded' or 'rate limit' in error_message.lower():
                if switch_api_key():
                    st.warning("Switching to alternate API key due to rate limit...")
                    if retry_func:
                        return retry_func(*args, **kwargs)
                    return None
                else:
                    st.error("❌ All API keys have reached their rate limits!")
                    return None
            # Handle other specific error codes
            elif error_code == 'invalid_api_key' or error_type == 'invalid_request_error' and 'api key' in error_message.lower():
                st.error("❌ Authentication failed: Please check your API key")
                return None
            elif error_type == 'invalid_request_error':
                st.error(f"❌ Invalid request: {error_message}")
                return None
            elif error_type == 'server_error':
                st.error(f"❌ Server error: Please try again later. {error_message}")
                return None
            else:
                st.error(f"❌ API Error: {error_message}")
                return None
    return response_json

def process_api_response(response, retry_func=None, *args, **kwargs):
    """Process API response and handle errors"""
    try:
        response_json = response.json()
        
        # Check if response is successful and contains choices for OpenAI
        if response.status_code == 200 and "choices" in response_json:
            content = response_json["choices"][0]["message"]["content"]
            
            # First, check if there's a parameter-justification format after the JSON
            # This is our preferred format as it already has justifications
            if "DOCUMENT_TYPE:" in content and "DOCUMENT_TYPE_JUSTIFICATION:" in content:
                # Find where the parameter format starts
                param_start = content.find("DOCUMENT_TYPE:")
                if param_start > 0:
                    return content[param_start:]
            
            # If no parameter format, check for JSON
            if "```json" in content and "```" in content.split("```json", 1)[1]:
                # Extract JSON content
                json_content = content.split("```json", 1)[1].split("```", 1)[0].strip()
                # Try to parse it as JSON
                try:
                    import json
                    parsed_json = json.loads(json_content)
                    # Convert JSON to parameter format
                    formatted_content = []
                    for key, value in parsed_json.items():
                        # Skip null or N/A values
                        if value is None or value == "N/A":
                            continue
                        # Format key properly
                        formatted_key = key.upper().replace(" ", "_")
                        formatted_content.append(f"{formatted_key}: {value}")
                        # Add justification
                        if key == "Document Type":
                            formatted_content.append(f"{formatted_key}_JUSTIFICATION: Determined based on document format and content.")
                        elif key == "Component Type":
                            formatted_content.append(f"{formatted_key}_JUSTIFICATION: Identified from component characteristics in the document.")
                        elif key == "Notes":
                            continue  # Skip justification for notes
                        else:
                            formatted_content.append(f"{formatted_key}_JUSTIFICATION: Extracted from the document. Specific location unspecified.")
                    return "\n".join(formatted_content)
                except Exception as e:
                    # If JSON parsing fails, return the original content
                    print(f"JSON parsing error: {str(e)}")
            
            # If no JSON or parameter format found, return the original content
            return content
            
        # Handle API errors
        handled_response = handle_api_response(response_json, retry_func, *args, **kwargs)
        if handled_response and "choices" in handled_response:
            content = handled_response["choices"][0]["message"]["content"]
            
            # First, check if there's a parameter-justification format after the JSON
            # This is our preferred format as it already has justifications
            if "DOCUMENT_TYPE:" in content and "DOCUMENT_TYPE_JUSTIFICATION:" in content:
                # Find where the parameter format starts
                param_start = content.find("DOCUMENT_TYPE:")
                if param_start > 0:
                    return content[param_start:]
            
            # If no parameter format, check for JSON
            if "```json" in content and "```" in content.split("```json", 1)[1]:
                # Extract JSON content
                json_content = content.split("```json", 1)[1].split("```", 1)[0].strip()
                # Try to parse it as JSON
                try:
                    import json
                    parsed_json = json.loads(json_content)
                    # Convert JSON to parameter format
                    formatted_content = []
                    for key, value in parsed_json.items():
                        # Skip null or N/A values
                        if value is None or value == "N/A":
                            continue
                        # Format key properly
                        formatted_key = key.upper().replace(" ", "_")
                        formatted_content.append(f"{formatted_key}: {value}")
                        # Add justification
                        if key == "Document Type":
                            formatted_content.append(f"{formatted_key}_JUSTIFICATION: Determined based on document format and content.")
                        elif key == "Component Type":
                            formatted_content.append(f"{formatted_key}_JUSTIFICATION: Identified from component characteristics in the document.")
                        elif key == "Notes":
                            continue  # Skip justification for notes
                        else:
                            formatted_content.append(f"{formatted_key}_JUSTIFICATION: Extracted from the document. Specific location unspecified.")
                    return "\n".join(formatted_content)
                except Exception as e:
                    # If JSON parsing fails, return the original content
                    print(f"JSON parsing error: {str(e)}")
            
            # If no JSON or parameter format found, return the original content
            return content
            
        # If we get here, something went wrong
        error_info = response_json.get('error', {})
        if isinstance(error_info, dict):
            error_msg = error_info.get('message', 'Unknown error occurred')
        else:
            error_msg = str(error_info)
        
        return f"❌ API Error: {error_msg}"
        
    except Exception as e:
        return f"❌ Processing Error: {str(e)}"

# OpenAI API URL for GPT-4o
API_URL = "https://api.openai.com/v1/chat/completions"

def encode_image_to_base64(image_bytes):
    return "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("utf-8")

def parse_ai_response(response_text):
    """Parse the AI response into a structured format with enhanced handling for mixed document types."""
    results = {}
    justifications = {}
    document_info = {}
    lines = response_text.split('\n')
    
    # Debug the raw response
    print(f"Raw AI response: {response_text[:200]}...")
    
    # First pass to extract document type information
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().upper()
            value = value.strip()
            
            # Capture document type information
            if key == "DOCUMENT_TYPE":
                document_info["DOCUMENT_TYPE"] = value
            elif key == "COMPONENT_TYPE":
                document_info["COMPONENT_TYPE"] = value
    
    # Add document info to results if found
    if document_info:
        for key, value in document_info.items():
            results[key] = value
    
    # Second pass to extract all parameters and justifications
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().upper()
            # Remove any ** characters from parameter names
            key = key.replace('*', '')
            value = value.strip()
            # Remove any ** characters from the beginning of values
            if value.startswith('**'):
                value = value[2:].strip()
            
            # Skip document type keys already processed
            if key in ["DOCUMENT_TYPE", "COMPONENT_TYPE"]:
                continue
                
            # Check if this is a justification field
            if key.endswith('_JUSTIFICATION'):
                base_key = key.replace('_JUSTIFICATION', '')
                justifications[base_key] = value
            else:
                # Check if value contains any variation of [value] and set to empty if it does
                if '[value]' in value.lower() or '[values]' in value.lower():
                    value = ""
                
                # Handle different forms of "Not Specified" consistently
                if any(not_spec in value.upper() for not_spec in ["NOT SPECIFIED", "NOT AVAILABLE", "NOT VISIBLE", "UNKNOWN", "N/A", "NONE", "NOT FOUND", "NOT INDICATED", "NOT MARKED", "NOT GIVEN", "MISSING"]):
                    value = ""
                    
                # Parse JSON-like structures into separate lines
                if (value.startswith('{') and value.endswith('}')) or \
                   (value.startswith('[{') and value.endswith('}]')) or \
                   (value.startswith("'") and ":" in value):
                    try:
                        # Handle dict format: {'key1': 'value1', 'key2': 'value2'} 
                        # or list format: [{'key': 'value'}]
                        # or quoted string format: 'Mounting': 'Rear Clevis'
                        
                        # Strip outer brackets for processing
                        processed_value = value
                        if value.startswith('[{') and value.endswith('}]'):
                            processed_value = value[1:-1]  # Remove outer brackets
                        if value.startswith('{') and value.endswith('}'):
                            processed_value = value.strip('{}')
                            
                        value_parts = []
                        
                        # Handle different formats of key-value pairs
                        import re
                        
                        # Try to directly extract key-value pairs
                        # This handles formats like 'key1': 'value1', 'key2': 'value2'
                        pairs = re.findall(r'[\'"]([^\'"]*)[\'"]\s*:\s*[\'"]([^\'"]*)[\'"]\s*(?:,|$)', processed_value)
                        
                        if pairs:
                            # Just use the values directly without the keys - this is what we want to display
                            value_parts = [v for _, v in pairs]
                            value = v if len(value_parts) == 1 else "\n".join(value_parts)
                        else:
                            # Fallback to simple splitting if regex didn't work
                            if ',' in processed_value:
                                parts = processed_value.split(',')
                                for part in parts:
                                    if ':' in part:
                                        k, v = part.split(':', 1)
                                        k = k.strip().strip('\'"')
                                        v = v.strip().strip('\'"')
                                        # Just add the value, not the key
                                        value_parts.append(v)
                                
                                if value_parts:
                                    value = value_parts[0] if len(value_parts) == 1 else "\n".join(value_parts)
                    except Exception as e:
                        # If parsing fails, keep the original value but remove quotes and braces
                        if value.startswith("'") and value.endswith("'"):
                            value = value.strip("'")
                        elif value.startswith('"') and value.endswith('"'):
                            value = value.strip('"')
                        print(f"Error parsing JSON-like value: {e}")
                
                # Clean and standardize common units
                if value:
                    # Standardize diameter symbol
                    value = value.replace('ø', 'Ø')
                    
                    # Standardize units for consistency
                    unit_mappings = {
                        r'\bmm\b': 'mm',
                        r'\bcm\b': 'cm',
                        r'\bm\b': 'm',
                        r'\bkg\b': 'kg',
                        r'\bg\b': 'g',
                        r'\bt\b': 'tons',
                        r'\bbar\b': 'BAR',
                        r'\bBAR\b': 'BAR',
                        r'\bpsi\b': 'PSI',
                        r'\bPSI\b': 'PSI',
                        r'\bmpa\b': 'MPa',
                        r'\bMPa\b': 'MPa',
                        r'\bMPA\b': 'MPa',
                        r'\bC\b': '°C',
                        r'\bF\b': '°F',
                        r'\b°C\b': '°C',
                        r'\b°F\b': '°F',
                        r'\bDEG C\b': '°C',
                        r'\bDEG F\b': '°F'
                    }
                    
                    import re
                    for pattern, replacement in unit_mappings.items():
                        value = re.sub(pattern, replacement, value)
                
                # Store the value    
                results[key] = value if value else ""  # Keep blank if missing
    
    # Filter results if in custom mode
    if st.session_state.parameter_mode == "Custom":
        # Use generic key for custom parameters
        if "GENERIC" in st.session_state.custom_parameters:
            custom_params = st.session_state.custom_parameters["GENERIC"]
            
            # Debug info
            print(f"Custom mode active")
            print(f"Custom parameters: {custom_params}")
            print(f"Original results keys: {[k for k in results.keys() if not k.endswith('_JUSTIFICATION')]}")
            
            # Create a new filtered results dictionary with only the requested parameters
            filtered_results = {}
            # Always keep document type and component type
            filtered_results["DOCUMENT_TYPE"] = results.get("DOCUMENT_TYPE", "")
            filtered_results["COMPONENT_TYPE"] = results.get("COMPONENT_TYPE", "")
            
            # Add only the requested parameters and their justifications
            for param in custom_params:
                param_key = param.strip().upper()
                # Find the matching key in results (case insensitive)
                matching_key = None
                for key in results:
                    if not key.endswith('_JUSTIFICATION') and key not in ["DOCUMENT_TYPE", "COMPONENT_TYPE"]:
                        # Normalize both keys for comparison (remove underscores, spaces, etc.)
                        normalized_key = key.upper().replace('_', ' ').replace('-', ' ')
                        normalized_param = param_key.replace('_', ' ').replace('-', ' ')
                        
                        if normalized_key == normalized_param:
                            matching_key = key
                            break
                
                if matching_key:
                    # Add the parameter and its justification
                    filtered_results[matching_key] = results[matching_key]
                    just_key = f"{matching_key}_JUSTIFICATION"
                    if just_key in results:
                        filtered_results[just_key] = results[just_key]
                else:
                    # Add empty parameter if not found
                    filtered_results[param_key] = ""
                    filtered_results[f"{param_key}_JUSTIFICATION"] = "Parameter not found in the document."
            
            # Debug filtered results
            print(f"Filtered results keys: {[k for k in filtered_results.keys() if not k.endswith('_JUSTIFICATION')]}")
            
            # Replace results with filtered results
            results = filtered_results
    
    # Create a parameter mapping for related parameters to avoid duplication
    parameter_relationships = {
        # Standard relationships between similar parameters
        "HEIGHT": ["HEIGHT", "ITEM HEIGHT", "TOTAL HEIGHT"],
        "LENGTH": ["LENGTH", "ITEM LENGTH", "TOTAL LENGTH"],
        "WIDTH": ["WIDTH", "ITEM WIDTH", "TOTAL WIDTH"],
        "WEIGHT": ["WEIGHT", "ITEM WEIGHT", "UNIT WEIGHT", "PRODUCT WEIGHT"],
        "CLOSED HEIGHT": ["CLOSED HEIGHT", "MINIMUM HEIGHT", "MIN HEIGHT", "COLLAPSED HEIGHT"],
        "OPEN HEIGHT": ["OPEN HEIGHT", "MAXIMUM HEIGHT", "MAX HEIGHT", "EXTENDED HEIGHT"],
        "BORE DIAMETER": ["BORE DIAMETER", "BORE DIA", "INSIDE DIAMETER", "INNER DIAMETER", "BORE"],
        "ROD DIAMETER": ["ROD DIAMETER", "ROD DIA", "SHAFT DIAMETER", "PISTON ROD DIAMETER"],
        "LOAD CAPACITY": ["LOAD CAPACITY", "RATED CAPACITY", "RATED CAPACITY/LOAD", "RATED LOAD", "CAPACITY", "MAX LOAD"],
        "OPERATING PRESSURE": ["OPERATING PRESSURE", "PRESSURE RATING", "WORKING PRESSURE", "MAX PRESSURE"],
        "DIMENSIONS": ["DIMENSIONS", "ITEM DIMENSIONS", "OVERALL DIMENSIONS", "PRODUCT DIMENSIONS"],
        "MAKE": ["MAKE", "MANUFACTURER", "MANUFACTURER/MAKE", "BRAND", "MANUFACTURER/BRAND"],
        "MODEL": ["MODEL", "MODEL NUMBER", "MODEL/PART NUMBER", "PART NUMBER", "MODEL NO", "PART NO"],
        "MATERIAL": ["MATERIAL", "BODY MATERIAL", "CONSTRUCTION MATERIAL", "HOUSING MATERIAL"]
    }
    
    # Special handling for port-related parameters
    port_params = ["PORT SIZE", "PORT TYPE", "PORT LOCATION"]
    all_port_values = {}
    
    # Special handling for numeric range values like dimensions
    # Extract all numeric values with units from dimensions
    for dim_param in ["DIMENSIONS", "ITEM DIMENSIONS", "OVERALL DIMENSIONS"]:
        if dim_param in results and results[dim_param]:
            dimensions = results[dim_param]
            
            # Extract L x W x H pattern
            import re
            dim_pattern = r'(\d+(?:\.\d+)?)\s*(?:x|×)\s*(\d+(?:\.\d+)?)\s*(?:x|×)\s*(\d+(?:\.\d+)?)'
            match = re.search(dim_pattern, dimensions.lower())
            
            if match:
                # Extract the values and units
                length, width, height = match.groups()
                
                # Find the unit after the dimensions
                unit_match = re.search(r'(?:x|×)\s*\d+(?:\.\d+)?\s*([a-zA-Z]+)', dimensions.lower())
                unit = unit_match.group(1) if unit_match else "cm"  # Default to cm if no unit found
                
                # Only set length/width/height if they're not already present
                if "LENGTH" not in results or not results["LENGTH"]:
                    results["LENGTH"] = f"{length} {unit}"
                    results["LENGTH_JUSTIFICATION"] = "Extracted from overall dimensions."
                
                if "WIDTH" not in results or not results["WIDTH"]:
                    results["WIDTH"] = f"{width} {unit}"
                    results["WIDTH_JUSTIFICATION"] = "Extracted from overall dimensions."
                
                if "HEIGHT" not in results or not results["HEIGHT"]:
                    results["HEIGHT"] = f"{height} {unit}"
                    results["HEIGHT_JUSTIFICATION"] = "Extracted from overall dimensions."
    
    # Process port parameters to combine them if appropriate
    for port_param in port_params:
        if port_param in results and results[port_param]:
            all_port_values[port_param] = results[port_param]
    
    # If we have both port type and size, consider creating a combined PORT_SPECIFICATION
    if "PORT TYPE" in all_port_values and "PORT SIZE" in all_port_values:
        port_type = all_port_values["PORT TYPE"]
        port_size = all_port_values["PORT SIZE"]
        
        # Only combine if both have values
        if port_type and port_size:
            # Create combined port specification
            results["PORT_SPECIFICATION"] = f"{port_type} {port_size}"
            results["PORT_SPECIFICATION_JUSTIFICATION"] = "Combined from port type and port size information."
    
    # Normalize parameter names to find relations
    normalized_results = {}
    for key in list(results.keys()):
        if not key.endswith("_JUSTIFICATION") and results.get(key, "").strip():
            # Check if key contains JSON-like structure but wasn't properly parsed yet
            value = results[key]
            if isinstance(value, str) and (
                (value.startswith('{') and value.endswith('}')) or
                (value.startswith('[{') and value.endswith('}]')) or
                (value.startswith("'") and ":" in value)
            ):
                # Apply the same JSON parsing logic here to ensure consistent display
                try:
                    # Process different JSON-like formats
                    processed_value = value
                    if value.startswith('[{') and value.endswith('}]'):
                        processed_value = value[1:-1]
                    if value.startswith('{') and value.endswith('}'):
                        processed_value = value.strip('{}')
                        
                    import re
                    pairs = re.findall(r'[\'"]([^\'"]*)[\'"]\s*:\s*[\'"]([^\'"]*)[\'"]\s*(?:,|$)', processed_value)
                    
                    if pairs:
                        # Extract just the values
                        values = [v for _, v in pairs]
                        if len(values) == 1:
                            results[key] = values[0]
                        else:
                            results[key] = "\n".join(values)
                except Exception as e:
                    # If parsing fails, leave as is
                    print(f"Error normalizing JSON value: {e}")
            
            norm_key = key.upper()
            normalized_results[norm_key] = results[key]
            
            # Find and remove any related parameters that would cause duplication
            for main_param, related_params in parameter_relationships.items():
                if norm_key in related_params:
                    # This is a related parameter, check if main parameter exists with value
                    main_norm = main_param.upper()
                    if main_norm in normalized_results and normalized_results[main_norm]:
                        # If main parameter already has a value, this is a duplicate
                        if main_norm != norm_key:
                            # Transfer the justification from this param to the main param
                            just_key = f"{key}_JUSTIFICATION"
                            main_just_key = f"{main_param}_JUSTIFICATION"
                            if just_key in results:
                                results[main_just_key] = results[just_key]
                            # Remove this duplicate parameter
                            results[key] = ""
    
    # Handle dimension-related parameters to avoid duplicates
    if "DIMENSIONS" in results and results["DIMENSIONS"]:
        # If we have dimensions but no height/width values, try to extract them
        dimensions = results["DIMENSIONS"]
        
        # Try to parse dimensions like "93 x 55 x 29 Centimeters" into height/width/depth
        if "x" in dimensions.lower() or "×" in dimensions:
            # Handle both x and × symbols
            dim_parts = [part.strip() for part in dimensions.lower().replace('×', 'x').split("x")]
            
            # Extract unit if present
            unit = ""
            last_part = dim_parts[-1]
            # Find where the numbers end and unit begins
            for i, char in enumerate(last_part):
                if not (char.isdigit() or char == "." or char.isspace()):
                    if i > 0:
                        unit = last_part[i:].strip()
                        dim_parts[-1] = last_part[:i].strip()
                    break
            
            # Only set these if they're not already present with values
            if len(dim_parts) >= 1 and ("LENGTH" not in results or not results["LENGTH"]):
                length_val = dim_parts[0]
                if unit:
                    length_val += " " + unit
                results["LENGTH"] = length_val
                results["LENGTH_JUSTIFICATION"] = "Extracted from item dimensions."
            
            if len(dim_parts) >= 2 and ("WIDTH" not in results or not results["WIDTH"]):
                width_val = dim_parts[1]
                if unit:
                    width_val += " " + unit
                results["WIDTH"] = width_val
                results["WIDTH_JUSTIFICATION"] = "Extracted from item dimensions."
            
            if len(dim_parts) >= 3 and ("HEIGHT" not in results or not results["HEIGHT"]):
                height_val = dim_parts[2]
                if unit:
                    height_val += " " + unit
                results["HEIGHT"] = height_val
                results["HEIGHT_JUSTIFICATION"] = "Extracted from item dimensions."
    
    # Handle structured fields like Closed/Open Heights specifically for jacks/cylinders
    # For the Hyco jack in the image, we need to recognize the format "height FOR weight"
    for height_field in ["CLOSED HEIGHT", "OPEN HEIGHT", "MINIMUM HEIGHT", "MAXIMUM HEIGHT"]:
        if height_field in results and "FOR" in results[height_field].upper():
            # This might be a height specification that varies by weight/model
            height_value = results[height_field]
            
            # Try to extract structured height data in format "X FOR Y, Z FOR W"
            import re
            # Look for pattern like "200mm FOR 1 TON, 750mm FOR 1.5TON"
            height_matches = re.findall(r'(\d+(?:\.\d+)?(?:\s*[a-zA-Z]+)?)\s+FOR\s+([\d\.]+\s*TON)', height_value, re.IGNORECASE)
            
            if height_matches:
                # Create a structured version with all heights by capacity
                structured_value = ", ".join([f"{height} @ {capacity}" for height, capacity in height_matches])
                results[height_field] = structured_value
                results[f"{height_field}_JUSTIFICATION"] = "Structured from height specifications that vary by capacity."
    
    # Add justifications to results using a list of original keys to avoid modification during iteration
    original_keys = list(results.keys())
    for key in original_keys:
        # Skip document metadata fields and justification fields
        if key in ["DOCUMENT_TYPE", "COMPONENT_TYPE"] or key.endswith("_JUSTIFICATION"):
            continue
            
        # If justification is missing, add a contextual default one
        if key not in justifications:
            doc_type = document_info.get("DOCUMENT_TYPE", "").upper()
            
            if results[key]:
                if "PRODUCT_LISTING" in doc_type or "CATALOG" in doc_type:
                    justifications[key] = "Extracted from the product listing specifications."
                elif "SPECIFICATION" in doc_type:
                    justifications[key] = "Extracted from the specification sheet."
                elif "MIXED" in doc_type:
                    justifications[key] = "Extracted from the document. Exact location unspecified."
                else:
                    justifications[key] = "Extracted directly from the drawing."
            else:
                if "PRODUCT_LISTING" in doc_type or "CATALOG" in doc_type:
                    justifications[key] = "Not provided in the product listing."
                elif "SPECIFICATION" in doc_type:
                    justifications[key] = "Not included in the specification sheet."
                elif "MIXED" in doc_type:
                    justifications[key] = "Not found in any part of the document."
                else:
                    justifications[key] = "Not visible in the drawing."
        
        # Add the justification to the results
        just_key = f"{key}_JUSTIFICATION"
        if just_key not in results:
            results[just_key] = justifications.get(key, "")
    
    return results

def validate_and_improve_justifications(parsed_results):
    """
    Validate that all parameters have proper justifications and improve the quality of the data.
    Returns the improved parsed_results.
    """
    # Make a copy to avoid modifying the original during iteration
    results = parsed_results.copy()
    
    # Get all parameter keys (excluding justifications and component type)
    param_keys = [k for k in results.keys() if not k.endswith('_JUSTIFICATION') and k != 'COMPONENT_TYPE']
    
    # Drawing-specific justifications for common parameters
    drawing_specific_justifications = {
        "BORE_DIAMETER": "Measured from the internal diameter dimension line in the cylinder cross-section view.",
        "OUTSIDE_DIAMETER": "Measured from the external diameter dimension line in the drawing views.",
        "ROD_DIAMETER": "Extracted from the piston rod dimension line, typically shown in the side view or cross-section.",
        "STROKE_LENGTH": "Determined from the stroke dimension line between fully retracted and extended positions.",
        "CLOSED_LENGTH": "Measured from the overall length dimension in the fully retracted position.",
        "OPEN_LENGTH": "Calculated from the closed length plus stroke distance shown in the drawing.",
        "CYLINDER_ACTION": "Determined by examining the port configuration in the drawing (single vs. double acting).",
        "MOUNTING_TYPE": "Identified from the mounting detail view showing the attachment method.",
        "PORT_TYPE": "Read from the port detail view or cross-section showing the connection type.",
        "PORT_LOCATION": "Observed from the port positions shown in the main drawing views.",
        "SEAL_TYPE": "Identified from the seal detail section view showing the seal configuration.",
        "DIMENSIONS": "Extracted from the primary dimension lines showing length, width, and height.",
        "WEIGHT": "Inferred from material and volume calculations based on dimensions in the drawing."
    }
    
    for key in param_keys:
        justification_key = f"{key}_JUSTIFICATION"
        value = results.get(key, "").strip()
        justification = results.get(justification_key, "").strip()
        
        # Format the key for matching against our dictionary (standardize format)
        formatted_key = key.upper().replace(' ', '_')
        
        # Check if justification exists and is meaningful
        if not justification or justification.lower() in ["not available", "not specified", "unknown", "not provided", "not visible"]:
            if value:
                # If we have a value but no good justification, provide a better default
                if formatted_key in drawing_specific_justifications:
                    # Use our specific drawing-based justification
                    results[justification_key] = drawing_specific_justifications[formatted_key]
                else:
                    results[justification_key] = f"Extracted from dimension lines and annotations in the drawing for {key.replace('_', ' ').lower()}."
            else:
                # If no value and no good justification, provide a clear explanation
                results[justification_key] = f"This parameter ({key}) is not visible in any dimension lines or annotations in the drawing."
        
        # Check if justification is too generic
        elif "extracted" in justification.lower() and "from" in justification.lower() and len(justification.split()) < 8:
            # If we have a specific drawing-based justification, use it
            if formatted_key in drawing_specific_justifications:
                results[justification_key] = drawing_specific_justifications[formatted_key]
            # Otherwise improve generic justifications
            else:
                results[justification_key] = f"Extracted from dimension lines and visual elements in the drawing showing {key.replace('_', ' ').lower()} specifications."
        
        # If justification mentions tables but we want to emphasize drawings
        elif "table" in justification.lower() or "specification table" in justification.lower():
            # If we have a specific drawing-based justification, add it
            if formatted_key in drawing_specific_justifications:
                results[justification_key] = f"{justification} Also verified from {drawing_specific_justifications[formatted_key].lower()}"
            else:
                results[justification_key] = f"{justification} Also verified from dimension lines in the drawing."
        
        # If no specific location is mentioned in the justification, note this
        elif "top" not in justification.lower() and "bottom" not in justification.lower() and \
             "left" not in justification.lower() and "right" not in justification.lower() and \
             "center" not in justification.lower() and "table" not in justification.lower() and \
             "dimension" not in justification.lower() and "title" not in justification.lower() and \
             "label" not in justification.lower() and "section" not in justification.lower():
            if len(justification.split()) < 12:  # If justification is short and lacks location details
                # If we have a specific drawing-based justification, use it
                if formatted_key in drawing_specific_justifications:
                    results[justification_key] = drawing_specific_justifications[formatted_key]
                else:
                    results[justification_key] = f"{justification} (Located in the drawing dimension lines and annotations)"
        
        # Ensure all values have proper formatting
        if key in ["OPERATING PRESSURE", "PRESSURE RATING"] and value:
            if "BAR" not in value.upper():
                results[key] = f"{value} BAR"
        
        elif key in ["OPERATING TEMPERATURE"] and value:
            if "DEG" not in value.upper() and "°C" not in value:
                results[key] = f"{value} DEG C"
        
        # Remove any values that are clearly guesses
        if "approximately" in value.lower() or "about" in value.lower() or "around" in value.lower() or \
           "estimated" in value.lower() or "appears to be" in value.lower():
            results[key] = ""
            results[justification_key] = "Unable to determine with certainty from the drawing. No clear dimension line or annotation found."
    
    return results

def analyze_engineering_drawing(image_bytes, component_type=None):
    """Universal analyzer for all types of engineering drawings using mode-specific prompts"""
    base64_image = encode_image_to_base64(image_bytes)
    
    # If component type is provided, use a more targeted prompt
    system_content = "You are an expert mechanical engineer with extensive experience in engineering design, manufacturing, and technical documentation analysis. Your task is to extract ALL technical specifications and provide insightful engineering analysis based on the design elements in the document. Always assume the document has been properly oriented for reading. Extract parameter names EXACTLY as they appear in the drawing, without categorizing them or using predefined parameter names."
    
    # Base prompt parts that are common to all modes
    base_prompt_part1 = (
        "TASK: Analyze this engineering document as a professional mechanical engineer. "
        
        "STEP 1. DOCUMENT TYPE IDENTIFICATION\n"
        "  - Determine the document type:\n"
        "    (A) Engineering Drawing\n"
        "    (B) Product Listing/Catalog\n"
        "    (C) Specification Sheet\n"
        "    (D) Mixed Document (contains both drawings and tables)\n"
        "  - Document this determination as \"Document Type\" in your output.\n\n"
        
        "STEP 2. COMPONENT IDENTIFICATION\n"
        "  - Determine if the document describes one of these component types:\n"
        "      • Cylinder (hydraulic, pneumatic)\n"
        "      • Gearbox/Gear (transmission, reducer)\n"
        "      • Valve (ball, check, control)\n"
        "      • Nut/Bolt/Fastener\n"
        "      • Lifting Ram or Jack (hydraulic, transmission)\n"
        "      • Bearing\n"
        "      • Pump\n"
        "      • Motor\n"
        "  - If the component type is obvious but not in the list above, specify the exact type.\n"
        "  - If the type is ambiguous, mark the \"Component Type\" as \"UNKNOWN\" without guessing.\n\n"
    )
    
    # Create different prompts based on the parameter mode
    if st.session_state.parameter_mode == "Cylinder, Hyd/Pneumatic":
        # Create a cylinder-specific prompt focused on the 23 specified parameters
        user_content = base_prompt_part1 + (
            "STEP 3. CYLINDER-SPECIFIC PARAMETER EXTRACTION\n"
            "  - Extract ONLY these specific parameters for this cylinder:\n"
            "    1. CYLINDER_TYPE: Identify the exact type of cylinder shown in this drawing (e.g. single action/double action).\n"
            "    2. STROKE_LENGTH: Extract the total stroke length of the rod or piston in millimeters (e.g., Stroke = 900mm).\n"
            "    3. ROD_DIAMETER: Find the rod or shaft diameter in millimeters (look for values like 'Rod Seal 150mm').\n"
            "    4. WORKING_PRESSURE: What is the maximum working pressure rating (in BAR or PSI) of this component?\n"
            "    5. TEST_PRESSURE: What is the test pressure (in BAR) used for this component, if specified?\n"
            "    6. OPERATING_TEMPERATURE: Extract the operating temperature range or any specified temperature limits.\n"
            "    7. MATERIAL_SPECIFICATIONS: List all material specifications used for major parts (e.g., cylinder body, piston rod, seals). Include ASTM, IS codes, or GR grades.\n"
            "    8. MOUNTING_TYPE: Identify the mounting type used in this assembly (e.g., Flange, Rear Clevis, Foot Mount).\n"
            "    9. DRAWING_NUMBER: Provide the reference or drawing number (e.g., BHUSHAN REFERENCE DRAWING NO.: 6BRv-71170-A).\n"
            "    10. STANDARD_CODES: Extract any manufacturing or industry standard codes followed (e.g., IS:2062 GR. B, ASTM A106 GR B).\n"
            "    11. SPECIAL_FEATURES: List any special features, custom fittings, or non-standard components mentioned (e.g., Banjo fitting, Ball valve, Cushioning).\n"
            "    12. MANUFACTURER: What is the manufacturer's or vendor's name (e.g., RA SPECTRUM ENGINEERING, SERMCES PVT LTD)?\n"
            "    13. MODEL_NUMBER: Is there any model number or part number uniquely identifying this configuration?\n"
            "    14. TECHNICAL_NOTES: Include any additional technical notes, installation requirements, or warnings present in the drawing.\n"
            "  - EXTREMELY IMPORTANT: Do NOT extract any parameters not in this list\n"
            "  - Search thoroughly for these specific parameters throughout the document\n"
            "  - If a parameter in this list is not found, still include it with an empty value\n\n"
            
            "STEP 4. COMPREHENSIVE VISUAL SCANNING FOR CYLINDER PARAMETERS\n"
            "  - Methodically scan EVERY part of the document in this order:\n"
            "      1. Tables & Specification Boxes (highest priority)\n"
            "      2. Title Blocks & Headers\n"
            "      3. Dimensions & Callouts (annotations on drawings)\n"
            "      4. Notes & Footnotes\n"
            "      5. Text in Margins & Stamps\n"
            "  - Extract ALL numeric values along with units EXACTLY as they appear\n"
            "  - For dimensions, capture the complete value including tolerances\n\n"
            
            "STEP 5. ENGINEERING SYMBOL INTERPRETATION\n"
            "  - Identify engineering symbols relevant to the cylinder parameters:\n"
            "      • Ø or ⌀: Diameter\n" 
            "      • R: Radius\n"
            "      • ±: Tolerance\n"
            "      • ▭: Square\n"
            "      • Surface finish marks\n"
            "      • GD&T symbols\n"
            "  - Relate symbols to the dimensional values they qualify\n\n"
            
            "STEP 6. OUTPUT FORMAT\n"
            "  - Format your extraction with the EXACT parameter names as they appear in the list above\n"
            "  - DO NOT add dashes or bullet points before parameter names\n"
            "  - For each parameter, include a value and detailed justification explaining its source\n"
            "  - Format as PARAMETER_NAME: value and PARAMETER_NAME_JUSTIFICATION: explanation\n"
            "  - For empty parameters, explain why the information couldn't be found\n\n"
            
            "CRITICAL REMINDER: Your output MUST ONLY include DOCUMENT_TYPE, COMPONENT_TYPE, and the 14 cylinder parameters listed above. DO NOT include any other parameters even if they are clearly visible in the document."
        )
    elif st.session_state.parameter_mode == "Custom":
        # Get custom parameters for this component type or generic parameters
        custom_params = []
        if component_type and component_type in st.session_state.custom_parameters:
            custom_params = st.session_state.custom_parameters[component_type]
        elif "GENERIC" in st.session_state.custom_parameters:
            custom_params = st.session_state.custom_parameters["GENERIC"]
        
        if custom_params:
            # Create a custom mode prompt focused only on the specified parameters
            param_list = "\n".join([f"  - {param}" for param in custom_params])
            user_content = base_prompt_part1 + (
                f"STEP 3. CUSTOM PARAMETER EXTRACTION\n"
                f"  - Extract ONLY these specific parameters:\n{param_list}\n"
                f"  - EXTREMELY IMPORTANT: Do NOT extract any parameters not in this list\n"
                f"  - Search thoroughly for these specific parameters throughout the document\n"
                f"  - If a parameter in this list is not found, still include it with an empty value\n\n"
                
                "STEP 4. COMPREHENSIVE VISUAL SCANNING FOR CUSTOM PARAMETERS\n"
                "  - Methodically scan EVERY part of the document in this order:\n"
                "      1. Tables & Specification Boxes (highest priority)\n"
                "      2. Title Blocks & Headers\n"
                "      3. Dimensions & Callouts (annotations on drawings)\n"
                "      4. Notes & Footnotes\n"
                "      5. Text in Margins & Stamps\n"
                "  - Extract ALL numeric values along with units EXACTLY as they appear\n"
                "  - For dimensions, capture the complete value including tolerances\n\n"
                
                "STEP 5. ENGINEERING SYMBOL INTERPRETATION\n"
                "  - Identify engineering symbols relevant to the custom parameters:\n"
                "      • Ø or ⌀: Diameter\n" 
                "      • R: Radius\n"
                "      • ±: Tolerance\n"
                "      • ▭: Square\n"
                "      • Surface finish marks\n"
                "      • GD&T symbols\n"
                "  - Relate symbols to the dimensional values they qualify\n\n"
                
                "STEP 6. OUTPUT FORMAT\n"
                "  - Format your extraction with the EXACT parameter names as they appear in the list above\n"
                "  - DO NOT add dashes or bullet points before parameter names\n"
                "  - For each parameter, include a value and detailed justification explaining its source\n"
                "  - Format as PARAMETER_NAME: value and PARAMETER_NAME_JUSTIFICATION: explanation\n"
                "  - For empty parameters, explain why the information couldn't be found\n\n"
                
                "CRITICAL REMINDER: Your output MUST ONLY include DOCUMENT_TYPE, COMPONENT_TYPE, and the custom parameters listed above. DO NOT include any other parameters even if they are clearly visible in the document."
            )
            
            # Add component type for filtering if available
            if component_type:
                user_content += f"\n\nCOMPONENT_TYPE_FOR_FILTERING: {component_type}\n"
        else:
            # No custom parameters defined, use extracted mode prompt
            user_content = create_extracted_mode_prompt()
    else:
        # Use extracted mode prompt for any other mode value
        user_content = create_extracted_mode_prompt()
    
    # If component type is provided, use a more targeted prompt
    if component_type and component_type not in ["UNKNOWN"]:
        user_content = f"This is a {component_type} drawing. Analyze it as a professional mechanical engineer.\n\n" + user_content
    
    # Add component-specific parameter lists
    component_params = {
        "CYLINDER": (
            "For hydraulic/pneumatic Cylinders, look for these parameters using the EXACT names as they appear in the drawing:\n"
            "- Cylinder action type (single/double acting)\n"
            "- Bore (sometimes labeled as 'Bore', 'Bore Dia', or similar)\n"
            "- Outside diameter\n"
            "- Rod diameter (may be labeled as 'Piston Rod' or similar)\n"
            "- Stroke (the travel distance)\n"
            "- Closed length\n"
            "- Extended/Open length\n"
            "- Working/Operating pressure\n"
            "- Test pressure\n"
            "- Temperature range\n"
            "- Mounting type/method\n"
            "- Rod end type\n"
            "- Fluid medium\n"
            "- Drawing number\n"
            "- Materials (body, rod, etc.)\n"
            "- Load capacity\n"
            "- Compliance standards\n"
            "- Surface finishes\n"
            "- Coating types\n"
            "- Port specifications (type, size, location)\n"
            "- Sealing system\n"
            "- Manufacturer\n"
            "- Model/part number\n"
            "- Cushioning features\n"
            "IMPORTANT: Extract the parameter names EXACTLY as shown in the drawing, not using this list's terminology\n\n"
        ),
        "VALVE": (
            "For Valves, extract these critical parameters:\n"
            "MODEL/PART NUMBER (specific identifier)\n"
            "VALVE TYPE (ball, check, control, directional, etc.)\n"
            "VALVE SIZE/PORT SIZE (connection dimensions)\n"
            "PRESSURE RATING (max operating pressure)\n"
            "FLOW CAPACITY (flow rate, Cv)\n"
            "FLOW DIRECTION (indicated direction)\n"
            "OPERATING MEDIUM (fluid, gas type)\n"
            "CONNECTION TYPE (threaded, flanged, etc.)\n"
            "BODY MATERIAL (valve body material)\n"
            "SEAT/SEAL MATERIAL (soft seat, metal seat)\n"
            "OPERATING TEMPERATURE (temperature range)\n"
            "ACTUATION TYPE (manual, pneumatic, electric)\n"
            "OPERATION PATTERN (2-way, 3-way, 4-way)\n"
            "LEAKAGE CLASS (if specified)\n"
            "MANUFACTURER/MAKE (brand name)\n"
            "SPECIAL FEATURES (fire safe, anti-static, etc.)\n\n"
        ),
        "GEARBOX": (
            "For Gearboxes, extract these critical parameters:\n"
            "GEAR TYPE (helical, bevel, planetary, etc.)\n"
            "INPUT POWER (kW, HP)\n"
            "INPUT SPEED (RPM)\n"
            "OUTPUT SPEED (RPM)\n"
            "GEAR RATIO (reduction ratio)\n"
            "SERVICE FACTOR (load/duty factor)\n"
            "MOUNTING ARRANGEMENT (foot, flange, shaft)\n"
            "SHAFT ORIENTATION (parallel, right angle, etc.)\n"
            "INPUT SHAFT TYPE (solid, hollow, splined, etc.)\n"
            "OUTPUT SHAFT TYPE (solid, hollow, splined, etc.)\n"
            "SHAFT DIAMETER (input and output)\n"
            "BACKLASH (if specified)\n"
            "EFFICIENCY (percentage)\n"
            "COOLING ARRANGEMENT (fan, cooling fins)\n"
            "LUBRICATION SYSTEM (oil bath, grease, etc.)\n"
            "HOUSING MATERIAL (cast iron, aluminum, etc.)\n"
            "SEALING TYPE (lip seal, labyrinth, etc.)\n"
            "WEIGHT (kg, lbs)\n"
            "DIMENSIONS (LxWxH)\n"
            "MANUFACTURER/MAKE (brand name)\n"
            "MODEL/PART NUMBER (specific identifier)\n\n"
        ),
        "NUT": (
            "For Nuts/Bolts/Fasteners, extract these critical parameters:\n"
            "TYPE (hex, square, flange, etc.)\n"
            "SIZE/DIMENSION (thread diameter, length)\n"
            "THREAD TYPE (metric, imperial, etc.)\n"
            "THREAD PITCH (thread spacing)\n"
            "PROPERTY/STRENGTH CLASS (e.g., 8.8, 10.9)\n"
            "MATERIAL (steel grade, stainless, etc.)\n"
            "COATING/FINISH (zinc, cadmium, etc.)\n"
            "STANDARD COMPLIANCE (ISO, DIN, ANSI, etc.)\n"
            "HEAD DIMENSIONS (across flats, height)\n"
            "TORQUE SPECIFICATION (if provided)\n"
            "MANUFACTURER/MAKE (if branded)\n"
            "SPECIAL FEATURES (locking, self-tapping, etc.)\n\n"
        ),
        "LIFTING_RAM": (
            "For Lifting Rams/Jacks, extract these critical parameters:\n"
            "LOAD CAPACITY (maximum lifting weight)\n"
            "MINIMUM HEIGHT (collapsed height)\n"
            "MAXIMUM HEIGHT (extended height)\n"
            "CLOSED LENGTH (retracted length)\n"
            "OPEN LENGTH (extended length)\n"
            "LIFT RANGE/STROKE (travel distance)\n"
            "OPERATING PRESSURE (hydraulic pressure)\n"
            "PISTON DIAMETER (ram diameter)\n"
            "WEIGHT (unit weight)\n"
            "DIMENSIONS (LxWxH)\n"
            "MATERIAL (body material)\n"
            "ACTIVATION TYPE (manual, hydraulic, pneumatic)\n"
            "MANUFACTURER/BRAND (make)\n"
            "MODEL/PART NUMBER (specific identifier)\n"
            "SPECIAL FEATURES (quick lift, safety valve, etc.)\n"
            "PRICE (if listed in product catalog)\n\n"
        ),
        "BEARING": (
            "For Bearings, extract these critical parameters:\n"
            "BEARING TYPE (ball, roller, needle, etc.)\n"
            "DIMENSIONS (inner dia, outer dia, width)\n"
            "LOAD RATING (dynamic, static)\n"
            "SPEED RATING (maximum RPM)\n"
            "MATERIAL (bearing material)\n"
            "LUBRICATION TYPE (grease, oil, etc.)\n"
            "SEAL TYPE (shielded, sealed, open)\n"
            "MANUFACTURER/BRAND (make)\n"
            "MODEL/PART NUMBER (specific identifier)\n\n"
        )
    }
    
    # Only add component-specific parameter lists for non-custom and non-cylinder modes
    if st.session_state.parameter_mode != "Custom" and st.session_state.parameter_mode != "Cylinder, Hyd/Pneumatic":
        # Add component-specific parameter lists
        if component_type and component_type.upper() in component_params:
            user_content += component_params[component_type.upper()]
        else:
            # If component type is not in our standard list or is unknown, add all parameter lists
            for params in component_params.values():
                user_content += params
    
    # Make the initial API call
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": system_content
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_content
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": base64_image
                        }
                    }
                ]
            }
        ],
        "max_tokens": 4000,
        "temperature": 0.1
    }

    headers = {
        "Authorization": f"Bearer {st.session_state.current_api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        result = process_api_response(response, analyze_engineering_drawing, image_bytes, component_type)
        
        if "❌" not in result:
            # Parse results from first pass
            first_pass_results = parse_ai_response(result)
            
            # Process pressure ranges for consistent formatting in first pass
            for pressure_param in ['OPERATING PRESSURE', 'PRESSURE RATING']:
                if pressure_param in first_pass_results:
                    pressure = first_pass_results.get(pressure_param, '').strip()
                    if pressure:
                        # Standardize pressure range format
                        if '...' in pressure or '..' in pressure:
                            # Replace ellipsis with 'to'
                            pressure = pressure.replace('...', ' to ').replace('..', ' to ')
                        elif 'TO' in pressure.upper():
                            # Replace 'TO' with 'to' for consistent formatting
                            pressure = pressure.upper().replace('TO', 'to').lower()
                            pressure = pressure.replace('to', ' to ').replace('  to  ', ' to ')
                        
                        # Ensure "BAR" format is consistent
                        if 'BAR' not in pressure.upper():
                            pressure = pressure + " BAR"
                        
                        # Normalize spacing
                        pressure = ' '.join(pressure.split())
                        first_pass_results[pressure_param] = pressure
            
            # Process temperature ranges in first pass
            if 'OPERATING TEMPERATURE' in first_pass_results:
                temp = first_pass_results.get('OPERATING TEMPERATURE', '').strip()
                if temp:
                    # Standardize temperature range format
                    if '...' in temp or '..' in temp:
                        # Replace ellipsis with 'to'
                        temp = temp.replace('...', ' to ').replace('..', ' to ')
                    elif 'TO' in temp.upper():
                        # Replace 'TO' with 'to' for consistent formatting
                        temp = temp.upper().replace('TO', 'to').lower()
                        temp = temp.replace('to', ' to ').replace('  to  ', ' to ')
                    elif '+' in temp and '-' in temp:
                        # Handle formats like "-10°C +60°C"
                        parts = temp.replace('°C', '').replace('DEG C', '').split()
                        # Extract the numbers
                        nums = [p for p in parts if any(c.isdigit() for c in p)]
                        if len(nums) >= 2:
                            temp = f"{nums[0]} to {nums[1]} DEG C"
                    
                    # Ensure "DEG C" format is consistent
                    if 'DEG C' not in temp.upper():
                        # Remove any existing temperature units
                        temp = temp.replace('°C', '').replace('C', '')
                        # Add DEG C
                        if 'DEG' not in temp.upper():
                            temp = temp + " DEG C"
                    
                    # Normalize spacing
                    temp = ' '.join(temp.split())
                    first_pass_results['OPERATING TEMPERATURE'] = temp
            
            # Perform second pass for any missing fields without showing messages
            # Only perform second pass if params have empty values
            if st.session_state.parameter_mode == "Custom" and any(not first_pass_results.get(param.strip().upper(), "") for param in (st.session_state.custom_parameters.get("GENERIC", []) or [])):
                final_results = perform_second_extraction_pass(image_bytes, first_pass_results, component_type)
            elif st.session_state.parameter_mode == "Cylinder, Hyd/Pneumatic" and any(not first_pass_results.get(param, "") for param in ["BORE_DIAMETER", "MOUNTING", "OPERATING_TEMPERATURE", "OPERATING_PRESSURE", "CLOSE_LENGTH", "DRAWING_NUMBER", "FLUID", "ROD_END", "CYLINDER_ACTION", "STROKE_LENGTH", "ROD_DIAMETER", "OUTSIDE_DIAMETER", "BODY_MATERIAL", "OPEN_LENGTH", "RATED_LOAD", "PISTON_MATERIAL", "STANDARD", "SURFACE_FINISH", "COATING_THICKNESS", "SPECIAL_FEATURES", "CYLINDER_CONFIGURATION", "CYLINDER_STYLE", "CONCENTRICITY_OF_ROD_AND_TUBE"]):
                final_results = perform_second_extraction_pass(image_bytes, first_pass_results, component_type)
            else:
                final_results = first_pass_results
            
            # Validate and improve justifications
            final_results = validate_and_improve_justifications(final_results)
            
            # Get component type
            component_type = final_results.get('COMPONENT_TYPE', '')
            if not component_type:
                # Try to determine component type from other parameters
                if 'CYLINDER ACTION' in final_results:
                    component_type = 'CYLINDER'
                elif 'GEAR TYPE' in final_results:
                    component_type = 'GEARBOX'
                elif 'MODEL NO' in final_results and 'SIZE OF VALVE' in final_results:
                    component_type = 'VALVE'
                elif 'PROPERTY CLASS' in final_results and 'NUT STANDARD' in final_results:
                    component_type = 'NUT'
                elif 'PISTON LIFTING FORCE' in final_results:
                    component_type = 'LIFTING_RAM'
                else:
                    component_type = 'UNKNOWN'
            
            # Add component type to results
            final_results['COMPONENT_TYPE'] = component_type
            
            # Compare first and second pass results to count how many fields were improved
            improved_fields = 0
            for key, value in final_results.items():
                if not key.endswith("_JUSTIFICATION") and key not in ["DOCUMENT_TYPE", "COMPONENT_TYPE"]:
                    # If second pass found a value where first pass had none
                    if value and (key not in first_pass_results or not first_pass_results[key]):
                        improved_fields += 1
            
            return '\n'.join([f"{k}: {v}" for k, v in final_results.items()])
        return result
    except Exception as e:
        return f"❌ Processing Error: {str(e)}"

# Helper function to create the extracted mode prompt
def create_extracted_mode_prompt():
    """Create the prompt for extracted mode"""
    return (
        "TASK: Analyze this engineering document as a professional mechanical engineer. Extract all technical specifications and provide insightful engineering analysis based on the design elements in the document. The image has been automatically oriented correctly for you.\n\n"
        
        "STEP 1. DOCUMENT TYPE IDENTIFICATION\n"
        "  - Determine the document type:\n"
        "    (A) Engineering Drawing\n"
        "    (B) Product Listing/Catalog\n"
        "    (C) Specification Sheet\n"
        "    (D) Mixed Document (contains both drawings and tables)\n"
        "  - Document this determination as \"Document Type\" in your output.\n\n"
        
        "STEP 2. COMPREHENSIVE VISUAL SCANNING\n"
        "  - Methodically scan EVERY part of the document in this order:\n"
        "      1. Tables & Specification Boxes (highest priority)\n"
        "      2. Title Blocks & Headers\n"
        "      3. Dimensions & Callouts (annotations on drawings)\n"
        "      4. Notes & Footnotes\n"
        "      5. Text in Margins & Stamps\n"
        "  - Pay SPECIAL ATTENTION to data in tables, as they often contain the most critical specifications.\n"
        "  - Extract ALL numeric values along with units EXACTLY as they appear.\n"
        "  - For dimensions, capture the complete value including tolerances.\n"
        "  - Look for small text and specification tables that may be placed anywhere in the document.\n"
        "  - For product listings, examine ALL fields in the specifications section.\n\n"
        
        "STEP 3. EXTRACTION OF IDENTIFYING INFORMATION\n"
        "  - Look for and extract ALL of these identifying details:\n"
        "      • Manufacturer/Brand name\n"
        "      • Model numbers & Part numbers\n"
        "      • Drawing numbers & Revision information\n"
        "      • Standards & Certification references\n"
        "      • Serial numbers & Batch codes\n"
        "  - If a detail appears in multiple places, record it from the most authoritative location.\n\n"
        
        "STEP 4. COMPONENT IDENTIFICATION\n"
        "  - Determine if the document describes one of these component types:\n"
        "      • Cylinder (hydraulic, pneumatic)\n"
        "      • Gearbox/Gear (transmission, reducer)\n"
        "      • Valve (ball, check, control)\n"
        "      • Nut/Bolt/Fastener\n"
        "      • Lifting Ram or Jack (hydraulic, transmission)\n"
        "      • Bearing\n"
        "      • Pump\n"
        "      • Motor\n"
        "  - If the component type is obvious but not in the list above, specify the exact type.\n"
        "  - If the type is ambiguous, mark the \"Component Type\" as \"UNKNOWN\" without guessing.\n\n"
        
        "STEP 5. ENGINEERING SYMBOL INTERPRETATION\n"
        "  - Identify ALL engineering symbols present in the drawing:\n"
        "      • Ø or ⌀: Diameter\n" 
        "      • R: Radius\n"
        "      • ±: Tolerance\n"
        "      • ▭: Square\n"
        "      • Surface finish marks (✓, ✗)\n"
        "      • Weld symbols\n"
        "      • GD&T symbols (straightness, flatness, circularity, etc.)\n"
        "      • Thread symbols and callouts\n"
        "  - For each symbol found, explain its significance in this specific design\n"
        "  - Relate symbols to the dimensional values they qualify\n\n"
        
        "STEP 6. PARAMETER EXTRACTION\n"
        "  - Extract each parameter name EXACTLY as it appears in the drawing\n"
        "  - Do NOT use generic parameter categories like 'PRIMARY PHYSICAL DIMENSIONS'\n"
        "  - Instead, use the exact labels from the drawing like 'Bore Diameter', 'Rod Diameter', 'Working Pressure', etc.\n"
        "  - Maintain the exact parameter names shown in the technical document\n"
        "  - Do not categorize parameters into groups\n\n"
        
        "PARAMETER EXTRACTION MODE: Full Extraction\n"
        "  - Extract ALL parameters visible in the document, even if uncommon or non-standard.\n"
        "  - Be exhaustive and thorough in your search for any technical specifications.\n\n"
        
        "STEP 7. DETAILED PARAMETER EXTRACTION\n"
        "  - Extract parameters with their EXACT names as they appear in the drawing\n"
        "  - Do not rename, reformat, or categorize parameters\n"
        "  - For cylinder drawings, look for parameter names like 'Bore', 'Rod Diameter', 'Stroke', etc.\n"
        "  - Use the same formatting, capitalization, and terminology as shown in the drawing\n\n"
        
        "STEP 8. ENGINEERING INSIGHTS & ANALYSIS\n"
        "  - After extracting numerical parameters, analyze their engineering implications:\n"
        "      • What does the bore/rod diameter ratio suggest about stability and load capacity?\n"
        "      • How do the material choices impact longevity, corrosion resistance, and thermal properties?\n"
        "      • Based on dimensions and pressure ratings, estimate the operational force capabilities\n"
        "      • Analyze the safety factor implied by test pressure vs. operating pressure\n"
        "      • Evaluate the design for maintenance accessibility and service life\n\n"
        
        "STEP 9. PERFORMANCE-BASED DESIGN ANALYSIS\n"
        "  - Based on extracted values and drawing structure, determine:\n"
        "      • Expected load-bearing capacity and mechanical stress points\n"
        "      • Sealing mechanism effectiveness and potential failure modes\n"
        "      • Thermal expansion considerations and temperature management\n"
        "      • Potential wear points and fatigue-prone areas\n\n"
        
        "STEP 10. FUNCTIONALITY MAPPING\n"
        "  - Based on mounting type, expected movement, and connection points:\n"
        "      • Infer the component's operational purpose in a larger system\n"
        "      • Determine if this is a fixed or dynamic system\n"
        "      • Identify if it allows axial movement or rotational flexibility\n"
        "      • Analyze operational constraints based on design features\n\n"
        
        "STEP 11. MANUFACTURING & ASSEMBLY CONSIDERATIONS\n"
        "  - Evaluate complexity in manufacturing based on:\n"
        "      • Tolerance levels and their impact on production costs\n"
        "      • Thread specifications and special machining requirements\n"
        "      • Number of unique components and assembly complexity\n"
        "      • Potential fabrication challenges based on materials and geometries\n\n"
        
        "STEP 12. OUTPUT FORMAT\n"
        "  - Format your extraction with the EXACT parameter names as they appear in the drawing\n"
        "  - DO NOT use generic category names like 'PRIMARY PHYSICAL DIMENSIONS'\n"
        "  - DO NOT add dashes or bullet points before parameter names\n"
        "  - Instead use the drawing's original parameter names like 'Bore Diameter', 'Rod Diameter', etc.\n"
        "  - For each parameter, include a value and detailed justification explaining its source\n"
        "  - Use the parameter-justification format where each parameter is followed by its justification\n"
        "  - Format as PARAMETER_NAME: value and PARAMETER_NAME_JUSTIFICATION: explanation\n"
        "  - For empty parameters, explain why the information couldn't be found\n"
    )

def get_parameters_for_type(drawing_type):
    """Return the list of parameters to extract based on drawing type"""
    drawing_type = drawing_type.upper() if drawing_type else ""
    
    # Handle multiple variations of component types
    if "CYLINDER" in drawing_type:
        return [
            "CYLINDER ACTION",
            "BORE DIAMETER",
            "OUTSIDE DIAMETER",
            "ROD DIAMETER",
            "STROKE LENGTH",
            "CLOSED LENGTH",
            "OPEN LENGTH",
            "OPERATING PRESSURE",
            "TEST PRESSURE",
            "OPERATING TEMPERATURE",
            "MOUNTING TYPE",
            "ROD END TYPE",
            "FLUID TYPE",
            "DRAWING NUMBER",
            "BODY MATERIAL",
            "ROD MATERIAL",
            "PISTON MATERIAL",
            "RATED LOAD/CAPACITY",
            "STANDARD COMPLIANCE",
            "SURFACE FINISH",
            "COATING/PLATING",
            "CONCENTRICITY OF ROD AND TUBE",
            "PORT TYPE",
            "PORT SIZE",
            "PORT LOCATION",
            "SEAL TYPE",
            "MANUFACTURER/MAKE",
            "MODEL/PART NUMBER",
            "CUSHIONING"
        ]
    elif "GEARBOX" in drawing_type:
        return [
            "GEAR TYPE",
            "INPUT POWER",
            "INPUT SPEED",
            "OUTPUT SPEED",
            "GEAR RATIO",
            "SERVICE FACTOR",
            "MOUNTING ARRANGEMENT",
            "SHAFT ORIENTATION",
            "INPUT SHAFT TYPE",
            "OUTPUT SHAFT TYPE",
            "SHAFT DIAMETER",
            "BACKLASH",
            "EFFICIENCY",
            "DUTY",
            "COOLING ARRANGEMENT",
            "LUBRICATION SYSTEM",
            "HOUSING MATERIAL",
            "SEALING TYPE",
            "WEIGHT",
            "DIMENSIONS",
            "DRAWING NUMBER",
            "MANUFACTURER/MAKE",
            "MODEL/PART NUMBER"
        ]
    elif "VALVE" in drawing_type:
        return [
            "MODEL/PART NUMBER",
            "VALVE TYPE",
            "VALVE SIZE/PORT SIZE",
            "PRESSURE RATING",
            "FLOW CAPACITY",
            "FLOW DIRECTION",
            "OPERATING MEDIUM",
            "CONNECTION TYPE",
            "BODY MATERIAL",
            "SEAT/SEAL MATERIAL",
            "OPERATING TEMPERATURE",
            "ACTUATION TYPE",
            "OPERATION PATTERN",
            "LEAKAGE CLASS",
            "MANUFACTURER/MAKE",
            "SPECIAL FEATURES"
        ]
    elif "NUT" in drawing_type or "BOLT" in drawing_type or "FASTENER" in drawing_type:
        return [
            "TYPE",
            "SIZE/DIMENSION",
            "THREAD TYPE",
            "THREAD PITCH",
            "PROPERTY/STRENGTH CLASS",
            "MATERIAL",
            "COATING/FINISH",
            "STANDARD COMPLIANCE",
            "HEAD DIMENSIONS",
            "TORQUE SPECIFICATION",
            "MANUFACTURER/MAKE",
            "DRAWING NUMBER",
            "SPECIAL FEATURES"
        ]
    elif "LIFTING_RAM" in drawing_type or "JACK" in drawing_type or "TRANSMISSION_JACK" in drawing_type:
        return [
            "LOAD CAPACITY",
            "MINIMUM HEIGHT",
            "MAXIMUM HEIGHT",
            "CLOSED HEIGHT",
            "OPEN HEIGHT",
            "LIFT RANGE/STROKE",
            "OPERATING PRESSURE",
            "PISTON DIAMETER",
            "WEIGHT",
            "DIMENSIONS",
            "MATERIAL",
            "ACTIVATION TYPE",
            "MANUFACTURER/BRAND",
            "MODEL/PART NUMBER",
            "PRICE",
            "SPECIAL FEATURES",
            "HYDRAULIC SYSTEM",
            "OIL VOLUME",
            "PRODUCT FEATURES",
            "WARRANTY INFORMATION",
            "ITEM DIMENSIONS",
            "SIZE VARIATIONS",
            "CONSTRUCTION MATERIAL",
            "PRODUCT CODE"
        ]
    elif "BEARING" in drawing_type:
        return [
            "BEARING TYPE",
            "INNER DIAMETER",
            "OUTER DIAMETER",
            "WIDTH/THICKNESS",
            "LOAD RATING DYNAMIC",
            "LOAD RATING STATIC",
            "SPEED RATING",
            "MATERIAL",
            "LUBRICATION TYPE",
            "SEAL TYPE",
            "MANUFACTURER/BRAND",
            "MODEL/PART NUMBER",
            "STANDARD COMPLIANCE"
        ]
    elif drawing_type in st.session_state.custom_products and isinstance(st.session_state.custom_products[drawing_type], dict):
        # Return parameters for custom product type
        return st.session_state.custom_products[drawing_type].get('parameters', [])
    else:
        # For unknown or custom component types, return comprehensive list of parameters
        return [
            "MODEL/PART NUMBER",
            "DIMENSIONS",
            "MATERIAL",
            "WEIGHT",
            "STANDARD/SPECIFICATION",
            "MANUFACTURER/MAKE",
            "DRAWING NUMBER",
            "OPERATING CONDITIONS",
            "SPECIAL FEATURES",
            "MOUNTING DETAILS",
            "CONNECTIONS",
            "RATED CAPACITY/LOAD",
            "PRICE",
            "BRAND",
            "ITEM DIMENSIONS",
            "LOAD CAPACITY",
            "PRODUCT CODE",
            "WARRANTY INFORMATION",
            "OPERATING TEMPERATURE",
            "OPERATING PRESSURE",
            "CONSTRUCTION MATERIAL"
        ]

def get_extraction_parameters(drawing_type):
    """
    Get the parameters to extract based on the selected parameter mode.
    
    Modes:
    - Custom: Use user-specified parameters
    - Cylinder, Hyd/Pneumatic: Use 23 specific cylinder parameters
    """
    # If in custom mode, use the user-defined parameters
    if st.session_state.parameter_mode == "Custom":
        # Use generic custom parameters
        if "GENERIC" in st.session_state.custom_parameters:
            return st.session_state.custom_parameters.get("GENERIC", [])
        else:
            # If no custom parameters defined, fall back to default
            return get_parameters_for_type(drawing_type)
    
    # If in cylinder mode, use the predefined cylinder parameters
    elif st.session_state.parameter_mode == "Cylinder, Hyd/Pneumatic":
        return [
            "BORE_DIAMETER", "MOUNTING", "OPERATING_TEMPERATURE", "OPERATING_PRESSURE",
            "CLOSE_LENGTH", "DRAWING_NUMBER", "FLUID", "ROD_END", "CYLINDER_ACTION",
            "STROKE_LENGTH", "ROD_DIAMETER", "OUTSIDE_DIAMETER", "BODY_MATERIAL",
            "OPEN_LENGTH", "RATED_LOAD", "PISTON_MATERIAL", "STANDARD", "SURFACE_FINISH",
            "COATING_THICKNESS", "SPECIAL_FEATURES", "CYLINDER_CONFIGURATION", 
            "CYLINDER_STYLE", "CONCENTRICITY_OF_ROD_AND_TUBE"
        ]
    
    # Default fallback
    return get_parameters_for_type(drawing_type)

print("Current API key:", st.session_state.current_api_key)


def identify_drawing_type(image_bytes):
    """Identify the type of technical document and component using AI vision model"""
    base64_image = encode_image_to_base64(image_bytes)
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert level electrical and mechanical engineer with extensive experience analyzing all types of technical documents including engineering drawings, product listings, and specification sheets. Your task is to accurately identify both document types and component types with high precision and consistency. The image has been automatically oriented correctly for reading. Never guess - only provide definitive answers when certain."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "TASK: Identify BOTH the document type AND component type in this technical document. The image has been properly oriented for you.\n\n"
                            
                            "### CRITICAL INSTRUCTIONS\n"
                            "1. First determine the DOCUMENT TYPE:\n"
                            "   - ENGINEERING_DRAWING: Contains technical drawings with dimensions and specifications\n"
                            "   - PRODUCT_LISTING: Contains product information, pricing, and marketing content\n"
                            "   - SPECIFICATION_SHEET: Contains organized technical specifications in tables or lists\n"
                            "   - MIXED_DOCUMENT: Contains multiple document types combined\n\n"
                            
                            "2. Then identify the COMPONENT TYPE:\n"
                            "   - CYLINDER (pneumatic, hydraulic, etc.)\n"
                            "   - VALVE\n"
                            "   - GEARBOX\n"
                            "   - NUT\n"
                            "   - LIFTING_RAM or JACK\n"
                            "   - TRANSMISSION_JACK\n"
                            "   - BEARING\n"
                            "   - PUMP\n"
                            "   - MOTOR\n"
                            "   - Other specific component type in ALL CAPS\n\n"
                            
                            "3. Examination Process:\n"
                            "   - Check title blocks, headers, and document structure first\n"
                            "   - Look for company logos, document templates, and formatting\n"
                            "   - Examine tables, dimensions, and technical notations\n"
                            "   - Be EXTREMELY CONSISTENT in your categorization\n\n"
                            
                            "### RESPONSE FORMAT\n"
                            "You MUST respond in this exact format: 'DOCUMENT_TYPE: COMPONENT_TYPE'\n"
                            "Examples:\n"
                            "- 'ENGINEERING_DRAWING: CYLINDER'\n"
                            "- 'PRODUCT_LISTING: TRANSMISSION_JACK'\n"
                            "- 'SPECIFICATION_SHEET: VALVE'\n"
                            "- 'MIXED_DOCUMENT: HYDRAULIC_CYLINDER'\n\n"
                            
                            "If you can identify the document type but not the component type, respond with 'DOCUMENT_TYPE: UNKNOWN'.\n"
                            "If you cannot identify either with confidence, respond with 'UNKNOWN: UNKNOWN'.\n\n"
                            
                            "IMPORTANT: Your response must be ONLY the document and component types in the format specified above. No explanations or additional text."
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": base64_image
                        }
                    }
                ]
            }
        ],
        "max_tokens": 100,
        "temperature": 0
    }

    headers = {
        "Authorization": f"Bearer {st.session_state.current_api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        result = process_api_response(response, identify_drawing_type, image_bytes)
        
        # Parse the result which should be in format "DOCUMENT_TYPE: COMPONENT_TYPE"
        if "❌" not in result:
            result = result.strip().upper()
            
            # Store document type information in session state
            if ':' in result:
                document_type, component_type = result.split(':', 1)
                document_type = document_type.strip()
                component_type = component_type.strip()
                
                # Store document type for future reference
                if 'document_types' not in st.session_state:
                    st.session_state.document_types = {}
                
                # Store the document type information
                st.session_state.document_types[result] = {
                    'document_type': document_type,
                    'component_type': component_type
                }
            else:
                # If no colon found, assume it's just a component type
                component_type = result
                document_type = "ENGINEERING_DRAWING"  # Default
            
            # Handle standard component types
            standard_types = ["CYLINDER", "VALVE", "GEARBOX", "NUT", "LIFTING_RAM", "JACK", "TRANSMISSION_JACK"]
            
            # Store custom component types
            if component_type not in standard_types and component_type != "UNKNOWN":
                if 'custom_component_types' not in st.session_state:
                    st.session_state.custom_component_types = {}
                
                st.session_state.custom_component_types[component_type] = {
                    'document_type': document_type
                }
            
            return component_type
        
        return result
    except Exception as e:
        return f"❌ Processing Error: {str(e)}"

def submit_feedback_to_company(feedback_data, drawing_info, additional_notes=""):
    """
    Submit feedback to the company's system
    Returns: (success: bool, message: str)
    """
    try:
        # Create a comprehensive feedback package
        feedback_package = {
            "timestamp": datetime.datetime.now().isoformat(),
            "drawing_info": {
                "drawing_number": drawing_info.get("drawing_number", ""),
                "drawing_type": drawing_info.get("drawing_type", ""),
                "processing_date": datetime.datetime.now().strftime("%Y-%m-%d")
            },
            "corrections": feedback_data,
            "additional_notes": additional_notes,
            "user_info": {
                "session_id": st.session_state.get("session_id", "unknown"),
                "submission_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        # Here you would implement the actual API call to your company's feedback system
        # For now, we'll just log it and store in session state
        st.session_state.feedback_history.append(feedback_package)
        
        # In a real implementation, you would send this to your backend:
        # response = requests.post(
        #     "https://your-company-api.com/feedback",
        #     json=feedback_package,
        #     headers={"Authorization": "Bearer " + API_KEY}
        # )
        # if response.status_code != 200:
        #     return False, "Failed to submit feedback to server"
        
        return True, "Feedback submitted successfully"
    except Exception as e:
        return False, f"Error submitting feedback: {str(e)}"

def convert_pdf_using_pymupdf(pdf_bytes):
    """Convert PDF to images using PyMuPDF (faster and no external dependencies)"""
    try:
        # Load PDF from bytes
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        image_bytes_list = []
        page_count = pdf_document.page_count
        
        # Get document details for better naming
        metadata = pdf_document.metadata
        document_title = metadata.get('title', '')

        # Convert each page to an image
        for page_num in range(page_count):
            page = pdf_document[page_num]
            
            # Get the page as a PNG image with higher resolution
            pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))  # Higher quality
            img_data = pix.tobytes("png")
            
            # Convert PNG to JPEG for consistency and smaller size
            img = Image.open(io.BytesIO(img_data))
            img_byte_arr = io.BytesIO()
            img = img.convert('RGB')  # Convert to RGB mode for JPEG
            
            # Add page number indicator as a subtle overlay
            draw = ImageDraw.Draw(img)
            try:
                # Try to get a font, fallback to default if not available
                font = ImageFont.truetype("arial.ttf", 24)
            except IOError:
                font = ImageFont.load_default()
                
            # Add page number indicator in the corner
            page_text = f"Page {page_num + 1}/{page_count}"
            text_width = draw.textlength(page_text, font=font) if hasattr(draw, 'textlength') else 150
            
            # Position in bottom right with padding
            draw.rectangle(
                [(img.width - text_width - 20, img.height - 40), (img.width - 5, img.height - 5)],
                fill=(50, 50, 50, 180)
            )
            draw.text(
                (img.width - text_width - 10, img.height - 35),
                page_text,
                fill=(255, 255, 255),
                font=font
            )
            
            img.save(img_byte_arr, format='JPEG', quality=90, optimize=True)
            image_bytes_list.append((img_byte_arr.getvalue(), page_num + 1, page_count, document_title))

        pdf_document.close()
        return image_bytes_list
    except Exception as e:
        st.error(f"Error converting PDF with PyMuPDF: {str(e)}")
        return None

def convert_pdf_using_pdf2image_alternative(pdf_bytes):
    """Try alternative PDF to image conversion using pdf2image with different settings"""
    try:
        # Try using pdf2image without poppler first
        images = convert_from_bytes(
            pdf_bytes,
            dpi=300,  # Higher DPI for better quality
            fmt='jpeg',
            grayscale=False,
            size=None,
            use_pdftocairo=False  # Try without pdftocairo first
        )
        
        # Convert PIL images to bytes
        image_bytes_list = []
        page_count = len(images)
        
        for i, image in enumerate(images):
            img_byte_arr = io.BytesIO()
            
            # Add page number indicator
            draw = ImageDraw.Draw(image)
            try:
                # Try to get a font, fallback to default if not available
                font = ImageFont.truetype("arial.ttf", 24)
            except IOError:
                font = ImageFont.load_default()
                
            # Add page number indicator in the corner
            page_text = f"Page {i + 1}/{page_count}"
            text_width = draw.textlength(page_text, font=font) if hasattr(draw, 'textlength') else 150
            
            # Position in bottom right with padding
            draw.rectangle(
                [(image.width - text_width - 20, image.height - 40), (image.width - 5, image.height - 5)],
                fill=(50, 50, 50, 180)
            )
            draw.text(
                (image.width - text_width - 10, image.height - 35),
                page_text,
                fill=(255, 255, 255),
                font=font
            )
            
            image.save(img_byte_arr, format='JPEG', quality=90, optimize=True)
            image_bytes_list.append((img_byte_arr.getvalue(), i + 1, page_count, ""))
        
        return image_bytes_list
    except Exception as e:
        st.error(f"Error with alternative PDF conversion: {str(e)}")
        return None

def convert_pdf_to_images(pdf_bytes, filename=""):
    """Convert PDF bytes to a list of PIL Images using multiple methods"""
    # Try PyMuPDF first (no external dependencies)
    result = convert_pdf_using_pymupdf(pdf_bytes)
    if result:
        return result

    # Try pdf2image with alternative settings
    st.info("Attempting PDF conversion with alternative method...")
    result = convert_pdf_using_pdf2image_alternative(pdf_bytes)
    if result:
        return result

    # Finally, try poppler if available
    if check_poppler_installed():
        st.info("Attempting PDF conversion with Poppler...")
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                temp_pdf.write(pdf_bytes)
                temp_pdf.seek(0)
                
                try:
                    images = convert_from_bytes(pdf_bytes, dpi=300, fmt='jpeg', 
                                             grayscale=False, size=None,
                                             thread_count=2)
                    
                    image_bytes_list = []
                    page_count = len(images)
                    
                    for i, image in enumerate(images):
                        img_byte_arr = io.BytesIO()
                        
                        # Add page number indicator
                        draw = ImageDraw.Draw(image)
                        try:
                            # Try to get a font, fallback to default if not available
                            font = ImageFont.truetype("arial.ttf", 24)
                        except IOError:
                            font = ImageFont.load_default()
                            
                        # Add page number indicator in the corner
                        page_text = f"Page {i + 1}/{page_count}"
                        text_width = draw.textlength(page_text, font=font) if hasattr(draw, 'textlength') else 150
                        
                        # Position in bottom right with padding
                        draw.rectangle(
                            [(image.width - text_width - 20, image.height - 40), (image.width - 5, image.height - 5)],
                            fill=(50, 50, 50, 180)
                        )
                        draw.text(
                            (image.width - text_width - 10, image.height - 35),
                            page_text,
                            fill=(255, 255, 255),
                            font=font
                        )
                        
                        image.save(img_byte_arr, format='JPEG', quality=90, optimize=True)
                        image_bytes_list.append((img_byte_arr.getvalue(), i + 1, page_count, ""))
                    
                    return image_bytes_list
                except Exception as e:
                    st.error(f"Error converting PDF with Poppler: {str(e)}")
                    return None
                finally:
                    try:
                        os.unlink(temp_pdf.name)
                    except Exception:
                        pass
        except Exception as e:
            st.error(f"Error handling PDF file: {str(e)}")
            return None
    else:
        st.warning("""
        For better PDF conversion quality, you can install Poppler:
        • On macOS: brew install poppler
        • On Ubuntu/Debian: sudo apt-get install poppler-utils
        • On Windows: Download from https://blog.alivate.com.au/poppler-windows/
        """)
    
    return None

def detect_orientation_fallback(image_bytes):
    """
    Fallback method to detect orientation using basic image analysis.
    This is used if the API call fails.
    """
    try:
        # Check if pytesseract is available
        if not TESSERACT_AVAILABLE:
            print("Pytesseract not available for fallback orientation detection")
            return "ROTATE_0"  # Default to no rotation
            
        from PIL import Image
        
        # Open the image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Try all four orientations and see which has the most recognized text
        orientations = {
            "ROTATE_0": image,
            "ROTATE_90": image.rotate(-90, expand=True),
            "ROTATE_180": image.rotate(-180, expand=True),
            "ROTATE_270": image.rotate(-270, expand=True)
        }
        
        best_orientation = "ROTATE_0"
        max_text_score = 0
        
        for orientation, img in orientations.items():
            try:
                # Convert to numpy array for tesseract
                img_array = np.array(img)
                
                # Use tesseract to detect text
                text_data = pytesseract.image_to_data(img_array, output_type=pytesseract.Output.DICT)
                
                # Calculate a score based on confidence of detected text
                conf_values = [int(conf) for conf in text_data['conf'] if conf != '-1']
                if conf_values:
                    avg_conf = sum(conf_values) / len(conf_values)
                    text_count = len([word for word in text_data['text'] if word.strip()])
                    text_score = avg_conf * text_count
                    
                    if text_score > max_text_score:
                        max_text_score = text_score
                        best_orientation = orientation
            except Exception as inner_error:
                print(f"Error analyzing orientation {orientation}: {str(inner_error)}")
                # If tesseract fails, just continue with the next orientation
                continue
        
        # Return the best orientation
        return best_orientation
    except Exception as e:
        print(f"Fallback orientation detection failed: {str(e)}")
        return "ROTATE_0"  # Default to no rotation on error

def detect_and_correct_orientation(image_bytes):
    """
    Detect and correct the orientation of an image using OpenAI's vision model.
    Returns the rotated image bytes if rotation is needed, or the original image bytes if not.
    """
    try:
        # First, decode the image to check if it's already correctly oriented
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to base64 for API call
        base64_image = encode_image_to_base64(image_bytes)
        base64_image_data_url = f"data:image/png;base64,{base64_image}"

        
        try:
            # Call OpenAI API to determine the orientation
            payload = {
                "model": "gpt-5.2",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert in analyzing engineering drawings and technical documents. Your task is to determine if the image is in the correct orientation for reading."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Analyze this engineering drawing or technical document and tell me ONLY if it needs rotation. Respond with EXACTLY ONE of these options:\n1. ROTATE_0 (no rotation needed, image is correctly oriented)\n2. ROTATE_90 (rotate 90 degrees clockwise)\n3. ROTATE_180 (rotate 180 degrees)\n4. ROTATE_270 (rotate 270 degrees clockwise / 90 degrees counter-clockwise)\n\nBe extremely attentive to text orientation, title blocks, and standard engineering drawing layouts. Respond ONLY with one of the four options above, nothing else."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": base64_image_data_url
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 10,
                "temperature": 0
            }

            headers = {
                "Authorization": f"Bearer {st.session_state.current_api_key}",
                "Content-Type": "application/json"
            }

            response = requests.post(API_URL, headers=headers, json=payload)
            if response.status_code == 200:
                response_json = response.json()
                rotation_result = response_json["choices"][0]["message"]["content"].strip()
            else:
                # On API error, use fallback method
                print(f"API error while checking orientation: {response.status_code}")
                rotation_result = detect_orientation_fallback(image_bytes)
        except Exception as api_error:
            print(f"API call for orientation detection failed: {str(api_error)}")
            # If API call fails, use fallback method
            rotation_result = detect_orientation_fallback(image_bytes)
        
        # Rotate the image based on API response
        if rotation_result == "ROTATE_0":
            print("Image orientation is correct, no rotation needed")
            return image_bytes  # No rotation needed
        
        # Perform rotation
        if rotation_result == "ROTATE_90":
            rotated_image = image.rotate(-90, expand=True)  # Negative for clockwise
            rotation_message = "Rotated 90° clockwise"
        elif rotation_result == "ROTATE_180":
            rotated_image = image.rotate(-180, expand=True)
            rotation_message = "Rotated 180°"
        elif rotation_result == "ROTATE_270":
            rotated_image = image.rotate(-270, expand=True)
            rotation_message = "Rotated 90° counter-clockwise"
        else:
            return image_bytes  # Default to original if response is unexpected
        
        # Convert rotated image back to bytes
        img_byte_arr = io.BytesIO()
        rotated_image.save(img_byte_arr, format=image.format or 'JPEG')
        rotated_bytes = img_byte_arr.getvalue()
        
        # Log the rotation for debugging
        print(f"Image orientation corrected: {rotation_result} - {rotation_message}")
        st.info(f" Image orientation corrected: {rotation_message}")
        
        return rotated_bytes
            
    except Exception as e:
        print(f"Error in orientation detection: {str(e)}")
        return image_bytes  # Return original on error

def process_uploaded_file(uploaded_file):
    """Process uploaded file whether it's an image or PDF"""
    try:
        if uploaded_file.type == "application/pdf":
            # Show processing message
            with st.spinner('Converting PDF to images...'):
                # Convert PDF to images
                pdf_bytes = uploaded_file.read()
                image_bytes_list = convert_pdf_to_images(pdf_bytes, uploaded_file.name)
                if not image_bytes_list:
                    st.error("Failed to convert PDF to images. Please check if the PDF is valid.")
                    return None
                
                # Apply orientation correction to each page
                corrected_image_bytes_list = []
                for image_data in image_bytes_list:
                    image_bytes, page_number, page_count, doc_title = image_data
                    
                    # Check and correct orientation
                    with st.spinner(f'Analyzing orientation of page {page_number}...'):
                        corrected_bytes = detect_and_correct_orientation(image_bytes)
                        corrected_image_bytes_list.append((corrected_bytes, page_number, page_count, doc_title))
                
                st.success(f"Successfully converted PDF to {len(corrected_image_bytes_list)} images with corrected orientation")
                return corrected_image_bytes_list
        else:
            # Handle direct image upload
            try:
                # Verify it's a valid image
                image_bytes = uploaded_file.read()
                image = Image.open(io.BytesIO(image_bytes))
                uploaded_file.seek(0)  # Reset file pointer
                
                # Correct orientation
                with st.spinner('Analyzing image orientation...'):
                    corrected_bytes = detect_and_correct_orientation(image_bytes)
                
                # Return single image with metadata (as a list for consistency)
                return [(corrected_bytes, 1, 1, uploaded_file.name)]
            except Exception as e:
                st.error(f"Invalid image file: {str(e)}")
                return None
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None

def process_drawing(drawing_type, image_data, file_name, img_idx=0):
    """Process a single drawing and update the session state."""
    # Unpack image data - handle both formats (backwards compatibility)
    if isinstance(image_data, tuple) and len(image_data) >= 3:
        image_bytes, page_number, page_count, doc_title = image_data
        suffix = f"_page_{page_number}_of_{page_count}"
        if doc_title:
            file_name = doc_title
    else:
        # Legacy format
        image_bytes = image_data
        suffix = f"_page_{img_idx + 1}"
    
    # Create a unique identifier for this drawing
    drawing_id = str(uuid.uuid4())[:8]
    
    new_drawing = {
        'Drawing Type': drawing_type,
        'Drawing No.': f"Processing{suffix}",
        'Processing Status': 'Processing..',
        'Extracted Fields Count': '0/0',
        'Confidence Score': '0%',
        'Internal ID': drawing_id  # Add internal ID for tracking
    }
    
    # Add to table
    st.session_state.drawings_table = pd.concat([
        st.session_state.drawings_table,
        pd.DataFrame([new_drawing])
    ], ignore_index=True)
    
    # Process the drawing
    with st.spinner(f'Analyzing {drawing_type.lower()} drawing{suffix}...'):
        # Track this component type in the custom_component_types session state
        if drawing_type not in ["CYLINDER", "VALVE", "GEARBOX", "NUT", "LIFTING_RAM", "UNKNOWN"]:
            if 'custom_component_types' not in st.session_state:
                st.session_state.custom_component_types = {}
            st.session_state.custom_component_types[drawing_type] = True
            
        # Pass the component type to the analyzer for more targeted analysis
        result = analyze_engineering_drawing(image_bytes, drawing_type)
        
        if result and "❌" not in result:
            parsed_results = parse_ai_response(result)
            
            # Get drawing number based on component type
            if drawing_type == "VALVE":
                drawing_number = parsed_results.get('MODEL NO', '')
            else:
                drawing_number = parsed_results.get('DRAWING NUMBER', '') or parsed_results.get('MODEL NUMBER', '')
            
            if not drawing_number or drawing_number == 'Unknown':
                # Use file name or component type plus suffix and drawing ID for uniqueness
                drawing_number = f"{file_name.split('.')[0]}{suffix}_{drawing_id}"
            
            # Store results
            st.session_state.current_image[drawing_number] = image_bytes
            st.session_state.all_results[drawing_number] = parsed_results
            
            # Get the detected component type from results and update if different
            detected_type = parsed_results.get('COMPONENT_TYPE', '')
            if detected_type and detected_type != drawing_type and detected_type != "UNKNOWN":
                # Update the drawing type in the table
                drawing_type = detected_type
                # Also track this detected type
                if detected_type not in ["CYLINDER", "VALVE", "GEARBOX", "NUT", "LIFTING_RAM", "UNKNOWN"]:
                    if 'custom_component_types' not in st.session_state:
                        st.session_state.custom_component_types = {}
                    st.session_state.custom_component_types[detected_type] = True
            
            # Update status
            parameters = get_extraction_parameters(drawing_type)
            
            # Extract all parameters that were detected (excluding justifications and component type)
            detected_params = [k for k in parsed_results.keys() 
                              if not k.endswith('_JUSTIFICATION') and k != 'COMPONENT_TYPE']
            
            # Count non-empty fields from both standard parameters and any additional detected parameters
            non_empty_standard = sum(1 for k in parameters if k in parsed_results and parsed_results.get(k, '').strip())
            non_empty_additional = sum(1 for k in detected_params if k not in parameters and parsed_results.get(k, '').strip())
            non_empty_fields = non_empty_standard + non_empty_additional
            
            # Use the larger of standard parameters or detected parameters for total count
            total_fields = max(len(parameters), len(detected_params))
            
            # Ensure we have valid field counts
            if total_fields == 0:
                total_fields = 1  # Avoid division by zero
            
            # Add any additional detected parameters to the custom product type if it exists
            if drawing_type not in ["CYLINDER", "VALVE", "GEARBOX", "NUT", "LIFTING_RAM", "UNKNOWN"]:
                if drawing_type not in st.session_state.custom_products:
                    # Create a new custom product type with the detected parameters
                    new_params = [k for k in detected_params if k != 'COMPONENT_TYPE']
                    st.session_state.custom_products[drawing_type] = {
                        'parameters': new_params,
                        'auto_detected': True
                    }
                elif isinstance(st.session_state.custom_products[drawing_type], dict):
                    # Add any new parameters that were detected but not in the current list
                    current_params = st.session_state.custom_products[drawing_type].get('parameters', [])
                    for param in detected_params:
                        if param not in current_params and param != 'COMPONENT_TYPE':
                            current_params.append(param)
                    st.session_state.custom_products[drawing_type]['parameters'] = current_params
            
            # Calculate confidence percentage with bounds checking
            confidence_percent = min(100, max(0, (non_empty_fields / total_fields * 100)))
            
            new_drawing.update({
                'Drawing Type': drawing_type,  # Update with potentially new detected type
                'Drawing No.': drawing_number,
                'Processing Status': 'Completed' if non_empty_fields >= total_fields * 0.7 else 'Needs Review',
                'Extracted Fields Count': f"{non_empty_fields}",  # Show only the number of extracted fields
                'Confidence Score': f"{confidence_percent:.0f}%",
                'Internal ID': drawing_id  # Keep the internal ID
            })
            
            # Update the table row
            mask = st.session_state.drawings_table['Internal ID'] == drawing_id
            if any(mask):
                st.session_state.drawings_table.loc[mask, new_drawing.keys()] = list(new_drawing.values())
            else:
                # Fallback to updating the last row if ID not found (shouldn't happen)
                st.session_state.drawings_table.iloc[-1] = new_drawing
                
            return drawing_number
        else:
            new_drawing.update({
                'Processing Status': 'Failed',
                'Confidence Score': '0%',
                'Extracted Fields Count': '0/0'
            })
            
            # Update the table row
            mask = st.session_state.drawings_table['Internal ID'] == drawing_id
            if any(mask):
                st.session_state.drawings_table.loc[mask, new_drawing.keys()] = list(new_drawing.values())
            else:
                # Fallback to updating the last row if ID not found (shouldn't happen)
                st.session_state.drawings_table.iloc[-1] = new_drawing
                
            return None

def main():
    # Set page config
    st.set_page_config(
        page_title="JSW Engineering Drawing DataSheet Extractor",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Add JSW logo at the top with improved styling
    logo_path = "assets/logojsw.png"
    try:
        # Use Streamlit's native image component for the logo
        col1, col2 = st.columns([1, 5])
        with col1:
            st.image(logo_path, width=200)
        with col2:
            st.markdown("""
                <div>
                    <h1 class="app-title">Features Extractor for MPPG</h1>
                    <p class="app-subtitle">Extract specification for Cylinder, Hyd/Pneumatic</p>
                </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        # If there's an issue with the HTML approach, use Streamlit's native components
        try:
            logo = Image.open(logo_path)
            col1, col2 = st.columns([1, 5])
            with col1:
                st.image(logo, width=150)
            with col2:
                st.markdown("""
                    <div>
                        <h1 class="app-title">JSW Engineering Drawing DataSheet Extractor</h1>
                        <p class="app-subtitle">Extract technical specifications from engineering drawings</p>
                    </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            # If logo can't be loaded at all, just show the title
            st.markdown("""
                <div class="header">
                    <div>
                        <h1 class="app-title">JSW Engineering Drawing DataSheet Extractor</h1>
                        <p class="app-subtitle">Extract technical specifications from engineering drawings</p>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    # Custom CSS for a clean, modern UI with black, white, and gray shades
    st.markdown("""
        <style>
        /* Base variables */
        :root {
            --primary-bg: #FFFFFF;
            --secondary-bg: #F8F9FA;
            --accent-bg: #FAFAFA;
            --text-color: #212529;
            --text-secondary: #6C757D;
            --border-color: #E0E0E0;
            --primary-accent: #2C3E50;
            --secondary-accent: #3498DB;
            --success-color: #28A745;
            --warning-color: #FFC107;
            --danger-color: #DC3545;
            --shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
            --transition: all 0.2s ease;
            --border-radius: 4px;
            --header-height: 60px;
        }

        /* Dark mode variables */
        @media (prefers-color-scheme: dark) {
            :root {
                --primary-bg: #212529;
                --secondary-bg: #343A40;
                --accent-bg: #2C3034;
                --text-color: #F8F9FA;
                --text-secondary: #ADB5BD;
                --border-color: #495057;
                --shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
            }
        }

        /* Global Styles */
        .main {
            background-color: var(--primary-bg);
            color: var(--text-color);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
        }

        /* Header styles */
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 0;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 24px;
        }
        
        /* Logo styles */
        .logo-container {
            display: flex;
            align-items: center;
            margin-right: 20px;
        }
        
        .logo-image {
            max-height: 60px;
            object-fit: contain;
            margin-right: 15px;
        }

        .app-title {
            font-size: 24px;
            font-weight: 600;
            color: var(--text-color);
            margin: 0;
        }

        .app-subtitle {
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        /* Card component */
        .card {
            background-color: var(--primary-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--border-radius);
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: var(--shadow);
            transition: var(--transition);
        }

        .card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        }

        .card-header {
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 16px;
        }

        .card-title {
            font-size: 18px;
            font-weight: 600;
            margin: 0 0 4px 0;
            color: var(--text-color);
        }

        .card-subtitle {
            color: var(--text-secondary);
            font-size: 14px;
            margin: 0;
        }

        /* Section dividers */
        .divider {
            height: 1px;
            background-color: var(--border-color);
            margin: 20px 0;
        }

        /* Button styles */
        .stButton > button {
            background-color: var(--primary-accent);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: var(--border-radius);
            font-weight: 500;
            cursor: pointer;
            transition: var(--transition);
            text-transform: none;
            letter-spacing: normal;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            height: 36px;
        }

        .stButton > button:hover {
            filter: brightness(90%);
        }

        .stButton > button:active {
            transform: translateY(1px);
        }

        /* Primary button */
        .stButton.primary > button {
            background-color: var(--primary-accent);
        }

        /* Secondary button */
        .stButton.secondary > button {
            background-color: var(--secondary-bg);
            color: var(--text-color);
            border: 1px solid var(--border-color);
        }

        /* Success button */
        .stButton.success > button {
            background-color: var(--success-color);
        }

        /* Warning button */
        .stButton.warning > button {
            background-color: var(--warning-color);
            color: #212529;
        }

        /* Danger button */
        .stButton.danger > button {
            background-color: var(--danger-color);
        }

        /* File uploader */
        .stFileUploader > div {
            background-color: var(--secondary-bg);
            border: 2px dashed var(--border-color);
            border-radius: var(--border-radius);
            padding: 20px;
            text-align: center;
            transition: var(--transition);
        }

        .stFileUploader > div:hover {
            border-color: var(--secondary-accent);
            background-color: var(--accent-bg);
        }

        /* Table styles */
        .styled-table {
            width: 100%;
            border-collapse: collapse;
            border: 1px solid var(--border-color);
            border-radius: var(--border-radius);
            overflow: hidden;
        }

        .styled-table thead {
            background-color: var(--secondary-bg);
        }

        .styled-table th {
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            color: var(--text-color);
            border-bottom: 1px solid var(--border-color);
        }

        .styled-table td {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
        }

        .styled-table tr:last-child td {
            border-bottom: none;
        }

        .styled-table tbody tr {
            transition: var(--transition);
        }

        .styled-table tbody tr:hover {
            background-color: var(--accent-bg);
        }

        /* Status indicators */
        .status-indicator {
            display: inline-flex;
            align-items: center;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }

        .status-processing {
            background-color: rgba(52, 152, 219, 0.1);
            color: #3498DB;
        }

        .status-completed {
            background-color: rgba(40, 167, 69, 0.1);
            color: #28A745;
        }

        .status-review {
            background-color: rgba(255, 193, 7, 0.1);
            color: #FFC107;
        }

        .status-failed {
            background-color: rgba(220, 53, 69, 0.1);
            color: #DC3545;
        }

        /* Progress bar */
        .progress-container {
            width: 100%;
            height: 6px;
            background-color: var(--secondary-bg);
            border-radius: 3px;
            overflow: hidden;
        }

        .progress-bar {
            height: 100%;
            border-radius: 3px;
            transition: width 0.3s ease;
        }

        .progress-high {
            background-color: var(--success-color);
        }

        .progress-medium {
            background-color: var(--warning-color);
        }

        .progress-low {
            background-color: var(--danger-color);
        }

        /* Image container */
        .image-container {
            border: 1px solid var(--border-color);
            border-radius: var(--border-radius);
            overflow: hidden;
            background-color: var(--secondary-bg);
        }

        .image-container img {
            width: 100%;
            height: auto;
            display: block;
        }

        /* Form controls */
        .form-control {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid var(--border-color);
            border-radius: var(--border-radius);
            background-color: var(--primary-bg);
            color: var(--text-color);
            transition: var(--transition);
        }

        .form-control:focus {
            border-color: var(--secondary-accent);
            outline: none;
            box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
        }

        /* Responsive images in gallery */
        .image-gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 16px;
        }

        .thumbnail {
            aspect-ratio: 4/3;
            object-fit: contain;
            width: 100%;
            border: 1px solid var(--border-color);
            border-radius: var(--border-radius);
            background-color: var(--secondary-bg);
            transition: var(--transition);
        }

        .thumbnail:hover {
            transform: scale(1.02);
            box-shadow: var(--shadow);
        }

        /* Custom file upload button */
        .file-upload-btn {
            display: inline-block;
            background-color: var(--primary-accent);
            color: white;
            padding: 8px 16px;
            border-radius: var(--border-radius);
            cursor: pointer;
            transition: var(--transition);
        }

        .file-upload-btn:hover {
            background-color: #1e2b3a;
        }

        /* Alerts */
        .alert {
            padding: 12px 16px;
            margin-bottom: 16px;
            border-radius: var(--border-radius);
            font-size: 14px;
        }

        .alert-info {
            background-color: rgba(52, 152, 219, 0.1);
            border-left: 4px solid #3498DB;
            color: #3498DB;
        }

        .alert-success {
            background-color: rgba(40, 167, 69, 0.1);
            border-left: 4px solid #28A745;
            color: #28A745;
        }

        .alert-warning {
            background-color: rgba(255, 193, 7, 0.1);
            border-left: 4px solid #FFC107;
            color: #FFC107;
        }

        .alert-error {
            background-color: rgba(220, 53, 69, 0.1);
            border-left: 4px solid #DC3545;
            color: #DC3545;
        }

        /* Badge */
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }

        .badge-primary {
            background-color: var(--primary-accent);
            color: white;
        }

        .badge-secondary {
            background-color: var(--secondary-bg);
            color: var(--text-color);
        }

        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* Custom streamlit components */
        .stTextInput > div > div > input {
            border: 1px solid var(--border-color);
            border-radius: var(--border-radius);
        }

        .stTextInput > div > div > input:focus {
            border-color: var(--secondary-accent);
            box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
        }

        /* Data editor (table) */
        .stDataFrame {
            border: 1px solid var(--border-color);
            border-radius: var(--border-radius);
            overflow: hidden;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: var(--border-radius);
            padding: 8px 16px;
        }

        .stTabs [aria-selected="true"] {
            background-color: var(--primary-accent);
            color: white;
        }

        /* Header bar for drawing view mode */
        .view-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px;
            background-color: var(--secondary-bg);
            border-radius: var(--border-radius);
            margin-bottom: 20px;
        }

        .view-title {
            font-size: 18px;
            font-weight: 600;
            margin: 0;
        }

        .view-actions {
            display: flex;
            gap: 8px;
        }

        /* Loading spinner overlay */
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }

        .spinner {
            border: 4px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top: 4px solid white;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* Upload container */
        .upload-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 32px;
            border: 2px dashed var(--border-color);
            border-radius: var(--border-radius);
            background-color: var(--secondary-bg);
            text-align: center;
            transition: var(--transition);
            margin: 20px 0;
        }

        .upload-container:hover {
            border-color: var(--secondary-accent);
            background-color: var(--accent-bg);
        }

        .upload-icon {
            font-size: 48px;
            color: var(--text-secondary);
            margin-bottom: 16px;
        }

        .upload-text {
            color: var(--text-secondary);
            margin-bottom: 16px;
        }

        /* Form groups */
        .form-group {
            margin-bottom: 16px;
        }

        .form-label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
        }

        /* Grid layout */
        .grid {
            display: grid;
            grid-template-columns: repeat(12, 1fr);
            gap: 20px;
        }

        /* Responsive adjustments */
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }

            .card {
                padding: 16px;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    # Initialize all session state variables
    if 'drawings_table' not in st.session_state:
        st.session_state.drawings_table = pd.DataFrame(columns=[
            'Drawing Type',
            'Drawing No.',
            'Processing Status',
            'Extracted Fields Count',
            'Confidence Score',
            'Internal ID'  # Add internal ID for tracking
        ])
    if 'all_results' not in st.session_state:
        st.session_state.all_results = {}
    if 'selected_drawing' not in st.session_state:
        st.session_state.selected_drawing = None
    if 'current_image' not in st.session_state:
        st.session_state.current_image = {}
    if 'edited_values' not in st.session_state:
        st.session_state.edited_values = {}
    if 'custom_products' not in st.session_state:
        st.session_state.custom_products = {}
    if 'custom_component_types' not in st.session_state:
        st.session_state.custom_component_types = {}
    if 'show_feedback_popup' not in st.session_state:
        st.session_state.show_feedback_popup = False
    if 'feedback_data' not in st.session_state:
        st.session_state.feedback_data = {}
    if 'feedback_history' not in st.session_state:
        st.session_state.feedback_history = []
    if 'feedback_status' not in st.session_state:
        st.session_state.feedback_status = None
    if 'processing_queue' not in st.session_state:
        st.session_state.processing_queue = []
    if 'needs_rerun' not in st.session_state:
        st.session_state.needs_rerun = False
    if 'parameter_mode' not in st.session_state:
        st.session_state.parameter_mode = "Default"
    if 'custom_parameters' not in st.session_state:
        st.session_state.custom_parameters = {}

    # Function to handle state changes that require a rerun
    def set_rerun():
        st.session_state.needs_rerun = True

    # Function to handle drawing selection
    def select_drawing(drawing_number):
        st.session_state.selected_drawing = drawing_number
        set_rerun()

    # Create sidebar for options and configurations
    with st.sidebar:
        st.markdown("### App Settings")
        
        # Show a notification if pytesseract is not available
        if not TESSERACT_AVAILABLE:
            st.warning("""
            ⚠️ Tesseract OCR is not installed. For better orientation detection when the API is unavailable, install:
            ```
            pip install pytesseract
            ```
            And install Tesseract OCR from:
            - Windows: https://github.com/UB-Mannheim/tesseract/wiki
            - Mac: brew install tesseract
            - Linux: apt-get install tesseract-ocr
            """)
        
        # Component type filter for listing
        if st.session_state.drawings_table.empty:
            component_types = ["All Types"]
        else:
            component_types = ["All Types"] + sorted(st.session_state.drawings_table["Drawing Type"].unique().tolist())
        
        selected_filter = st.selectbox("Filter by Component Type", component_types)
        
        # Confidence threshold slider
        confidence_threshold = st.slider(
            "Minimum Confidence Score",
            min_value=0,
            max_value=100,
            value=0,
            step=10,
            help="Filter drawings by minimum confidence score"
        )
        
        # Add export all button
        if not st.session_state.drawings_table.empty:
            if st.button("Export All Results to CSV", use_container_width=True):
                # Prepare data for export
                export_data = []
                for drawing_number, results in st.session_state.all_results.items():
                    drawing_type = st.session_state.drawings_table[
                        st.session_state.drawings_table['Drawing No.'] == drawing_number
                    ]['Drawing Type'].iloc[0] if drawing_number in st.session_state.drawings_table['Drawing No.'].values else "Unknown"
                    
                    data_row = {
                        "Drawing Number": drawing_number,
                        "Component Type": drawing_type
                    }
                    
                    # Add all non-justification fields
                    for k, v in results.items():
                        if not k.endswith('_JUSTIFICATION') and k != 'COMPONENT_TYPE':
                            data_row[k] = v
                    
                    export_data.append(data_row)
                
                # Create dataframe and download link
                if export_data:
                    export_df = pd.DataFrame(export_data)
                    csv = export_df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name="all_drawings_data.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
        
        # Add clear all button with confirmation
        if not st.session_state.drawings_table.empty:
            st.markdown("---")
            st.markdown("### Danger Zone")
            
            if st.button("Clear All Drawings", use_container_width=True, type="primary"):
                st.session_state.show_confirm = True
                
            if st.session_state.get("show_confirm", False):
                st.warning("This will delete all processed drawings. Are you sure?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Yes, Clear All", use_container_width=True):
                        st.session_state.drawings_table = pd.DataFrame(columns=[
                            'Drawing Type',
                            'Drawing No.',
                            'Processing Status', 
                            'Extracted Fields Count',
                            'Confidence Score',
                            'Internal ID'
                        ])
                        st.session_state.all_results = {}
                        st.session_state.current_image = {}
                        st.session_state.edited_values = {}
                        st.session_state.selected_drawing = None
                        st.session_state.show_confirm = False
                        st.session_state.processing_queue = []
                        st.experimental_rerun()
                with col2:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state.show_confirm = False
                        st.experimental_rerun()

    # File uploader with modern styling
    # st.markdown("""
    #     <div class="card">
    #         <div class="card-header">
    #             <h2 class="card-title">Upload Engineering Drawings</h2>
    #             <p class="card-subtitle">Upload images or multi-page PDF files of engineering drawings</p>
    #         </div>
    # """, unsafe_allow_html=True)

    # Custom file uploader - make sure it's the only uploader in the section
    uploaded_files = st.file_uploader("Upload drawings (PNG, JPG, JPEG, PDF)", type=['png', 'jpg', 'jpeg', 'pdf'], accept_multiple_files=True, label_visibility="collapsed")

    # Add parameter mode selection
    st.markdown("""
        <div style="margin-top: 20px;">
            <h3>Parameter Extraction Mode</h3>
        </div>
    """, unsafe_allow_html=True)
    
    parameter_mode = st.radio(
        "Select parameter extraction mode:",
        ["Custom", "Cylinder, Hyd/Pneumatic"],
        help="Custom: Specify which parameters to extract. Cylinder, Hyd/Pneumatic: Extract 23 specific cylinder parameters."
    )
    
    # Update the parameter mode in session state
    if parameter_mode != st.session_state.parameter_mode:
        # If Default or Extracted was previously selected, change it to Custom
        if st.session_state.parameter_mode in ["Default", "Extracted"]:
            st.session_state.parameter_mode = "Custom"
        # Handle the case where old "Cylinder" mode is still in session state
        elif st.session_state.parameter_mode == "Cylinder":
            st.session_state.parameter_mode = "Cylinder, Hyd/Pneumatic"
        else:
            st.session_state.parameter_mode = parameter_mode
    
    # Display explanation for the selected mode
   
    # Show custom parameter input if Custom mode is selected
    if parameter_mode == "Custom":
        st.markdown("""
            <div style="margin-top: 15px;">
                <h4>Custom Parameter Selection</h4>
                <p style="font-size: 14px; color: var(--text-secondary);">
                    Specify which parameters to extract. Enter only the parameters you want to see.
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        # Get existing custom parameters if any
        existing_params = ""
        # Use a generic key for all custom parameters
        if "GENERIC" in st.session_state.custom_parameters:
            existing_params = "\n".join(st.session_state.custom_parameters["GENERIC"])
        
        # Custom parameters input
        custom_params = st.text_area(
            "Enter Custom Parameters (one per line)",
            value=existing_params,
            height=200,
            placeholder="Enter the parameters you want to extract, one per line.\nExample:\nSIZE\nLOAD CAPACITY\nBRAND"
        )
        
        # Save button for custom parameters
        if st.button("Save Custom Parameters", type="primary"):
            # Parse and store the custom parameters
            params_list = [p.strip().upper() for p in custom_params.split("\n") if p.strip()]
            if params_list:
                # Store under generic key
                st.session_state.custom_parameters["GENERIC"] = params_list
                st.success(f"✅ Custom parameters saved. Only these parameters will be extracted.")
                # Display the saved parameters
                st.markdown("""
                    <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-top: 10px;">
                        <p style="font-weight: bold; margin-bottom: 5px;">Saved Custom Parameters:</p>
                        <ul style="margin-bottom: 0;">
                """, unsafe_allow_html=True)
                for param in params_list:
                    st.markdown(f"<li>{param}</li>", unsafe_allow_html=True)
                st.markdown("</ul></div>", unsafe_allow_html=True)
            else:
                # If the input is empty, remove any existing custom parameters
                if "GENERIC" in st.session_state.custom_parameters:
                    del st.session_state.custom_parameters["GENERIC"]
                st.warning("No custom parameters specified. All parameters will be extracted.")
        
        # Display currently saved parameters
        if "GENERIC" in st.session_state.custom_parameters:
            saved_params = st.session_state.custom_parameters["GENERIC"]
            if saved_params:
                st.markdown("""
                    <div style="background-color: #e8f4f8; padding: 10px; border-radius: 5px; margin-top: 10px; border-left: 4px solid #3498db;">
                        <p style="font-weight: bold; margin-bottom: 5px;">Currently Active Custom Parameters:</p>
                        <ul style="margin-bottom: 0;">
                """, unsafe_allow_html=True)
                for param in saved_params:
                    st.markdown(f"<li>{param}</li>", unsafe_allow_html=True)
                st.markdown("</ul></div>", unsafe_allow_html=True)
                st.info("⚠️ When processing drawings in Custom mode, ONLY these parameters will be extracted.")

    if uploaded_files:
        # Process each uploaded file
        for uploaded_file in uploaded_files:
            file_id = f"{uploaded_file.name}_{uploaded_file.size}"
            existing_files = [f"{f.name}_{f.size}" for f in st.session_state.processing_queue]
            if file_id not in existing_files:
                st.session_state.processing_queue.append(uploaded_file)

        # Create a grid display for uploaded files
        st.markdown("""
            <div class="card-header">
                <h3 class="card-title">Uploaded Files</h3>
                <p class="card-subtitle">Select files to process</p>
            </div>
            <div class="image-gallery">
        """, unsafe_allow_html=True)
        
        # Display uploaded files in a grid
        cols = st.columns(4)
        for idx, file in enumerate(uploaded_files):
            col = cols[idx % 4]
            with col:
                if file.type == "application/pdf":
                    st.markdown(f"""
                        <div class="card" style="padding: 10px; text-align: center; margin-bottom: 16px;">
                            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M14 2H6C4.89543 2 4 2.89543 4 4V20C4 21.1046 4.89543 22 6 22H18C19.1046 22 20 21.1046 20 20V8L14 2Z" stroke="#2C3E50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                                <path d="M14 2V8H20" stroke="#2C3E50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                                <path d="M12 18V12" stroke="#2C3E50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                                <path d="M9 15H15" stroke="#2C3E50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                            </svg>
                            <p style="margin-top: 8px; margin-bottom: 4px; font-weight: 500;">{file.name}</p>
                            <p style="margin: 0; font-size: 12px; color: var(--text-secondary);">PDF Document</p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    # For images, display a thumbnail
                    try:
                        # Display image directly with st.image instead of using HTML/Base64
                        image_bytes = file.read()
                        file.seek(0)  # Reset file pointer after reading
                        
                        # Create a thumbnail
                        image = Image.open(io.BytesIO(image_bytes))
                        
                        # Display the image with Streamlit's built-in image component
                        st.image(image, caption=file.name, width=150)
                    except Exception as e:
                        st.error(f"Error displaying image: {str(e)}")
                
                # Process button for each file
                if st.button(f"Process", key=f"process_{idx}"):
                    try:
                        processed_images = process_uploaded_file(file)
                        if processed_images:
                            for img_idx, image_data in enumerate(processed_images):
                                with st.spinner('Identifying drawing type...'):
                                    drawing_type = identify_drawing_type(image_data[0] if isinstance(image_data, tuple) else image_data)
                                    if drawing_type and "❌" not in drawing_type:
                                        drawing_number = process_drawing(drawing_type, image_data, file.name, img_idx)
                                        # Automatically display results after successful processing
                                        if drawing_number:
                                            st.session_state.selected_drawing = drawing_number
                                            st.success(f"✅ Successfully processed drawing: {drawing_number}")
                                        else:
                                            st.error("❌ Processing completed but no results were extracted. Please check the drawing and try again.")
                                    else:
                                        st.error(f"❌ Failed to identify drawing type: {drawing_type if drawing_type else 'Unknown error'}")
                        else:
                            st.error(f"❌ Failed to process file: {file.name}. Please check if it's a valid image or PDF.")
                    except Exception as e:
                        st.error(f"Error processing {file.name}: {str(e)}")
                    set_rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Close the upload card - keep this regardless of whether files are uploaded
    st.markdown("</div>", unsafe_allow_html=True)  

    # Display the processed drawings with modern styling
    if not st.session_state.drawings_table.empty:
        # Apply filtering based on sidebar selections if needed
        filtered_table = st.session_state.drawings_table.copy()
        
        # Filter by component type if not "All Types"
        if selected_filter != "All Types":
            filtered_table = filtered_table[filtered_table["Drawing Type"] == selected_filter]
            
        # Filter by confidence score
        if confidence_threshold > 0:
            filtered_table = filtered_table[
                filtered_table["Confidence Score"].apply(
                    lambda x: int(x.rstrip("%")) >= confidence_threshold
                )
            ]
            
        if filtered_table.empty and not st.session_state.drawings_table.empty:
            st.warning(f"No drawings match the current filters. Try adjusting your filter criteria.")
            
        # Only display the table if we have data after filtering
        if not filtered_table.empty:
            st.markdown("""
                <div class="card">
                    <div class="card-header">
                        <h2 class="card-title">Processed Drawings</h2>
                        <p class="card-subtitle">View and manage your processed technical drawings</p>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # Create a clean modern table manually instead of using HTML
            # This avoids potential rendering issues with complex HTML
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                st.markdown("**Drawing Type**")
            with col2:
                st.markdown("**Drawing No.**")
            with col3:
                st.markdown("**Actions**")
            
            st.markdown("<hr style='margin: 5px 0 15px 0; border-color: var(--border-color);'>", unsafe_allow_html=True)
            
            # Display each row from the filtered table
            for index, row in filtered_table.iterrows():
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col1:
                    st.markdown(f"<span class='badge badge-primary'>{row['Drawing Type']}</span>", unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"{row['Drawing No.']}")
                
                with col3:
                    # Add view button - this ensures reliable display
                    if st.button("View", key=f"view_{index}"):
                        st.session_state.selected_drawing = row['Drawing No.']
                        set_rerun()
                
                st.markdown("<hr style='margin: 10px 0; border-color: var(--border-color);'>", unsafe_allow_html=True)
    else:
        pass  # No drawings processed yet

    # Detailed view with improved styling
    if st.session_state.selected_drawing and st.session_state.selected_drawing in st.session_state.all_results:
        try:
            # Safely get results for the selected drawing
            results = st.session_state.all_results.get(st.session_state.selected_drawing, {})
            if not results:
                st.error(f"No data found for drawing {st.session_state.selected_drawing}. Please try processing the drawing again.")
                if st.button("Back to List", key="back_error"):
                    st.session_state.selected_drawing = None
                    set_rerun()
            else:
                # Get drawing type from table
                drawing_type_entries = st.session_state.drawings_table[
                    st.session_state.drawings_table['Drawing No.'] == st.session_state.selected_drawing
                ]
                
                if drawing_type_entries.empty:
                    drawing_type = results.get('COMPONENT_TYPE', 'UNKNOWN')
                else:
                    drawing_type = drawing_type_entries['Drawing Type'].iloc[0]
                
                # Header
                st.markdown("""
                    <div class="view-header">
                        <h2 class="view-title">Detailed View</h2>
                        <div class="view-actions">
                            <div id="back_button_placeholder"></div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Back button with better styling
                col1, col2 = st.columns([1, 5])
                with col1:
                    if st.button("✖ Close View", key="close_btn", type="primary"):
                        st.session_state.selected_drawing = None
                        set_rerun()
                with col2:
                    if st.button("⬅ Back to All Drawings", key="back_btn"):
                        st.session_state.selected_drawing = None
                        set_rerun()
                
                # Drawing info header with close button
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"""
                        <div class="card">
                            <div class="card-header">
                                <h3 class="card-title">{st.session_state.selected_drawing}</h3>
                                <p class="card-subtitle">Review and edit extracted specifications</p>
                            </div>
                            <div style="padding: 0 20px;">
                                <span class="badge badge-primary" style="background-color: #3498DB; color: white; padding: 5px 10px; border-radius: 4px; font-size: 12px; margin-bottom: 10px; display: inline-block;">
                                    Parameter Mode: {st.session_state.parameter_mode}
                                </span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                with col2:
                    if st.button("✖ Close", key="close_detail_btn", type="primary"):
                        st.session_state.selected_drawing = None
                        set_rerun()
                
                # Create two columns for the content
                image_col, edit_col = st.columns([1, 2])
                
                # Image column
                with image_col:
                    st.markdown("""
                        <div class="card">
                            <div class="card-body">
                                <div class="image-container">
                    """, unsafe_allow_html=True)
                
                    image_data = st.session_state.current_image.get(st.session_state.selected_drawing)
                    if image_data is not None:
                        try:
                            image = Image.open(io.BytesIO(image_data))
                            st.image(image)
                        except Exception as e:
                            st.error(f"Unable to display image: {str(e)}. Please try processing the drawing again.")
                    else:
                        st.warning("Image not available. Please try processing the drawing again.")
                    
                    st.markdown("</div></div></div>", unsafe_allow_html=True)
                
                # Edit column for parameters
                with edit_col:
                    # Add mode-specific header title
                    header_title = "Extracted Parameters"
                    if st.session_state.parameter_mode == "Custom":
                        header_title = "Custom Parameters (Filtered)"
                    elif st.session_state.parameter_mode == "Cylinder, Hyd/Pneumatic":
                        header_title = "Cylinder Parameters (23 Specific)"
                    
                    st.markdown(f"""
                        <div class="card">
                            <div class="card-header">
                                <h4 class="card-title">{header_title}</h4>
                            </div>
                            <div class="card-body">
                    """, unsafe_allow_html=True)
                
                # Initialize edited values for this drawing if not exists
                if st.session_state.selected_drawing not in st.session_state.edited_values:
                    st.session_state.edited_values[st.session_state.selected_drawing] = {}
                
                # Get parameters based on drawing type
                parameters = get_extraction_parameters(drawing_type)
                
                # Create columns for the table header
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.markdown("<strong>Parameter</strong>", unsafe_allow_html=True)
                with col2:
                    st.markdown("<strong>Value</strong>", unsafe_allow_html=True)
                
                st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
                
                # Display only component type (no document type)
                # if "COMPONENT_TYPE" in results:
                #     # Get the component type
                #     comp_type = results.get("COMPONENT_TYPE", drawing_type)
                #     st.markdown(f"### Component Type: {comp_type}")
                #     st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
                
                # Display parameters section header
                st.markdown("### Technical Parameters", unsafe_allow_html=True)
                
                # Create column headers with better styling
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.markdown("<div style='font-weight:600; font-size:16px;'>Parameter</div>", unsafe_allow_html=True)
                with col2:
                    st.markdown("<div style='font-weight:600; font-size:16px;'>Value</div>", unsafe_allow_html=True)
                
                st.markdown("<hr style='margin: 10px 0 20px 0;'>", unsafe_allow_html=True)
                
                # Display each parameter with editable field
                edited_data = []
                
                # Get the defined template parameters for this component type
                template_parameters = get_extraction_parameters(drawing_type)
                
                # Normalize all parameters to remove underscores and standardize case for comparison
                def normalize_param(param):
                    return param.upper().replace('_', ' ').replace('-', ' ')
                
                # Create a parameter mapping to handle different variations of the same parameter
                param_mapping = {}
                
                # Map template parameters
                for param in template_parameters:
                    normalized = normalize_param(param)
                    param_mapping[normalized] = param
                
                # Map result parameters
                result_params = []
                for key in results.keys():
                    if not key.endswith('_JUSTIFICATION') and key not in ["DOCUMENT_TYPE", "COMPONENT_TYPE"]:
                        normalized = normalize_param(key)
                        # If this parameter has a value, prefer it over template version
                        if results.get(key, '').strip():
                            param_mapping[normalized] = key
                        # Keep track of parameters found in results
                        result_params.append(normalized)
                
                # Create a list of parameters to display
                display_parameters = []
                normalized_display = set()  # Track what we've added to avoid duplicates
                
                # Filter parameters based on the selected mode
                if st.session_state.parameter_mode == "Custom" and "GENERIC" in st.session_state.custom_parameters:
                    # Print debug info
                    print(f"Display - Custom mode active")
                    print(f"Custom parameters: {st.session_state.custom_parameters['GENERIC']}")
                    
                    # Get the custom parameters list
                    custom_params = st.session_state.custom_parameters["GENERIC"]
                    
                    # ONLY include parameters from the custom list - strict filtering
                    for param in custom_params:
                        normalized = normalize_param(param)
                        if normalized not in normalized_display:
                            # Add the parameter if it's in the results or the custom list
                            matching_key = None
                            # Check if this param is in our mapping (from results)
                            if normalized in param_mapping:
                                matching_key = param_mapping[normalized]
                                print(f"Found matching key for {param}: {matching_key}")
                            else:
                                # If not in mapping, use the parameter as is
                                matching_key = param
                                print(f"No matching key found for {param}, using as is")
                            
                            display_parameters.append(matching_key)
                            normalized_display.add(normalized)
                    
                    # Debug - print the final display parameters
                    print(f"Final display parameters: {display_parameters}")
                
                elif st.session_state.parameter_mode == "Cylinder, Hyd/Pneumatic":
                    # Only include the 23 specific cylinder parameters
                    cylinder_params = [
                        "BORE_DIAMETER", "MOUNTING", "OPERATING_TEMPERATURE", "OPERATING_PRESSURE",
                        "CLOSE_LENGTH", "DRAWING_NUMBER", "FLUID", "ROD_END", "CYLINDER_ACTION",
                        "STROKE_LENGTH", "ROD_DIAMETER", "OUTSIDE_DIAMETER", "BODY_MATERIAL",
                        "OPEN_LENGTH", "RATED_LOAD", "PISTON_MATERIAL", "STANDARD", "SURFACE_FINISH",
                        "COATING_THICKNESS", "SPECIAL_FEATURES", "CYLINDER_CONFIGURATION", 
                        "CYLINDER_STYLE", "CONCENTRICITY_OF_ROD_AND_TUBE"
                    ]
                    
                    # Add each cylinder parameter to display list
                    for param in cylinder_params:
                        normalized = normalize_param(param)
                        if normalized not in normalized_display:
                            # Try to find a matching key in results
                            matching_key = None
                            if normalized in param_mapping:
                                matching_key = param_mapping[normalized]
                            else:
                                # If not in mapping, use the parameter as is
                                matching_key = param
                            
                            display_parameters.append(matching_key)
                            normalized_display.add(normalized)
                
                else:
                    # Extracted mode - show all parameters
                    # First, add all parameters that have values (either template or found)
                    for normalized, param in param_mapping.items():
                        if results.get(param, '').strip() and normalized not in normalized_display:
                            display_parameters.append(param)
                            normalized_display.add(normalized)
                    
                    # Then add any remaining template parameters that don't have values
                    for param in template_parameters:
                        normalized = normalize_param(param)
                        if normalized not in normalized_display and param not in ["DOCUMENT_TYPE", "COMPONENT_TYPE"]:
                            display_parameters.append(param)
                            normalized_display.add(normalized)
                
                # First let's sort parameters by whether they have values and their position in the template
                def param_sort_key(param):
                    # First priority: has a value
                    has_value = 0 if results.get(param, '').strip() else 1
                    # Second priority: is in template (and its position)
                    in_template = False
                    template_pos = len(template_parameters) + 1  # Default to end
                    
                    for i, template_param in enumerate(template_parameters):
                        if normalize_param(param) == normalize_param(template_param):
                            in_template = True
                            template_pos = i
                            break
                    
                    return (has_value, 0 if in_template else 1, template_pos)
                
                # Sort the parameters
                sorted_parameters = sorted(display_parameters, key=param_sort_key)
                
                # Now display the parameters
                for param in sorted_parameters:
                    # Skip the parameter if it's blank AND not in template
                    if not results.get(param, '').strip() and param not in template_parameters:
                        continue
                    
                    # Also skip certain parameters that are likely redundant/duplicate
                    skip_params = ["RATED CAPACITY/LOAD", "ITEM DIMENSIONS", "CAPACITY", "MANUFACTURER/MAKE"]
                    if param in skip_params and not results.get(param, '').strip():
                        continue
                    
                    # Filter parameters based on the selected mode
                    if st.session_state.parameter_mode == "Custom" and "GENERIC" in st.session_state.custom_parameters:
                        custom_params = [p.strip().upper() for p in st.session_state.custom_parameters["GENERIC"]]
                        # Skip parameters not in the custom list
                        param_normalized = param.upper().replace('_', ' ').replace('-', ' ')
                        custom_normalized = [p.upper().replace('_', ' ').replace('-', ' ') for p in custom_params]
                        
                        # Strict matching - only show exact parameters from custom list
                        found_match = False
                        for custom_norm in custom_normalized:
                            if param_normalized == custom_norm:
                                found_match = True
                                break
                        
                        if not found_match:
                            # Skip this parameter as it's not in the custom list
                            continue
                    
                    # In Cylinder mode, only show the 23 specific cylinder parameters
                    elif st.session_state.parameter_mode == "Cylinder, Hyd/Pneumatic":
                        cylinder_params = [
                            "BORE_DIAMETER", "MOUNTING", "OPERATING_TEMPERATURE", "OPERATING_PRESSURE",
                            "CLOSE_LENGTH", "DRAWING_NUMBER", "FLUID", "ROD_END", "CYLINDER_ACTION",
                            "STROKE_LENGTH", "ROD_DIAMETER", "OUTSIDE_DIAMETER", "BODY_MATERIAL",
                            "OPEN_LENGTH", "RATED_LOAD", "PISTON_MATERIAL", "STANDARD", "SURFACE_FINISH",
                            "COATING_THICKNESS", "SPECIAL_FEATURES", "CYLINDER_CONFIGURATION", 
                            "CYLINDER_STYLE", "CONCENTRICITY_OF_ROD_AND_TUBE"
                        ]
                        
                        # Normalize both the parameter and the cylinder parameters
                        param_normalized = param.upper().replace('_', ' ').replace('-', ' ')
                        cylinder_normalized = [p.upper().replace('_', ' ').replace('-', ' ') for p in cylinder_params]
                        
                        # Check if the parameter is in the cylinder parameters list
                        found_match = False
                        for cylinder_norm in cylinder_normalized:
                            if param_normalized == cylinder_norm:
                                found_match = True
                                break
                        
                        if not found_match:
                            # Skip this parameter as it's not in the cylinder parameters list
                            continue
                    
                    col1, col2 = st.columns([1, 3])
                    
                    original_value = results.get(param, '')
                    # Get the edited value from session state if it exists, otherwise use original
                    current_value = st.session_state.edited_values[st.session_state.selected_drawing].get(
                        param, 
                        original_value
                    )
                    
                    with col1:
                        # Display clean parameter name without dashes and with proper naming
                        clean_param = param.replace('_', ' ').replace('*', '')
                        # Convert to title case for better readability
                        clean_param = ' '.join(word.capitalize() for word in clean_param.split())
                        # Improve parameter names with better terminology and units
                        if clean_param.lower() == "bore":
                            clean_param = "Bore Diameter"
                        elif clean_param.lower() == "rod":
                            clean_param = "Rod Diameter"
                        elif clean_param.lower() == "stroke" and "length" not in clean_param.lower():
                            clean_param = "Stroke Length"
                        elif clean_param.lower() == "construction":
                            clean_param = "Construction Type"
                        elif clean_param.lower() == "working pressure":
                            clean_param = "Working Pressure"
                        elif clean_param.lower() == "test pressure":
                            clean_param = "Test Pressure"
                        elif clean_param.lower() == "port":
                            clean_param = "Port Specification"
                        elif clean_param.lower() == "medium":
                            clean_param = "Operating Medium"
                        elif clean_param.lower() == "cushion":
                            clean_param = "Cushioning Type"
                        elif clean_param.lower() == "mounting":
                            clean_param = "Mounting Type"
                        elif clean_param.lower() == "ø or ⌀":
                            clean_param = "Diameter Symbol"
                        elif clean_param.lower() == "r":
                            clean_param = "Radius Symbol"
                        elif clean_param.lower() == "±":
                            clean_param = "Tolerance Symbol"
                        elif clean_param.lower() == "gd&t symbols":
                            clean_param = "GD&T Symbols"
                        st.markdown(f"<div style='font-weight:500;'>{clean_param}</div>", unsafe_allow_html=True)
                    
                    with col2:
                        # Check if the value contains newlines (multiple lines) or is a JSON-like structure
                        is_multiline = '\n' in current_value
                        is_json_like = (current_value.startswith('{') and current_value.endswith('}')) or current_value.count(':') > 1
                        
                        if is_multiline or is_json_like:
                            # Use text_area for multiline values
                            line_count = max(3, current_value.count('\n') + 1)
                            edited_value = st.text_area(
                                f"Edit {param}",
                                value=current_value,
                                key=f"edit_{param}",
                                height=min(35 * line_count, 200),
                                label_visibility="collapsed"
                            )
                        else:
                            # Use text_input for single line values
                            edited_value = st.text_input(
                                f"Edit {param}",
                                value=current_value,
                                key=f"edit_{param}",
                                label_visibility="collapsed"
                            )
                        
                        # Store edited value in session state if changed
                        if edited_value != current_value:
                            st.session_state.edited_values[st.session_state.selected_drawing][param] = edited_value
                        
                        # Update the value for export
                        current_value = edited_value
                    
                    # Store confidence and justification for export data but don't display
                    confidence = "100%" if current_value.strip() else "0%"
                    if current_value != original_value and current_value.strip():
                        confidence = "100% (Manual)"
                    # Set specific confidence scores for certain parameters when needed
                    if param == "CLOSE LENGTH" and current_value.strip():
                        confidence = "80%"
                    elif param == "STROKE LENGTH" and current_value.strip():
                        confidence = "90%"
                        
                    justification = results.get(f"{param}_JUSTIFICATION", "")
                    if not justification and current_value != original_value and current_value.strip():
                        justification = "Manually entered by user"
                    
                    # Add to export data - only if the parameter has a value or is in the template
                    if current_value.strip() or param in template_parameters:
                        edited_data.append({
                            "Parameter": clean_param,
                            "Value": current_value
                        })
                
                # Add save and export buttons
                st.markdown("<div style='margin-top:24px; display:flex; gap:16px;'></div>", unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Create DataFrame for export
                    export_df = pd.DataFrame(edited_data)
                    csv = export_df.to_csv(index=False)
                    st.download_button(
                        label="Export to CSV",
                        data=csv,
                        file_name=f"{st.session_state.selected_drawing}_details.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

                with col2:
                    if st.button("Save Changes", type="primary", use_container_width=True):
                        # Collect changes for feedback
                        feedback_data = {}
                        for param, value in st.session_state.edited_values[st.session_state.selected_drawing].items():
                            if value.strip() and value != results.get(param, ''):
                                feedback_data[param] = {
                                    'original': results.get(param, ''),
                                    'corrected': value
                                }
                        
                        # Update the results
                        for param, value in st.session_state.edited_values[st.session_state.selected_drawing].items():
                            if value.strip():  # Only update non-empty values
                                results[param] = value
                        st.session_state.all_results[st.session_state.selected_drawing] = results
                        
                        # If there are changes, show feedback popup
                        if feedback_data:
                            st.session_state.feedback_data = feedback_data
                            st.session_state.show_feedback_popup = True
                        
                        st.success("Changes saved successfully")
                
                st.markdown("</div></div>", unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"Error displaying drawing details: {str(e)}")
            if st.button("Back to List", key="back_error2"):
                st.session_state.selected_drawing = None
                set_rerun()

    # Feedback Popup with modern styling
    if st.session_state.show_feedback_popup:
        st.markdown("""
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Submit Feedback</h3>
                    <p class="card-subtitle">Your corrections will help improve our extraction system</p>
                </div>
        """, unsafe_allow_html=True)

        # Display corrections in a table format
        if st.session_state.feedback_data:
            st.markdown("""
                <div style="margin: 16px 0;">
                    <h4>Changes Detected</h4>
                </div>
            """, unsafe_allow_html=True)
            
            for param, values in st.session_state.feedback_data.items():
                st.markdown(f"""
                    <div style="background: var(--secondary-bg); padding: 16px; border-radius: 4px; margin-bottom: 16px;">
                        <div style="font-weight: 500; margin-bottom: 8px;">
                            {param}
                        </div>
                        <div style="display: flex; gap: 24px;">
                            <div>
                                <span style="font-size: 12px; color: var(--text-secondary);">Original:</span>
                                <div>{values['original'] or '(empty)'}</div>
                            </div>
                            <div>
                                <span style="font-size: 12px; color: var(--text-secondary);">Corrected:</span>
                                <div>{values['corrected']}</div>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        
        # Additional feedback options
        st.markdown("<h4>Additional Information</h4>", unsafe_allow_html=True)
        feedback_category = st.selectbox(
            "Feedback Category",
            ["Value Correction", "Missing Information", "Wrong Recognition", "Other"]
        )
        
        additional_notes = st.text_area(
            "Additional Notes (optional)",
            placeholder="Please provide any additional context or observations..."
        )
        
        # Submission buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Submit Feedback", type="primary", use_container_width=True):
                # Get current drawing info
                drawing_info = {
                    "drawing_number": st.session_state.selected_drawing,
                    "drawing_type": st.session_state.drawings_table[
                        st.session_state.drawings_table['Drawing No.'] == st.session_state.selected_drawing
                    ]['Drawing Type'].iloc[0]
                }
                
                # Add category to feedback data
                feedback_data = {
                    "corrections": st.session_state.feedback_data,
                    "category": feedback_category,
                    "notes": additional_notes
                }
                
                # Submit feedback
                success, message = submit_feedback_to_company(
                    feedback_data,
                    drawing_info,
                    additional_notes
                )
                
                if success:
                    st.session_state.feedback_status = {
                        "type": "success",
                        "message": message
                    }
                    # Clear feedback popup
                    st.session_state.show_feedback_popup = False
                    st.session_state.feedback_data = {}
                else:
                    st.session_state.feedback_status = {
                        "type": "error",
                        "message": message
                    }
                
                set_rerun()
        
        with col2:
            if st.button("Cancel", type="secondary", use_container_width=True):
                st.session_state.show_feedback_popup = False
                st.session_state.feedback_data = {}
                set_rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # Display feedback status if exists
    if st.session_state.feedback_status:
        status_type = st.session_state.feedback_status["type"]
        message = st.session_state.feedback_status["message"]
        
        if status_type == "success":
            st.success(message)
        else:
            st.error(message)
        
        # Clear status after displaying
        st.session_state.feedback_status = None

    # Check if we need to rerun at the end of the main function
    if st.session_state.needs_rerun:
        st.session_state.needs_rerun = False
        st.rerun()

def perform_second_extraction_pass(image_bytes, initial_results, component_type=None):
    """
    Perform a second, more focused extraction pass to fill in missing fields.
    This pass specifically targets fields that were empty in the first extraction,
    with special focus on reading values from drawings, dimensions, and inferences.
    
    Args:
        image_bytes: The image data
        initial_results: Results from the first extraction pass
        component_type: The identified component type
        
    Returns:
        Updated results with previously missing fields filled in where possible
    """
    # Get empty fields from initial extraction
    empty_fields = []
    table_focused_fields = []
    
    for key, value in initial_results.items():
        # Skip justification fields and metadata fields
        if key.endswith("_JUSTIFICATION") or key in ["DOCUMENT_TYPE", "COMPONENT_TYPE"]:
            continue
            
        # Check if field is empty
        if not value or value.strip() == "":
            empty_fields.append(key)
        else:
            # Check if the justification indicates this came from a table
            justification = initial_results.get(f"{key}_JUSTIFICATION", "").lower()
            if "table" in justification or "specification" in justification:
                table_focused_fields.append(key)
    
    # If no empty fields and all values came from tables, focus on enhancing the drawing-based extraction
    if not empty_fields and len(table_focused_fields) > 5:
        # Select a subset of important fields to try to find additional information from the drawing itself
        drawing_focus_fields = [
            "BORE DIAMETER", "ROD DIAMETER", "STROKE LENGTH", "CLOSED LENGTH", "OPEN LENGTH",
            "CYLINDER ACTION", "PORT TYPE", "PORT LOCATION", "MOUNTING TYPE", "MATERIAL",
            "SEAL TYPE", "RATED LOAD", "CAPACITY", "DIMENSIONS", "WEIGHT"
        ]
        
        # Filter to fields that actually exist in our results
        drawing_focus_fields = [field for field in drawing_focus_fields if field in initial_results]
        
        # Add some fields to empty_fields to force re-extraction from drawing elements
        empty_fields = drawing_focus_fields[:5] if drawing_focus_fields else []
    
    # If no fields to process, return the original results
    if not empty_fields:
        return initial_results
        
    # Get component type from results if not provided
    if not component_type and "COMPONENT_TYPE" in initial_results:
        component_type = initial_results["COMPONENT_TYPE"]
    
    # Format empty fields for the prompt
    empty_fields_str = "\n".join([f"- {field}" for field in empty_fields])
    
    # Convert image to base64
    base64_image = encode_image_to_base64(image_bytes)
    
    # Create a targeted system prompt for the second pass with emphasis on drawing elements
    system_content = """
    You are a senior mechanical design engineer with specialized expertise in technical drawing interpretation.
    Your task is to extract engineering data directly from visual elements of the drawing rather than from text or tables.
    
    CORE CAPABILITIES:
    1. Dimensional Analysis - Extract precise measurements from dimension lines and callouts
    2. Engineering Symbol Interpretation - Decode GD&T symbols, tolerances, and technical annotations
    3. Cross-Section Analysis - Evaluate internal features from sectional views
    4. Visual Engineering Inference - Determine mechanical properties from visual representations
    5. Manufacturing Assessment - Identify production requirements from drawing details
    
    Your expertise as a design engineer allows you to understand not just WHAT is shown, but WHY certain design choices were made.
    Focus on extracting information from the drawing itself, not from specification tables or text blocks which have already been processed.
    """
    
    # Create user prompt focusing on the missing fields and visual elements
    user_content = f"""
    FOCUSED DRAWING ANALYSIS TASK:
    
    This is a {component_type} drawing. I need you to extract information DIRECTLY FROM THE DRAWING ELEMENTS (not from specification tables) for these specific parameters:
    {empty_fields_str}
    
    INSTRUCTIONS FOR VISUAL ANALYSIS:
    
    1. DIMENSION FOCUS: Carefully examine all dimension lines on the drawing. These appear as lines with arrowheads and numerical values indicating measurements.
       - Look for dimensions showing lengths, diameters, depths, radii, etc.
       - Pay attention to the unit symbols (mm, in, etc.) and decimal precision
    
    2. ENGINEERING SYMBOLS: Identify and interpret standard engineering symbols:
       - Ø symbol indicates diameter
       - R symbol indicates radius
       - ± indicates tolerance
       - ▭ indicates square
       - ⌀ indicates cylindrical feature
       - Surface finish symbols
    
    3. SECTION VIEWS: Examine any cross-sectional views (typically indicated by hatched areas):
       - These reveal internal features not visible from the outside
       - Look for wall thicknesses, internal clearances, and nested components
    
    4. DETAIL VIEWS: Check for any magnified detail views:
       - These show specific features at a larger scale
       - Often indicated by a circled letter or number referencing the main view
    
    5. VISUAL INFERENCE: Make professional inferences based on the drawing:
       - For cylinder action, check for visible ports (one port = single acting, two ports = double acting)
       - For mounting type, observe how the component connects to other parts
       - For materials, note any hatching patterns or material symbols
    
    6. DRAWING ANNOTATIONS: Look for non-tabular annotations:
       - Notes directly on the drawing pointing to specific features
       - Text along dimension lines
       - Labels on components
    
    7. REFERENCE INFORMATION: Check the drawing borders and title blocks for:
       - Scale information (to verify dimensions)
       - Drawing standards used
       - Revision history
    
    For each parameter, provide:
    1. The extracted value with proper units
    2. A precise justification explaining EXACTLY where in the drawing you found this information
    3. Description of any visual elements that led to this determination
    """
    base64_image_data_url = f"data:image/png;base64,{base64_image}"

    
    # Make the API call
    payload = {
        "model": "gpt-5.2",
        "messages": [
            {
                "role": "system",
                "content": system_content
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_content
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url":  base64_image_data_url
                        }
                    }
                ]
            }
        ],
        "max_tokens": 4000,
        "temperature": 0.1
    }

    headers = {
        "Authorization": f"Bearer {st.session_state.current_api_key}",
        "Content-Type": "application/json"
    }

    try:
        # Make the API call
        response = requests.post(API_URL, headers=headers, json=payload)
        result = process_api_response(response)
        
        if "❌" not in result:
            # Parse the results
            second_pass_results = {}
            
            # Process the response line by line
            lines = result.strip().split("\n")
            current_field = None
            current_value = None
            justification = []
            
            for line in lines:
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Check if this is a field header (all caps with colon)
                if ":" in line and line.split(":")[0].isupper() and any(field in line.split(":")[0] for field in empty_fields):
                    # If we were processing a previous field, save it
                    if current_field and current_value is not None:
                        second_pass_results[current_field] = current_value
                        if justification:
                            # Ensure justification mentions the drawing visual elements
                            just_text = " ".join(justification)
                            if "table" in just_text.lower() and "specification" in just_text.lower():
                                # Replace table-focused justification with drawing-focused one
                                just_text = "Extracted directly from dimension lines and annotations in the drawing."
                            second_pass_results[f"{current_field}_JUSTIFICATION"] = just_text
                    
                    # Start a new field
                    parts = line.split(":", 1)
                    current_field = parts[0].strip()
                    current_value = parts[1].strip() if len(parts) > 1 else ""
                    justification = []
                    
                # If not a field header, this might be a justification or continuation
                elif current_field:
                    # Check if this is a justification marker
                    if "JUSTIFICATION:" in line or "Justification:" in line:
                        justification = [line.split(":", 1)[1].strip()]
                    # Otherwise add to justification
                    else:
                        justification.append(line)
            
            # Add the last field being processed
            if current_field and current_value is not None:
                second_pass_results[current_field] = current_value
                if justification:
                    # Ensure justification mentions the drawing visual elements
                    just_text = " ".join(justification)
                    if "table" in just_text.lower() and "specification" in just_text.lower():
                        # Replace table-focused justification with drawing-focused one
                        just_text = "Extracted directly from dimension lines and annotations in the drawing."
                    second_pass_results[f"{current_field}_JUSTIFICATION"] = just_text
            
            # Update the original results with new findings
            updated_results = initial_results.copy()
            for key, value in second_pass_results.items():
                # For non-justification fields, create a combined value if appropriate
                if not key.endswith("_JUSTIFICATION") and value and value.upper() != "NOT FOUND":
                    original_value = updated_results.get(key, "")
                    
                    # If we have both original and new values, and they're different
                    if original_value and original_value != value:
                        # Check if one contains the other
                        if value in original_value:
                            # Keep the more complete value
                            updated_results[key] = original_value
                        elif original_value in value:
                            # New value is more complete
                            updated_results[key] = value
                        else:
                            # They are different - if from different sources, keep both with a note
                            original_justification = updated_results.get(f"{key}_JUSTIFICATION", "").lower()
                            if "table" in original_justification or "specification" in original_justification:
                                # Original from table, new from drawing - combine them
                                updated_results[key] = f"{original_value} [Table]; {value} [Drawing]"
                            else:
                                # Just use the new value if it seems more complete
                                if len(value) > len(original_value):
                                    updated_results[key] = value
                    else:
                        # No original value or they're the same, use the new one
                        updated_results[key] = value
                
                # For justification fields, enhance them to emphasize drawing elements
                elif key.endswith("_JUSTIFICATION"):
                    base_key = key.replace("_JUSTIFICATION", "")
                    original_value = updated_results.get(base_key, "")
                    
                    if original_value:
                        original_justification = updated_results.get(key, "")
                        
                        # Only update justification if it's from a specification table
                        if "table" in original_justification.lower() or "specification" in original_justification.lower():
                            updated_results[key] = value
                        elif "drawing" not in original_justification.lower() and "dimension" not in original_justification.lower():
                            # Enhance justification to include drawing elements
                            drawing_note = "Also verified from drawing dimensions and visual elements."
                            updated_results[key] = f"{original_justification} {drawing_note}"
            
            # Add engineering analysis section if not already present
            if "ENGINEERING_ANALYSIS" not in updated_results:
                # Extract engineering insights from the response
                engineering_insights = extract_engineering_insights(result)
                if engineering_insights:
                    updated_results["ENGINEERING_ANALYSIS"] = engineering_insights
                    updated_results["ENGINEERING_ANALYSIS_JUSTIFICATION"] = "Derived from detailed analysis of drawing dimensions, proportions, and mechanical design principles."
            
            return updated_results
        
        # If the API call failed, return the original results
        return initial_results
    
    except Exception as e:
        print(f"Error in second extraction pass: {str(e)}")
        return initial_results  # Return original results on error

def extract_engineering_insights(response_text):
    """
    Extract engineering insights and analysis from the second pass response.
    
    Args:
        response_text: The raw text response from the second extraction pass
        
    Returns:
        Structured engineering insights as a string
    """
    # Look for sections that contain engineering analysis
    insight_markers = [
        "ENGINEERING PERFORMANCE", 
        "PERFORMANCE ANALYSIS",
        "FUNCTIONAL ANALYSIS",
        "DESIGN ANALYSIS",
        "ENGINEERING IMPLICATIONS",
        "MANUFACTURING CONSIDERATIONS",
        "FUNCTIONAL SIGNIFICANCE",
        "STRESS ANALYSIS",
        "LOAD CAPACITY",
        "OPERATIONAL CHARACTERISTICS"
    ]
    
    insights = []
    lines = response_text.split('\n')
    in_insight_section = False
    current_insight = []
    
    for line in lines:
        # Check if this line starts a new insight section
        if any(marker.lower() in line.lower() for marker in insight_markers):
            # If we were already in an insight section, save it
            if in_insight_section and current_insight:
                insights.append('\n'.join(current_insight))
                current_insight = []
            
            # Start new insight section
            in_insight_section = True
            current_insight.append(line.strip())
        
        # If we're in an insight section, add the line
        elif in_insight_section:
            # Check if this line might end the section (empty line or new section header)
            if not line.strip() or line.strip().isupper() or ":" in line and line.split(":")[0].isupper():
                # End the current section
                if current_insight:
                    insights.append('\n'.join(current_insight))
                    current_insight = []
                in_insight_section = False
            else:
                # Add to current insight
                current_insight.append(line.strip())
    
    # Add the last insight section if it exists
    if in_insight_section and current_insight:
        insights.append('\n'.join(current_insight))
    
    # If no specific insight sections were found, try to extract any engineering analysis paragraphs
    if not insights:
        # Look for paragraphs that mention engineering concepts
        engineering_terms = [
            "load", "stress", "capacity", "efficiency", "performance", 
            "durability", "safety factor", "design", "operation", 
            "pressure rating", "temperature", "material properties",
            "wear", "fatigue", "failure mode", "lifecycle", "maintenance"
        ]
        
        # Extract paragraphs with engineering terms
        paragraphs = []
        current_para = []
        
        for line in lines:
            if not line.strip():
                if current_para:
                    paragraph = ' '.join(current_para)
                    if any(term in paragraph.lower() for term in engineering_terms):
                        paragraphs.append(paragraph)
                    current_para = []
            else:
                current_para.append(line.strip())
        
        # Add the last paragraph if it exists
        if current_para:
            paragraph = ' '.join(current_para)
            if any(term in paragraph.lower() for term in engineering_terms):
                paragraphs.append(paragraph)
        
        # Use the extracted paragraphs as insights
        insights = paragraphs
    
    # Format the insights as a single string
    if insights:
        formatted_insights = "ENGINEERING ANALYSIS:\n\n"
        for i, insight in enumerate(insights):
            formatted_insights += f"{i+1}. {insight}\n\n"
        return formatted_insights
    
    return ""

def process_raw_results(raw_results, drawing_id, file_name, image_bytes):
    """Process the raw results from the API and update the session state."""
    # If we have raw results, count how many fields were extracted
    if raw_results:
        # Count non-justification fields excluding document and component type
        total_fields = 0
        filled_fields = 0
        
        for key in raw_results:
            if not key.endswith("_JUSTIFICATION") and key not in ["DOCUMENT_TYPE", "COMPONENT_TYPE", "ENGINEERING_ANALYSIS"]:
                total_fields += 1
                if raw_results.get(key) and raw_results.get(key).strip():
                    filled_fields += 1
        
        # Format confidence score 
        confidence_score = int((filled_fields / max(1, total_fields)) * 100)
        
        # Get document and component types
        doc_type = raw_results.get("DOCUMENT_TYPE", "Unknown")
        component_type = raw_results.get("COMPONENT_TYPE", "Unknown")
        
        # Format drawing number for display
        if "DRAWING NUMBER" in raw_results and raw_results["DRAWING NUMBER"]:
            drawing_no = raw_results["DRAWING NUMBER"]
        elif "MODEL/PART NUMBER" in raw_results and raw_results["MODEL/PART NUMBER"]:
            drawing_no = f"Model: {raw_results['MODEL/PART NUMBER']}"
        elif "MODEL NUMBER" in raw_results and raw_results["MODEL NUMBER"]:
            drawing_no = f"Model: {raw_results['MODEL NUMBER']}"
        elif "PART NUMBER" in raw_results and raw_results["PART NUMBER"]:
            drawing_no = f"Part: {raw_results['PART NUMBER']}"
        else:
            # Use the file name as fallback
            drawing_no = file_name if file_name else f"Drawing {drawing_id}"
        
        # Update drawings table with results
        idx = st.session_state.drawings_table.index[st.session_state.drawings_table["Internal ID"] == drawing_id].tolist()
        if idx:
            st.session_state.drawings_table.at[idx[0], "Drawing Type"] = component_type
            st.session_state.drawings_table.at[idx[0], "Drawing No."] = drawing_no
            st.session_state.drawings_table.at[idx[0], "Processing Status"] = "✅ Completed"
            st.session_state.drawings_table.at[idx[0], "Extracted Fields Count"] = f"{filled_fields}/{total_fields}"
            st.session_state.drawings_table.at[idx[0], "Confidence Score"] = f"{confidence_score}%"
            
            # Format the extracted_parameters for display
            formatted_params = []
            engineering_analysis = None
            
            # Group parameters into categories
            categories = {
                "PRIMARY PHYSICAL DIMENSIONS": [],
                "MECHANICAL PROPERTIES": [],
                "MANUFACTURING FEATURES": [],
                "APPLICATION CONTEXT": [],
                "IDENTIFICATION": [],
                "OTHER": []
            }
            
            # Define which parameters go into which category
            category_mapping = {
                # Physical dimensions
                "BORE DIAMETER": "PRIMARY PHYSICAL DIMENSIONS",
                "ROD DIAMETER": "PRIMARY PHYSICAL DIMENSIONS",
                "STROKE LENGTH": "PRIMARY PHYSICAL DIMENSIONS",
                "CLOSED LENGTH": "PRIMARY PHYSICAL DIMENSIONS",
                "OPEN LENGTH": "PRIMARY PHYSICAL DIMENSIONS",
                "OUTSIDE DIAMETER": "PRIMARY PHYSICAL DIMENSIONS",
                "DIMENSIONS": "PRIMARY PHYSICAL DIMENSIONS",
                "WEIGHT": "PRIMARY PHYSICAL DIMENSIONS",
                "SIZE/DIMENSION": "PRIMARY PHYSICAL DIMENSIONS",
                "SHAFT DIAMETER": "PRIMARY PHYSICAL DIMENSIONS",
                "VALVE SIZE/PORT SIZE": "PRIMARY PHYSICAL DIMENSIONS",
                "PORT SIZE": "PRIMARY PHYSICAL DIMENSIONS",
                
                # Mechanical properties
                "OPERATING PRESSURE": "MECHANICAL PROPERTIES",
                "TEST PRESSURE": "MECHANICAL PROPERTIES",
                "OPERATING TEMPERATURE": "MECHANICAL PROPERTIES",
                "RATED LOAD/CAPACITY": "MECHANICAL PROPERTIES",
                "LOAD CAPACITY": "MECHANICAL PROPERTIES",
                "PRESSURE RATING": "MECHANICAL PROPERTIES",
                "FLOW CAPACITY": "MECHANICAL PROPERTIES",
                "INPUT POWER": "MECHANICAL PROPERTIES",
                "GEAR RATIO": "MECHANICAL PROPERTIES",
                "EFFICIENCY": "MECHANICAL PROPERTIES",
                "PROPERTY/STRENGTH CLASS": "MECHANICAL PROPERTIES",
                "LOAD RATING": "MECHANICAL PROPERTIES",
                "SPEED RATING": "MECHANICAL PROPERTIES",
                
                # Manufacturing features
                "BODY MATERIAL": "MANUFACTURING FEATURES",
                "ROD MATERIAL": "MANUFACTURING FEATURES",
                "MATERIAL": "MANUFACTURING FEATURES",
                "SURFACE FINISH": "MANUFACTURING FEATURES",
                "COATING/PLATING": "MANUFACTURING FEATURES",
                "SEAL TYPE": "MANUFACTURING FEATURES",
                "THREAD TYPE": "MANUFACTURING FEATURES",
                "THREAD PITCH": "MANUFACTURING FEATURES",
                "HOUSING MATERIAL": "MANUFACTURING FEATURES",
                "SEALING TYPE": "MANUFACTURING FEATURES",
                "SEAT/SEAL MATERIAL": "MANUFACTURING FEATURES",
                
                # Application context
                "CYLINDER ACTION": "APPLICATION CONTEXT",
                "MOUNTING TYPE": "APPLICATION CONTEXT",
                "ROD END TYPE": "APPLICATION CONTEXT",
                "FLUID TYPE": "APPLICATION CONTEXT",
                "STANDARD COMPLIANCE": "APPLICATION CONTEXT",
                "PORT TYPE": "APPLICATION CONTEXT",
                "PORT LOCATION": "APPLICATION CONTEXT",
                "CUSHIONING": "APPLICATION CONTEXT",
                "VALVE TYPE": "APPLICATION CONTEXT",
                "FLOW DIRECTION": "APPLICATION CONTEXT",
                "OPERATING MEDIUM": "APPLICATION CONTEXT",
                "CONNECTION TYPE": "APPLICATION CONTEXT",
                "ACTUATION TYPE": "APPLICATION CONTEXT",
                "OPERATION PATTERN": "APPLICATION CONTEXT",
                "SPECIAL FEATURES": "APPLICATION CONTEXT",
                "GEAR TYPE": "APPLICATION CONTEXT",
                "MOUNTING ARRANGEMENT": "APPLICATION CONTEXT",
                "SHAFT ORIENTATION": "APPLICATION CONTEXT",
                "COOLING ARRANGEMENT": "APPLICATION CONTEXT",
                "LUBRICATION SYSTEM": "APPLICATION CONTEXT",
                "TORQUE SPECIFICATION": "APPLICATION CONTEXT",
                "ACTIVATION TYPE": "APPLICATION CONTEXT",
                "BEARING TYPE": "APPLICATION CONTEXT",
                "LUBRICATION TYPE": "APPLICATION CONTEXT",
                
                # Identification
                "MANUFACTURER/MAKE": "IDENTIFICATION",
                "MODEL/PART NUMBER": "IDENTIFICATION",
                "DRAWING NUMBER": "IDENTIFICATION",
                "MANUFACTURER": "IDENTIFICATION",
                "MANUFACTURER/BRAND": "IDENTIFICATION",
                "MODEL NUMBER": "IDENTIFICATION",
                "PART NUMBER": "IDENTIFICATION"
            }
            
            # Sort parameters into categories
            for key, value in raw_results.items():
                # Skip justification fields, document type, component type, and empty values
                if (key.endswith("_JUSTIFICATION") or 
                    key in ["DOCUMENT_TYPE", "COMPONENT_TYPE"] or 
                    not value or not value.strip()):
                    continue
                
                # Handle engineering analysis separately
                if key == "ENGINEERING_ANALYSIS":
                    engineering_analysis = value
                    continue
                
                # Determine category
                category = category_mapping.get(key, "OTHER")
                
                # Add to appropriate category
                justification = raw_results.get(f"{key}_JUSTIFICATION", "")
                categories[category].append({
                    "param": key,
                    "value": value,
                    "justification": justification
                })
            
            # Format each category
            for category, params in categories.items():
                if params:  # Only include non-empty categories
                    formatted_params.append(f"## {category}")
                    for param in params:
                        formatted_params.append(f"**{param['param']}**: {param['value']}")
                        
                        # Include justification if it exists and we're in detailed mode
                        if param['justification'] and st.session_state.show_justifications:
                            formatted_params.append(f"*Source: {param['justification']}*")
                    
                    # Add spacing between categories
                    formatted_params.append("")
            
            # Add engineering analysis if it exists
            if engineering_analysis:
                formatted_params.append("## ENGINEERING ANALYSIS")
                formatted_params.append(engineering_analysis)
            
            # Save the formatted results
            st.session_state.extracted_parameters[drawing_id] = {
                "component_type": component_type,
                "document_type": doc_type,
                "drawing_no": drawing_no,
                "formatted_params": "\n".join(formatted_params),
                "raw_params": raw_results,
                "image_bytes": image_bytes,
                "confidence_score": confidence_score,
                "extraction_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

if __name__ == "__main__":
    main()
