import streamlit as st
import cv2
import numpy as np
import easyocr
import base64
from PIL import Image

# 1. Function to convert local background image to base64
def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# 2. Page Configuration
st.set_page_config(page_title="Delta University | ID Scanner", page_icon="🎓", layout="centered")

# 3. Enhanced CSS Styling
try:
    bg_base64 = get_base64_image("background.jpg")
    st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpg;base64,{bg_base64}");
            background-attachment: fixed;
            background-size: cover;
            background-position: center;
        }}
        
        /* Darker overlay to make White Text pop */
        .stApp::before {{
            content: "";
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background-color: rgba(0, 0, 0, 0.5); /* Black transparent layer */
            z-index: -1;
        }}

        /* Make ALL text WHITE */
        h1, h2, h3, p, span, label, .stMarkdown {{ 
            color: #FFFFFF !important; 
            font-weight: bold !important; 
        }}

        /* Gold Button Style */
        .stButton>button {{
            background-color: #C5A059 !important;
            color: white !important;
            border-radius: 15px !important;
            border: none !important;
            font-weight: bold !important;
            width: 100%;
        }}

        /* Specific style for file uploader text */
        .st-emotion-cache-1ae8k9u {{ color: white !important; }}
        </style>
        """, unsafe_allow_html=True)
except:
    st.warning("Please ensure 'background.jpg' is in the project folder.")

# --- Header Section ---
col_logo, col_head = st.columns([2, 4]) 

with col_logo:
    try:
        st.image("Delta Univ.png", width=120)
    except:
        st.write("🎓")

with col_head:
    st.title("Delta University")
    st.write("Automated ID Recognition System")

st.divider()

# --- Functions ---
def final_balanced_clean(image_crop):
    if len(image_crop.shape) == 3:
        gray = cv2.cvtColor(image_crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_crop
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    contrast = clahe.apply(gray)
    blurred = cv2.GaussianBlur(contrast, (3, 3), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((2,2), np.uint8)
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    return closed

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr()

# --- Main logic ---
uploaded_file = st.file_uploader("Upload ID Card", type=['jpg', 'jpeg', 'png'])

if uploaded_file is not None:
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    
    with st.spinner('Processing...'):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 30, 150)
        contours, _ = cv2.findContours(cv2.dilate(edged, np.ones((5,5))), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        if len(contours) > 0:
            x, y, w, h = cv2.boundingRect(contours[0])
            crop = img[y + int(h * 0.22) : y + int(h * 0.90), x + int(w * 0.02) : x + int(w * 0.98)]
            final_for_ocr = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (800, 500))
            
            zones = {
                "Name": final_for_ocr[80:250, 10:640], 
                "ID_Number": final_for_ocr[330:430, 175:380] 
            }

            st.markdown("### Extracted Results")
            for label, zone_img in zones.items():
                cleaned = final_balanced_clean(zone_img)
                text = " ".join(reader.readtext(cleaned, detail=0)).strip()
                
                if label == "Name":
                    text = ''.join(filter(lambda x: x.isalpha() or x.isspace(), text))
                else:
                    text = ''.join(filter(str.isdigit, text))
                
                st.write(f"**{label}:**")
                st.success(text if text else "Not found")
        else:
            st.error("Card detection failed.")