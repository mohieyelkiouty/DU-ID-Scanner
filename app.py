import streamlit as st
import cv2
import numpy as np
import easyocr
import base64
from PIL import Image

# --- convert local background image to base64 ---
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except:
        return None

# --- Page Configuration ---
st.set_page_config(page_title="Delta University | ID Scanner", page_icon="🎓", layout="centered")

# --- Enhanced CSS Styling ---
bg_base64 = get_base64_image("assets/background.jpg")
if bg_base64:
    st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpg;base64,{bg_base64}");
            background-attachment: fixed; background-size: cover; background-position: center;
        }}
        .stApp::before {{
            content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background-color: rgba(0, 0, 0, 0.6); z-index: -1;
        }}
        h1, h2, h3, p, span, label, .stMarkdown {{ 
            color: #FFFFFF !important; font-weight: bold !important; 
        }}
        .stButton>button {{
            background-color: #C5A059 !important; color: white !important;
            border-radius: 15px !important; border: none !important; width: 100%;
        }}
        </style>
        """, unsafe_allow_html=True)

# --- Header Section ---
col_logo, col_head = st.columns([1, 4]) 
with col_logo:
    try: st.image("assets/Delta Univ.png", width=100)
    except: st.title("🎓")
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
    return thresh

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr()

# --- Template Matching & Alignment ---
def align_single_template_scene(scene_img, template_img, min_matches=8):
    gray_scene = cv2.cvtColor(scene_img, cv2.COLOR_BGR2GRAY)
    gray_temp  = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)

    sift = cv2.SIFT_create()
    kp_temp, des_temp   = sift.detectAndCompute(gray_temp, None)
    kp_scene, des_scene = sift.detectAndCompute(gray_scene, None)

    if des_scene is None or des_temp is None:
        return None

    bf = cv2.BFMatcher()
    matches = bf.knnMatch(des_temp, des_scene, k=2)

    good = []
    for m, n in matches:
        if m.distance < 0.75 * n.distance:
            good.append(m)

    if len(good) < min_matches:
        return None

    src_pts = np.float32([kp_temp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp_scene[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    M, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
    if M is None:
        return None

    h, w = gray_temp.shape
    aligned = cv2.warpPerspective(scene_img, M, (w, h))
    return aligned

# --- Main Logic ---
uploaded_file = st.file_uploader("Upload ID Card", type=['jpg', 'jpeg', 'png'])

if uploaded_file is not None:
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    
    with st.spinner('Processing Card...'):
        template = cv2.imread("assets/template.png") 
        
        if template is None:
            st.error("Template file not found in assets folder!")
            st.stop()

        crop = align_single_template_scene(img, template)
        
        if crop is not None:
            final_for_ocr = cv2.resize(crop, (800, 500))
            
            zones = {
                "Student Name": final_for_ocr[140:280, 10:640], 
                "ID Number": final_for_ocr[330:400, 175:380] 
            }

            st.markdown("### 📋 Extracted Results")
            cols = st.columns(2)
            
            for idx, (label, zone_img) in enumerate(zones.items()):
                cleaned = final_balanced_clean(zone_img)
                results = reader.readtext(cleaned, detail=0)
                text = " ".join(results).strip()
                
                if "Name" in label:
                    text = ''.join(filter(lambda x: x.isalpha() or x.isspace(), text))
                else:
                    text = ''.join(filter(str.isdigit, text))

                with cols[idx % 2]:
                    st.write(f"**{label}:**")
                    if text:
                        st.success(text)
                    else:
                        st.warning("Not detected")
            
            with st.expander("See Aligned Card"):
                st.image(cv2.cvtColor(final_for_ocr, cv2.COLOR_BGR2RGB))
        else:
            st.error("Card detection failed. Please ensure the card is clear and flat.")
