import streamlit as st
import base64
from PIL import Image
import io
import os
import json
import re
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from pyairtable import Api

# 🔒 CONTRASEÑA DE ACCESO
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔒 Restricted Access")
    st.info("Private application: enter password to continue.")
    clave = st.text_input("Password", type="password")
    if clave == "AhoraNorbury2026":
        st.session_state.autenticado = True
        st.rerun()
    elif clave:
        st.error("❌ Incorrect password")
    st.stop()

# CONFIGURACIÓN GENERAL
st.set_page_config(
    page_title="Stamp Assistant",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
html, body, .stApp {width:100%!important;max-width:100%!important;overflow-x:hidden!important;margin:0!important;padding:0.5rem!important;}
* {box-sizing:border-box!important;}
.stButton>button {width:100%!important;min-height:48px!important;}
img, .stDataFrame {max-width:100%!important;height:auto!important;}
[data-testid="stSidebar"] {display:none!important;}
</style>
""", unsafe_allow_html=True)

# 🔧 API SOLAR (UPSTAGE) — SOLO SE CAMBIÓ ESTA PARTE
UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
UPSTAGE_URL = "https://api.upstage.ai/v1/solar/chat/completions"
UPSTAGE_MODEL = "solar-vision-1.5-preview"

def llamar_solar(mensajes, temperatura=0.0, max_tokens=800):
    if not UPSTAGE_API_KEY:
        return "ERROR: UPSTAGE_API_KEY not configured in Secrets"
    cabeceras = {
        "Authorization": f"Bearer {UPSTAGE_API_KEY}",
        "Content-Type": "application/json"
    }
    datos = {
        "model": UPSTAGE_MODEL,
        "messages": mensajes,
        "temperature": temperatura,
        "max_tokens": max_tokens
    }
    try:
        respuesta = requests.post(UPSTAGE_URL, headers=cabeceras, json=datos, timeout=120)
        respuesta.raise_for_status()
        return respuesta.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"AI Error: {str(e)}"

# FUNCIÓN PARA ANALIZAR IMAGEN (USA SOLAR, MISMA LÓGICA DE ANTES)
def analizar_imagen_estampa(b64_imagen):
    if not UPSTAGE_API_KEY:
        return [{"country":"Unknown","year":"Unknown","face_value":"Unknown","condition":"Unknown","sale_price_gbp":0.0,"description":"Set UPSTAGE_API_KEY in Secrets"}]
    try:
        instruccion = """Analyze this stamp accurately. Return ONLY valid JSON array:
[{"country":"...","year":"...","face_value":"...","condition":"...","sale_price_gbp":NUMBER,"description":"..."}]
- All text MUST BE IN ENGLISH.
- Prices always in GBP (£).
- If unsure, write "Unknown" — do not invent data."""
        imagen_b64_url = f"data:image/jpeg;base64,{b64_imagen}"
        mensajes = [
            {"role":"user","content":[
                {"type":"text","text":instruccion},
                {"type":"image_url","image_url":{"url":imagen_b64_url}}
            ]}
        ]
        respuesta = llamar_solar(mensajes)
        texto_limpio = re.search(r'\[.*\]|\{.*\}', respuesta, re.DOTALL).group()
        return json.loads(texto_limpio)
    except Exception as e:
        return [{"country":"Unknown","year":"Unknown","face_value":"Unknown","condition":"Unknown","sale_price_gbp":0.0,"description":f"Error: {str(e)}"}]

# 🔧 EBAY UK — EXACTAMENTE IGUAL
EBAY_APP_ID = os.getenv("EBAY_APP_ID", "")
EBAY_CERT_ID = os.getenv("EBAY_CERT_ID", "")
EBAY_DEV_ID = os.getenv("EBAY_DEV_ID", "")
EBAY_TOKEN = os.getenv("EBAY_TOKEN", "")
EBAY_SITIO = "3"
CATEGORIA_EBAY = "260"
MONEDA_EBAY = "GBP"
CAMPO_PUBLICAR = "List on eBay"

def publicar_en_ebay(datos):
    if not all([EBAY_APP_ID, EBAY_CERT_ID, EBAY_DEV_ID, EBAY_TOKEN]):
        return False, "Missing eBay credentials"
    if not datos.get("sale_price_gbp") or datos.get("sale_price_gbp") <= 0:
        return False, "Invalid GBP price"
    url = "https://api.ebay.com/ws/api.dll"
    cabeceras = {
        "X-EBAY-API-CALL-NAME": "AddFixedPriceItem",
        "X-EBAY-API-APP-NAME": EBAY_APP_ID,
        "X-EBAY-API-DEV-NAME": EBAY_DEV_ID,
        "X-EBAY-API-CERT-NAME": EBAY_CERT_ID,
        "X-EBAY-API-SITEID": EBAY_SITIO,
        "Authorization": f"Bearer {EBAY_TOKEN}",
        "Content-Type": "text/xml"
    }
    titulo = f"Stamp {datos['country']} {datos.get('year','')} - {datos.get('condition','')}"[:80]
    descripcion = f"""Genuine original stamp.
Country: {datos['country']}
Year: {datos.get('year','Not specified')}
Face value: {datos.get('face_value','Not specified')}
Condition: {datos.get('condition','Not specified')}
Details: {datos.get('description','No additional details')}
Fast secure shipping from United Kingdom."""
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <AddFixedPriceItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
        <RequesterCredentials><eBayAuthToken>{EBAY_TOKEN}</eBayAuthToken></RequesterCredentials>
        <Item>
            <Title>{titulo}</Title>
            <Description>{descripcion}</Description>
            <Category>{CATEGORIA_EBAY}</Category>
            <StartPrice currencyID="{MONEDA_EBAY}">{datos['sale_price_gbp']}</StartPrice>
            <Quantity>1</Quantity><ListingDuration>GTC</ListingDuration>
            <Country>GB</Country><Currency>{MONEDA_EBAY}</Currency><Location>United Kingdom</Location>
            <ReturnPolicy><ReturnsAcceptedOption>ReturnsAccepted</ReturnsAcceptedOption><RefundOption>MoneyBack</RefundOption><ReturnsWithinOption>Days_30</ReturnsWithinOption><ShippingCostPaidByOption>Buyer</ShippingCostPaidByOption></ReturnPolicy>
        </Item>
    </AddFixedPriceItemRequest>"""
    try:
        resp = requests.post(url, data=xml.encode("utf-8"), headers=cabeceras, timeout=60)
        raiz = ET.fromstring(resp.text)
        id_ok = raiz.find(".//ItemID")
        return (True, id_ok.text) if id_ok is not None else (False, "eBay error")
    except Exception as e:
        return False, str(e)

# AIRTABLE — EXACTAMENTE IGUAL
CONECTADO_AIRTABLE = False
try:
    api_airtable = Api(os.getenv("AIRTABLE_API_KEY"))
    tabla_airtable = api_airtable.table(os.getenv("AIRTABLE_BASE_ID"), os.getenv("AIRTABLE_TABLA"))
    CONECTADO_AIRTABLE = True
except Exception:
    pass

def publicar_desde_airtable():
    if not CONECTADO_AIRTABLE: st.warning("No Airtable connection"); return
    if not all([EBAY_APP_ID, EBAY_TOKEN]): st.warning("Add eBay keys first"); return
    st.info("Checking records...")
    regs = tabla_airtable.all(); pub=0; skip=0
    for r in regs:
        f = r["fields"]
        if not bool(f.get(CAMPO_PUBLICAR,False)): skip+=1; continue
        d = {"country":f.get("country","Unknown"),"year":f.get("year",""),"face_value":f.get("Face_value",""),"condition":f.get("condition",""),"sale_price_gbp":float(f.get("sale_price_gbp",0))or0,"description":f.get("description","")}
        ok,res = publicar_en_ebay(d)
        if ok: st.success(f"✅ Published: {res}"); tabla_airtable.update(r["id"],{CAMPO_PUBLICAR:False,"eBay ID":res}); pub+=1
        else: st.warning(f"Record {r['id']}: {res}")
    st.info(f"Checked {len(regs)} | Published {pub} | Skipped {skip}")

def cargar_base():
    if not CONECTADO_AIRTABLE: return pd.DataFrame(columns=["id","saved_date","country","year","Face_value","condition","sale_price_gbp","description","List on eBay","image_b64"])
    return pd.DataFrame([{"id":f.get("id"),"saved_date":f.get("saved_date"),"country":f.get("country"),"year":f.get("year"),"Face_value":f.get("Face_value"),"condition":f.get("condition"),"sale_price_gbp":f.get("sale_price_gbp"),"description":f.get("description"),"List on eBay":bool(f.get("List on eBay",False)),"image_b64":f.get("image_b64")} for f in [x["fields"] for x in tabla_airtable.all()]])

def guardar(regs):
    if not CONECTADO_AIRTABLE: st.warning("Not saved"); return
    ok=0
    for r in regs:
        tabla_airtable.create({
            "saved_date":datetime.now().isoformat(timespec="seconds")+"Z",
            "country":str(r.get("country","Unknown")),"year":str(r.get("year","Unknown")),
            "Face_value":str(r.get("face_value","Unknown")),"condition":str(r.get("condition","Unknown")),
            "sale_price_gbp":float(r.get("sale_price_gbp",0)),"description":str(r.get("description","No details")),
            "List on eBay":bool(r.get("publicar_en_ebay",False)),"image_b64":str(r.get("image_b64",""))
        })
        ok+=1
    st.success(f"Saved: {ok}")

# INTERFAZ — EXACTAMENTE IGUAL
st.title("📮 Stamp Assistant")
if CONECTADO_AIRTABLE: st.success("Connected to Airtable")

if st.button("🔍 Check & publish marked records"):
    publicar_desde_airtable()

st.header("📤 Add stamp")
modo = st.radio("Upload from:", ["📂 Gallery", "📸 Camera"])
archivo = None
if modo == "📂 Gallery":
    archivo = st.file_uploader("Image", type=["jpg","jpeg","png"])
else:
    if "cam" not in st.session_state: st.session_state.cam=False
    if not st.session_state.cam:
        if st.button("📸 Open camera"): st.session_state.cam=True; st.rerun()
    else:
        foto = st.camera_input("Take photo")
        if foto: archivo = foto
        if st.button("❌ Close camera"): st.session_state.cam=False; st.rerun()

if archivo:
    img = Image.open(archivo); st.image(img, width=300)
    buf = io.BytesIO(); img.convert("RGB").resize((350,280), Image.Resampling.BILINEAR).save(buf, format="JPEG", quality=70)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    with st.spinner("Analyzing stamp with SOLAR..."):
        datos = analizar_imagen_estampa(b64)[0]

    st.subheader("📋 Stamp details")
    pais = st.text_input("Country", value=datos.get("country","Unknown"))
    anio = st.text_input("Year", value=datos.get("year","Unknown"))
    valor = st.text_input("Face value", value=datos.get("face_value","Unknown"))
    estado = st.text_input("Condition", value=datos.get("condition","Unknown"))
    precio = st.number_input("Price (£ GBP)", min_value=0.0, step=0.01, format="%.2f", value=float(datos.get("sale_price_gbp",0)))
    desc = st.text_area("Description", value=datos.get("description",""))
    publicar = st.checkbox("List on eBay", value=bool(datos.get("publicar_en_ebay",False)))

    if st.button("💾 Save"):
        guardar([{
            "country":pais,"year":anio,"face_value":valor,"condition":estado,
            "sale_price_gbp":precio,"description":desc,"publicar_en_ebay":publicar,"image_b64":b64
        }])

st.header("📚 Saved stamps")
if st.button("Show / Hide list"): st.session_state.mostrar = not st.session_state.get("mostrar",False)
if st.session_state.get("mostrar",False):
    df = cargar_base()
    if not df.empty:
        df["sale_price_gbp"] = df["sale_price_gbp"].apply(lambda x: f"£{x:.2f}")
        df["List on eBay"] = df["List on eBay"].apply(lambda x: "✅ Yes" if x else "❌ No")
        st.dataframe(df.drop(columns=["image_b64"]), hide_index=True)
    else:
        st.info("No stamps saved yet")

st.download_button("📥 Download CSV",
    data=cargar_base().drop(columns=["image_b64"]).to_csv(index=False).encode("utf-8"),
    file_name=f"stamps_{datetime.now().strftime('%Y%m%d')}.csv")