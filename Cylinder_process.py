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

# Try to import gradio_client for image upscaling
try:
    from gradio_client import Client
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False
    # st.warning("Gradio client not available. Image upscaling will be disabled. Install with: pip install gradio_client")
    ""

# Set tesseract path if available
if TESSERACT_AVAILABLE:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Users\shrey\Downloads\tesseract-ocr-w64-setup-v5.3.0.20221214.exe"

# Add your imgbb API key here (get one from https://api.imgbb.com/)
IMGBB_API_KEY = "02b10ba01695e9bb477f0155e4b7a3a0"

def upload_to_imgbb(image_bytes):
    """Upload image bytes to imgbb and return the public URL"""
    try:
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            temp_file.write(image_bytes)
            temp_path = temp_file.name
        with open(temp_path, "rb") as file:
            response = requests.post(
                "https://api.imgbb.com/1/upload",
                params={"key": IMGBB_API_KEY},
                files={"image": file}
            )
        os.unlink(temp_path)
        if response.status_code == 200:
            data = response.json()
            return data["data"]["url"]
        else:
            st.error(f"imgbb upload failed: {response.text}")
            return None
    except Exception as e:
        st.error(f"imgbb upload error: {str(e)}")
        return None


def upscale_image(image_bytes):
    """Upscale the image using Gradio API"""
    if not GRADIO_AVAILABLE:
        return image_bytes
    
    try:
        with st.spinner("Upscaling image for better analysis..."):
            # Save image to a temporary file
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_file.write(image_bytes)
                temp_path = temp_file.name
            
            # Create Gradio client with updated parameters to avoid the headers issue
            client = Client(
                "https://bookbot-image-upscaling-playground.hf.space/",
                output_dir=tempfile.gettempdir()
            )
            
            # Use a simpler predict call to avoid connection issues
            try:
                result = client.predict(
                    temp_path,
                    "modelx2",  # Use x2 upscaling mode
                    api_name="/predict"
                )
            except TypeError as e:
                if "extra_headers" in str(e):
                    # Downgrade gradio-client if this error occurs
                    # st.warning("Your gradio-client version might be incompatible. Try: pip install gradio-client==0.6.1")
                    ""
                    return image_bytes
                else:
                    raise e
            
            # Read the upscaled image
            if result and os.path.exists(result):
                with open(result, "rb") as f:
                    upscaled_image_bytes = f.read()
                
                # Clean up temporary files
                try:
                    os.unlink(temp_path)
                    os.unlink(result)
                except:
                    pass
                
                # st.success("Image successfully upscaled for better analysis")
                ""
                return upscaled_image_bytes
            else:
                # st.warning("Upscaling failed, using original image")
                ""
                return image_bytes
    except Exception as e:
        # st.warning(f"Error during image upscaling: {str(e)}. Using original image.")
        ""
        return image_bytes


def parse_ai_response(response_text):
    """Parse the AI response for cylinder-specific data"""
    # Specialized parsing for cylinders
    return response_text


def analyze_engineering_drawing(image_bytes, component_type="cylinder"):
    """Analyze the uploaded drawing for cylinder-specific parameters with ultra-precise prompts"""
    parameters = {
        "CYLINDER ACTION": "NA",
        "BORE DIAMETER": "NA",
        "ROD DIAMETER": "NA",
        "STROKE LENGTH": "NA",
        "CLOSE LENGTH": "NA",
        "OPERATING PRESSURE": "NA",
        "OPERATING TEMPERATURE": "NA",
        "MOUNTING": "NA",
        "ROD END": "NA",
        "FLUID": "NA",
        "DRAWING NUMBER": "NA",
        "REVISION": "NA"
    }
    
    # Upload image to imgbb and get public URL
    image_url = upload_to_imgbb(image_bytes)
    if not image_url:
        st.error("Failed to upload image to imgbb. Analysis cannot proceed.")
        return {"component_type": component_type, "parameters": parameters}
    
    system_content = """You are an elite mechanical drawing interpreter with 50 years of experience as a hydraulic cylinder engineer. 
    Your expertise lies in analyzing technical drawings of hydraulic and pneumatic cylinders with unparalleled precision. 
    You can read between the lines, synthesize information from disparate parts of the drawing, and apply deep domain knowledge. 
    Your ultimate goal is to extract 100% accurate specifications and design values from these drawings. 
    If a value is not explicitly stated, you MUST use your extensive engineering knowledge, industry standards, 
    and the provided inference rules to determine the most probable and accurate value. 
    Only use 'NA' if a parameter is truly uninferable and meaningless in the context of a cylinder drawing, 
    after exhausting all inference possibilities and considering all typical engineering values."""

    user_content = """
YOU MUST EXTRACT 100% OF THE FOLLOWING 12 PARAMETERS — NO EXCEPTIONS. DO NOT EXTRACT ANY OTHER PARAMETERS.

The 12 required parameters are:
1. CYLINDER ACTION
2. BORE DIAMETER
3. ROD DIAMETER
4. STROKE LENGTH
5. CLOSE LENGTH
6. OPERATING PRESSURE
7. OPERATING TEMPERATURE
8. MOUNTING
9. ROD END
10. FLUID
11. DRAWING NUMBER
12. REVISION

### 🧠 SYSTEM ROLE

You are **Extractor-9000-Pinnacle**, a high-fidelity AI designed for extracting structured technical parameters from complex 2D cylinder engineering drawings. Your core capabilities:

* **High-resolution OCR + Layout Parsing**: Tables, leaders, balloons, title blocks, callouts
* **Visual Classification**: When allowed (e.g., mounting, rod-end)
* **Chain-of-Thought Reasoning**: Every parameter must be reasoned in a scratchpad log
* **Contextual Cross-validation**: Validate data across title blocks, tables, dimensions, and drawing annotations
* **Red-Line Rules Enforcement**
* **Final Audit Gate** after extraction
* **Modular logic blocks** for fluid detection, mounting, rod-end style, and cylinder configuration

---

### 🔴 ABSOLUTE EXTRACTION RULES

1. Extract all parameters exactly as defined below.
2. Use explicit values found in the drawing whenever available.
3. If a value is not explicitly stated, apply your 50 years of hydraulic/pneumatic cylinder engineering expertise and the inference rules below to determine the most accurate value.
4. Only use "NA" if a parameter is truly uninferable and meaningless in this context, after exhausting all inference possibilities.
5. Accept parameter names with ≥90% similarity to the names below (see equivalences).

---

### 📋 PARAMETER NAME EQUIVALENCES (≥90% match):

- "BORE:", "ID:" → "BORE DIAMETER"
- "ROD:", "RD:" → "ROD DIAMETER"
- "STROKE:", "S.L." → "STROKE LENGTH"
- "CLOSE:" → "CLOSE LENGTH"
- "PRESSURE:" → "OPERATING PRESSURE"
- "TEMP:" → "OPERATING TEMPERATURE"
- "DWG NO:", "DRG NO:", "PART NO:" → "DRAWING NUMBER"
- "REV", "Revision" → "REVISION"
- "FLUID:", "MEDIUM:" → "FLUID"
- "MOUNTING:" → "MOUNTING"
- "ACTION:" → "CYLINDER ACTION"

---

### 🔴 RED-LINE RULES (ENFORCE AFTER EACH PARAMETER)

| Rule   | Description                                                                                                           |
| ------ | --------------------------------------------------------------------------------------------------------------------- |
| **R1** | BORE: Must contain literal terms "BORE", "BORE DIA" or use visual estimation with scale                              |
| **R2** | Mounting & Rod-End Styles can be visually inferred ONLY if allowed                                                    |
| **R3** | Learning Enhancement: Use patterns from similar drawings to infer missing fields                                      |
| **R4** | Operating Pressure = Working Pressure; Rod = Piston = Rod Diameter; Drawing Number = Model (if drawing number absent) |       
| **R5** | If value is not found in the drawing, Strictly Return NA and not the explanation.
---

## 🔁 18-STEP EXTRACTION WORKFLOW (Scratchpad Log Per Step)

1. **Global OCR Sweep** – list every text block, table, leader, annotation
2. **Spec Table Lock-On** – OCR table row-by-row; mark all values (TBL)
3. **Keyword Spotlight** – scan all text for keywords like "BORE", "Φ", "Ø", "ID", "STROKE", "ROD", "PRESSURE"
4. **Title Block Deep Dive** – OCR lower-right title block area fully
5. **Dimension Leader Scan** – Find dimensions like "362 CLOSED", "Ø110", "STROKE 300"
6. **Visual Mounting Type Detection** (see MOUNTING DETECTION MODULE below)
7. **Contextual Analysis** – interpret overall drawing context for material, configuration, load, and fluid
8. **Red-Line Audit** – run checklist R1–R5
9. **Detail Enhancement** – use zoom/enhancement for tight tables/fine print
10. **Edge Case Handling** – if label ambiguous, fallback to drawing conventions. Mark NA if unsure.
11. **Cross Validation** – ensure parameters align across drawing views
12. **Review All Parameters** – completeness and accuracy check
13. **Image Enhancement** – enhance if low contrast
14. **Hybrid Visual-Textual Analysis** – combine data sources if one is missing
15. **Adaptive Learning** – use previous extractions to inform patterns
16. **Final Audit Check** – All parameters validated?
17. **FLUID DETECTION MODULE** (see below)
18. **FINAL VERIFICATION** – Output formatted results after audit pass

---

### 📐 CRITICAL PARAMETERS TO EXTRACT (AND INFER IF NECESSARY):

**BORE DIAMETER**: Look for **BORE** labeled with "CYLINDER BORE", "BORE:", or the diameter symbol "Ø" near the barrel of the cylinder.
    The **bore diameter** refers to the inner diameter of the cylinder tube.
    If the bore diameter is not labeled, infer it by checking the piston diameter or the tube's outer diameter (OD) and using wall thickness (if available).
    Typically, the bore will be shown close to the barrel in cross-section views of the cylinder.

**STROKE LENGTH**: Search for **STROKE** labeled with "STROKE LENGTH", "STROKE:", or abbreviations like "S.L."
    Stroke length is the distance the piston moves inside the cylinder from its fully retracted position to its fully extended position.
    If stroke length is not explicitly mentioned, compute it from the extended length and close length if both are available.
    Look for annotations related to the **piston travel range** or **stroke markings** in the technical sections or dimensions of the cylinder.

**CLOSE LENGTH**: Look for labels such as CLOSE LENGTH, RETRACTED LENGTH, or MINIMUM LENGTH. 
    In the image, CLOSE LENGTH is calculated by subtracting the **STROKE LENGTH** from the EXTENDED LENGTH.
    The closed length is measured from the centerline of the mounting points at each end of the cylinder, to the end of the cylinder in the retracted position, where the piston rod is fully inside the cylinder.
    CLOSE LENGTH is often mentioned near the cylinder retraction description or in the context of piston movement.

**ROD DIAMETER**: Look for **ROD DIAMETER**, **ROD**, or "Ø" symbols near the **piston rod** section of the cylinder.
    The **ROD DIAMETER** is the diameter of the piston rod, and in the drawing, it is clearly marked near the rod area.
    If not explicitly mentioned, look for **dimensions near the rod section** of the cylinder and check if there are any cross-sectional views showing the rod's size.

**OPERATING PRESSURE**: Look for labels such as PRESSURE, WORKING PRESSURE, or similar terms. Check for units like BAR, MPa, or any pressure-related indications in the drawing.
    The OPERATING PRESSURE is usually found in the technical specification section or near pressure-related diagrams. 
    If it's missing, infer it based on related symbols or contextual information, such as pressure valve annotations.

**OPERATING TEMPERATURE**: Look for labels like TEMP, TEMPERATURE, or any closely related terms in the drawing. This value typically appears in the technical specification section. Operating temperature may be shown as a single number or AS A RANGE.
    If a temperature range is give, you need to return the entire range.
    If the temperature is not explicitly mentioned, look for system specifications or operational limits that could suggest the temperature range. 
    You can also infer it based on the type of fluid used or the working conditions described in the drawing.

**DRAWING NUMBER**: Search for labels such as DWG NO, DRG NO, PART NO, or any similar identifier.
    The DRAWING NUMBER is typically located at the right bottom section of the image in the title block or near the technical specifications.
    Examine the corners for drawing number mostly it will be in bottom right corner section but if not here then look for other corners.

**REVISION**: Look for "REV", "Revision" or any mentioned with any close name, often located near the drawing number or part number. 
    The revision number will typically be a two-digit value (e.g., 00, 01, 02, 03).
    If found, return the revision value; if no revision number is present, return "00" if it is missing.

**FLUID**: Look for "FLUID:", "OIL:", "AIR:". (See FLUID HANDLING RULES below)

**MOUNTING**: Identify the mounting type either by visual clues or text labels like CLEVIS, FLANGE, LUG, TRUNNION, or ROD EYE.
    Mounting types are typically indicated in the technical specification section or near the cylinder's visual diagram.
    If not explicitly labeled, check VISUAL INFERENCE GUIDELINES below so that you will be able to analyse by observing the diagram.

**ROD END**: Look for labels such as ROD END, THREAD, CLEVIS, or ROD EYE.
    These terms define the type of attachment or connection at the end of the piston rod. 
    If no label is found, look for visual clues showing the type of connection, such as thread types or clevis fittings in the diagram.

**CYLINDER ACTION**: Infer the cylinder action based on the number of ports or the cylinder type. A double-acting cylinder typically has 2 ports, while a single-acting cylinder has only 1 port.
    Infer the cylinder action by looking for acting-related terms such as **"DOUBLE ACTING"** or **"SINGLE ACTING"** in the text area of the drawing.

---

### 📊 EXTRACTION STRATEGY:

- First, extract from specification/dimension tables (highest priority).
- Then parse callouts, arrows, labeled dimensions near drawing features and find values from the drawing.
- Examine the corners for drawing number mostly it will be in bottom right corner section but if not here then look for other corners.
- Check notes or remarks for pressure, temperature, special features.
- Use geometric shape recognition for mounting and rod end types.
- Employ OCR reasoning to read faint or rotated text.
- Respect units as given; do not convert unless instructed.
- Avoid estimating values by scaling the drawing.
- Use your deep domain expertise and inference rules to fill gaps logically.

---

### 👁️ VISUAL INFERENCE GUIDELINES:

**CLEVIS**: A clevis mount appears as a forked U-shaped structure typically located at the rear (cap end) of the cylinder. It has two parallel arms with a transverse hole through both for a pin, allowing the cylinder to pivot during operation. This configuration is commonly used in applications where rotational freedom is required. Visually, look for symmetrical fork arms extending from the cylinder and a clearly defined central hole aligned across the arms.

**FLANGE**: A flange mount is identified by a flat disc or rectangular plate extending from the front or rear of the cylinder, featuring multiple evenly spaced bolt holes around its perimeter. This type of mount is used for rigid, fixed installations where no rotation is needed. In drawings, it appears as a flush face plate directly attached to the end cap, often with visible bolt circle markings or dimensioned bolt patterns.

**LUG**: A lug mount appears as flat side tabs with bolt holes, typically mounted on the side of the cylinder barrel. These are used for side-mounting applications where the cylinder needs to be attached to a surface.

**TRUNNION**: A trunnion mount features a cylindrical pivot pin or axle that extends horizontally from the center or ends of the cylinder barrel. This design enables pivoting around the trunnion axis and is ideal for applications where the cylinder must follow an arc or swing. Look for a smooth cylindrical shaft centered and perpendicular to the cylinder body, either mid-barrel or attached to the heads.

**ROD END CLEVIS**: A clevis on the rod end is a small U-shaped fork with a pinhole, used to attach the rod to a mating component. This allows angular freedom at the connection point. Visually, it mirrors the clevis mounting style but is located at the tip of the piston rod. It typically has two short arms extending from the rod with a central hole that accommodates a pivot pin.

**ROD END THREAD**: A threaded rod end is seen as a straight cylindrical shaft with visible threads (male) or a recessed threaded hole (female). This allows for secure mechanical fastening into a mating part. In drawings, look for parallel ridges or note callouts indicating thread specifications such as "M20x1.5" or internal threading with depth markings.

**ROD END ROD EYE**: The rod eye is a looped end with a centered hole, often used with a spherical bearing or bushing to allow for misalignment and multidirectional articulation. It appears as a circular eyelet at the rod's tip, and may contain additional details like a bearing symbol or internal ring. This design provides robust connection while accommodating slight angular movement.

---

### ⚙️ MOUNTING DETECTION MODULE

If text doesn't clearly state the mounting type, perform visual reasoning:

* **Step 1: Structural Mapping**
  Analyze ends of the cylinder (head/cap/rod sides). Map any protruding shapes, holes, or flat surfaces to mounting clues.

* **Step 2: Visual-Reasoning Map** (apply fuzzy logic to shapes)
  - **Clevis**: Forked "U"-shape with holes on both sides
  - **Threaded Clevis**: Forked U-shape + visible threading
  - **Flange**: Flat ring/plate with bolt holes near the end face
  - **Trunnion**: Round pivot pins protruding from side or mid-body
  - **Lug**: Flat side tabs with bolt holes
  - **Spherical Rod End**: Rounded housing with ball-socket/eyelet

* **Step 3: Multi-view Cross Check**
  Compare side/top views if provided. Prioritize end views for mounting logic.

* **Step 4: Confidence Estimation**
  If shape matches multiple categories weakly → return `unknown`
  If single strong match → classify directly

---

### 🌊 FLUID HANDLING RULES (STRICT):

- If "Mineral Oil" is mentioned, return **HYD. OIL MINERAL**.
- If "HLP68", "ISO VG46", or "Synthetic Oil" are mentioned, keep the term as it is.
- If "Compressed Air", "Pneumatic", or "AIR" is mentioned, return **FLUID = AIR**.
- If fluid is not directly specified but the drawing indicates a **hydraulic cylinder** (e.g., high pressure, robust construction), infer **HYD. OIL MINERAL**.
- If the system is **pneumatic** (indicated by words like pneumatic or compressed air), infer **FLUID = AIR**.

Pay particular attention to words like **hydraulic** or **pneumatic** within the drawing, as these terms will be a key indicator of the type of fluid, even if the word "fluid" is not directly mentioned.

### 🌊 FLUID DETECTION MODULE (Hierarchical Scoring):

**Objective**: Determine if the cylinder is **HYDRAULIC** or **PNEUMATIC**

#### Step 1: Explicit Terms (Score +5)
- "HYDRAULIC", "MINERAL OIL", "HLP", "VG32", "ATF" → +5 Hydraulic
- "PNEUMATIC", "AIR", "COMPRESSED AIR", "ISO 8573" → +5 Pneumatic

#### Step 2: Pressure (Score +5)
- Pressure > 60 bar → +5 Hydraulic
- Pressure ≤ 12 bar → +5 Pneumatic

#### Step 3: Port/Thread Sizes
- Threads like "M64x3", "1" BSP" → +3 Hydraulic
- Threads like "G1/8", "1/4 NPT", "M16x1" → +3 Pneumatic

#### Step 4: Bore/Rod Ratio
- Large bore & thick rod: Ø160/Ø110 → +2 Hydraulic
- Thin rod & medium bore: Ø80/Ø25 → +2 Pneumatic

#### Step 5: Construction Cues
- Spherical bearings, welded housing, heavy tie rods → +2 Hydraulic
- Magnetic piston, light alloy, ISO pattern → +2 Pneumatic

---

### ✅ OUTPUT REQUIREMENTS:

- Avoid printing complex special characters (e.g., Omega (Ω), diameter (⌀)), but if simple symbols like plus (+), minus (−), or degree (°) appear, they are allowed. If any complex symbol is present, exclude the symbol and just take the number or text around it without using the symbol.
- Use "NA" for uninferable values only after exhausting all inference possibilities.
- Return your reasoning + extracted values exactly as follows:

---

#### Markdown Format – Scratchpad Reasoning (Think Log)

```
<parameter name> : Your thinking process for this parameter
```

#### Final Output Block (No extra words):

```
CYLINDER ACTION:  
BORE DIAMETER:  
ROD DIAMETER:  
STROKE LENGTH:  
CLOSE LENGTH:  
OPERATING PRESSURE:  
OPERATING TEMPERATURE:  
MOUNTING:  
ROD END:  
FLUID:  
DRAWING NUMBER:  
REVISION:  
```

NOW ANALYZE THIS CYLINDER DRAWING AND EXTRACT ONLY THE 12 PARAMETERS LISTED ABOVE, APPLYING INFERENCE RULES AS NEEDED. DO NOT EXTRACT ANY OTHER PARAMETERS.

"""

    API_URL = "https://api.openai.com/v1/chat/completions"
    API_KEY = os.getenv("OPENAI_API_KEY")
    print(f"[API Key]: {API_KEY}")

    payload = {
        "model": "gpt-5.2", 
        "messages": [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_content},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}}
                ]
            }
        ],
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    print(f"[Model being used]: {payload['model']}")
    st.write(f"[Model being used]: {payload['model']}")

    try:
        with st.spinner('Conducting precise cylinder analysis...'):
            import json, pprint
            print("=== RAW PAYLOAD ===")
            pprint.pprint(payload, width=120)
            print("=== SERIALISED ===")
            print(json.dumps(payload, ensure_ascii=False, indent=2)[:2000], "…")
            response = requests.post(API_URL, headers=headers, json=payload)
            print("HTTP", response.status_code)
            print("HEADERS", response.headers)
            print("BODY", response.text)
            st.write("[OpenAI API Main Response]", response)
            print("[OpenAI API Main Response]", response)
            if response.status_code == 200:
                response_json = response.json()
                st.write("[OpenAI API Main Response]", response_json)
                print("[OpenAI API Main Response]", response_json)
                if "choices" in response_json:
                    content = response_json["choices"][0]["message"]["content"]
                    
                    lines = content.strip().split('\n')
                    for line in lines:
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip().upper()
                            value = value.strip()
                            
                            # Clean up value and validate
                            if value and value.upper() not in ["NA", "N/A", "NOT SPECIFIED", "NONE", "NOT FOUND", "UNKNOWN", ""]:
                                # Remove common brackets and clean
                                value = value.replace('[', '').replace(']', '').strip()
                                
                                # Special handling for specific parameters
                                if key in ["BORE DIAMETER"]:
                                    # Only accept if it's clearly from a table/label specification
                                    if any(indicator in content.lower() for indicator in ["table", "specification", "spec", "labeled", "marked"]):
                                        if key in parameters:
                                            parameters[key] = value
                                elif key in parameters:
                                    parameters[key] = value

                    # Strict fluid processing - only convert "Mineral Oil"
                    if parameters.get("FLUID", "NA") != "NA":
                        fluid_value = parameters["FLUID"]
                        if "mineral oil" in fluid_value.lower():
                            parameters["FLUID"] = "HYD. OIL MINERAL"
                        elif any(air_keyword in fluid_value.lower() for air_keyword in ["air", "pneumatic", "compressed air"]):
                            parameters["FLUID"] = "AIR"
                        # Keep all other fluid specifications exactly as found

        # Enhanced validation with focused re-extraction for critical missing parameters
        critical_missing = []
        for param in ["BORE DIAMETER", "FLUID", "MOUNTING"]:
            if parameters.get(param, "NA") == "NA":
                critical_missing.append(param)

        # Focused re-extraction for missing critical parameters
        # if critical_missing:
        #     for param in critical_missing:
        #         focused_result = focused_parameter_extraction(image_bytes, param, API_URL, headers)
        #         if focused_result and focused_result != "NA":
        #             # Apply same strict rules
        #             if param == "FLUID":
        #                 if "mineral oil" in focused_result.lower():
        #                     parameters["FLUID"] = "HYD. OIL MINERAL"
        #                 elif any(air_keyword in focused_result.lower() for air_keyword in ["air", "pneumatic", "compressed air"]):
        #                     parameters["FLUID"] = "AIR"
        #                 else:
        #                     parameters["FLUID"] = focused_result
        #             else:
        #                 parameters[param] = focused_result

        # Apply intelligent defaults only for non-critical parameters
        apply_conservative_defaults(parameters)

    except Exception as e:
        st.error(f"Error during analysis: {str(e)}")
        # Apply conservative defaults even on error
        apply_conservative_defaults(parameters)
    
    return {"component_type": component_type, "parameters": parameters}


def focused_parameter_extraction(image_bytes, parameter, api_url, headers):
    """Focused extraction for specific critical parameters"""
    focused_prompts = {
        "BORE DIAMETER": """
ULTRA-FOCUSED TASK: Find BORE DIAMETER from specification table or explicit label ONLY.

STRICT RULES:
- ONLY extract if you see "BORE:", "BORE DIA:", "BORE DIAMETER:", "ID:" in a table or label
- DO NOT calculate from dimension lines or visual measurement
- Look specifically in specification tables or technical data boxes
- If not explicitly labeled in text, return "NA"

Search locations:
1. Specification table with parameter names
2. Technical data box
3. Explicit text labels with "BORE" keyword

Output: [number only] or "NA"
""",
        "FLUID": """
ULTRA-FOCUSED TASK: Find exact FLUID specification as written.

SEARCH LOCATIONS:
1. Title block fluid specification
2. Operating conditions section
3. Technical specifications table
4. "Fluid:" or "Medium:" labels

EXTRACT EXACTLY AS WRITTEN:
- "Hydraulic oil HLP68" → keep as "Hydraulic oil HLP68"
- "ISO VG46" → keep as "ISO VG46"
- "Mineral Oil" → can convert to "HYD. OIL MINERAL"
- "Air" → use "AIR"

Output: [exact fluid specification as found]
""",
        "MOUNTING": """
ULTRA-FOCUSED TASK: Identify MOUNTING type from visual structure and any text labels.

VISUAL IDENTIFICATION:
- CLEVIS: Two parallel mounting ears with spherical bearing
- FLANGE: Circular mounting plate with bolt holes in pattern
- LUG: Side-mounted brackets on cylinder body
- TRUNNION: Pin through middle of cylinder barrel
- ROD EYE: Single eye at rod end

Also check for text mentioning mounting type.

Output: [Clevis/Flange/Lug/Rod Eye/Trunnion]
"""
    }

    payload = {
        "model": "gpt-5.2",
        "reasoning": {"effort": "high"},
        "messages": [
            {"role": "system", "content": f"You are a specialist in extracting {parameter} from technical drawings with 100% accuracy."},
            {
                "role": "user", 
                "content": [
                    {"type": "text", "text": focused_prompts},
                    {"type": "image_url", "image_url": {"url": upload_to_imgbb(image_bytes), "detail": "high"}}
                ]
            }
        ],
        "temperature": 0
    }

    print(f"[Model being used for focused extraction ({parameter})]: {payload['model']}")
    st.write(f"[Model being used for focused extraction ({parameter})]: {payload['model']}")

    try:
        response = requests.post(api_url, headers=headers, json=payload)
        st.write(f"[OpenAI API Focused Extraction: {parameter}]", response)
        print(f"[OpenAI API Focused Extraction: {parameter}]", response)
        if response.status_code == 200:
            # Log the full response from the Bot
            st.write(f"[OpenAI API Focused Extraction: {parameter}]", response.json())
            print(f"[OpenAI API Focused Extraction: {parameter}]", response.json())
            content = response.json()["choices"][0]["message"]["content"].strip()
            
            # Extract the value from response
            if ':' in content:
                _, value = content.split(':', 1)
                value = value.strip().replace('[', '').replace(']', '')
            else:
                value = content
                
            if value.upper() not in ["NA", "N/A", "NOT FOUND", "NOT SPECIFIED", ""]:
                return value
    except:
        pass
    
    return None


def apply_conservative_defaults(parameters):
    """Apply conservative intelligent defaults for non-critical parameters only"""
    
    # Only apply defaults for action type and rod end based on available data
    if parameters["CYLINDER ACTION"] == "NA":
        if parameters.get("FLUID") in ["HYD. OIL MINERAL", "Hydraulic oil HLP68"] or "hydraulic" in parameters.get("FLUID", "").lower():
            parameters["CYLINDER ACTION"] = "DOUBLE ACTING"
        elif parameters.get("FLUID") == "AIR" or "air" in parameters.get("FLUID", "").lower():
            parameters["CYLINDER ACTION"] = "SINGLE ACTING"
    
    # Rod end based on mounting
    if parameters["ROD END"] == "NA":
        if parameters.get("MOUNTING") == "Clevis":
            parameters["ROD END"] = "clevis"
        else:
            parameters["ROD END"] = "thread"
    
    # Conservative temperature defaults
    # if parameters["OPERATING TEMPERATURE"] == "NA":
    #     if "hydraulic" in parameters.get("FLUID", "").lower():
    #         parameters["OPERATING TEMPERATURE"] = "80"
    #     elif parameters.get("FLUID") == "AIR":
    #         parameters["OPERATING TEMPERATURE"] = "60"


def process_uploaded_file(uploaded_file):
    """Process the uploaded file for cylinder analysis"""
    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        if uploaded_file.type == "application/pdf":
            images = convert_pdf_to_images(file_bytes, uploaded_file.name)
            if images and images[0]:
                # Upscale the first page of the PDF
                upscaled_image = upscale_image(images[0])
                return upscaled_image
        else:
            # For direct image uploads, return the bytes
            try:
                # Convert to PIL Image and back to bytes to ensure consistent format
                image = Image.open(io.BytesIO(file_bytes))
                img_byte_arr = io.BytesIO()
                image = image.convert('RGB')  # Convert to RGB mode for consistency
                image.save(img_byte_arr, format='JPEG', quality=95)
                image_bytes = img_byte_arr.getvalue()
                
                # Upscale the image
                upscaled_image = upscale_image(image_bytes)
                return upscaled_image
            except Exception as e:
                # st.error(f"Error processing image: {str(e)}")
                ""
                return None
    return None


def convert_pdf_to_images(pdf_bytes, filename=""):
    """Convert PDF bytes to images"""
    try:
        # Try using PyMuPDF first (faster and more reliable)
        try:
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            image_list = []
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # Higher quality
                img_data = pix.tobytes("jpeg")
                image_list.append(img_data)
            
            pdf_document.close()
            return image_list
        except Exception as mupdf_error:
           ""
            # st.warning(f"PyMuPDF conversion failed, trying alternative method: {str(mupdf_error)}")
            
        # Fall back to pdf2image if PyMuPDF fails
        images = convert_from_bytes(pdf_bytes, dpi=200)
        image_list = []
        
        for image in images:
            img_byte_arr = io.BytesIO()
            image = image.convert('RGB')  # Convert to RGB mode for JPEG
            image.save(img_byte_arr, format='JPEG', quality=90)
            image_list.append(img_byte_arr.getvalue())
            
        return image_list
    except PDFPageCountError:
        st.error("Failed to convert PDF to images. Please ensure the PDF is valid.")
        return None
    except Exception as e:
        st.error(f"PDF conversion error: {str(e)}")
        return None


def main():
    """Main function for the Streamlit app"""
    st.set_page_config(page_title="Precision Cylinder Analysis Tool", layout="wide")
    
    # Add logo and title
    col1, col2 = st.columns([1, 5])
    try:
        logo = Image.open("assets/logojsw.png")
        col1.image(logo, width=100)
    except:
        pass
    col2.title("Precision Cylinder Analysis Tool")
    
    st.markdown("### Upload a cylinder drawing for comprehensive parameter extraction")
    st.markdown("This enhanced tool provides detailed analysis of hydraulic/pneumatic cylinder drawings with improved accuracy.")
    
    # Add option to enable/disable image upscaling
    # enable_upscaling = st.checkbox("Enable image upscaling for better analysis (recommended)", value=True)
    enable_upscaling = True
    
    uploaded_file = st.file_uploader("Upload a cylinder drawing (PDF or image)", type=["pdf", "png", "jpg", "jpeg"])

    if uploaded_file:
        # Process the uploaded file
        image_data = process_uploaded_file(uploaded_file)
        
        # Skip upscaling if disabled
        if not enable_upscaling and image_data:
            # Re-process without upscaling
            file_bytes = uploaded_file.read()
            if uploaded_file.type == "application/pdf":
                images = convert_pdf_to_images(file_bytes, uploaded_file.name)
                if images and images[0]:
                    image_data = images[0]
            else:
                image = Image.open(io.BytesIO(file_bytes))
                img_byte_arr = io.BytesIO()
                image = image.convert('RGB')
                image.save(img_byte_arr, format='JPEG', quality=95)
                image_data = img_byte_arr.getvalue()
        
        if image_data:
            # Create columns for image and results
            col1, col2 = st.columns([1, 1])
            
            # Display the image
            with col1:
                st.image(image_data, caption="Uploaded Drawing", use_container_width=True)
            
            # Analyze the drawing and display results
            with col2:
                with st.spinner("Conducting detailed cylinder analysis..."):
                    results = analyze_engineering_drawing(image_data)
                    
                    st.markdown("### Extracted Parameters")
                    
                    # Create a DataFrame for better display
                    params = results["parameters"]
                    df_data = []
                    
                    # Use exactly the specified parameters in the exact sequence
                    parameter_list = [
                        "CYLINDER ACTION",
                        "BORE DIAMETER",
                        "ROD DIAMETER",
                        "STROKE LENGTH",
                        "CLOSE LENGTH",
                        "OPERATING PRESSURE",
                        "OPERATING TEMPERATURE",
                        "MOUNTING",
                        "ROD END",
                        "FLUID",
                        "DRAWING NUMBER",
                        "REVISION"
                    ]
                    
                    # Add all parameters to the data list in the exact sequence specified
                    for param in parameter_list:
                        value = params.get(param, "NA")
                        if value == "":
                            value = "NA"
                        df_data.append({"Parameter": param, "Value": value})
                    
                    # Create DataFrame
                    df = pd.DataFrame(df_data)
                    
                    # Display all results in a single table
                    st.table(df)
                    
                    # Add download button for results
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="Download Results as CSV",
                        data=csv,
                        file_name=f"cylinder_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                    )


if __name__ == "__main__":
    main()
