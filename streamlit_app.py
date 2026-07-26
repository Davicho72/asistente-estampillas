import streamlit as st
import base64
from PIL import Image
import io
import os
import json
import re
import time
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from pyairtable import Api

# 🔒 CONTRASEÑA DE ACCESO
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔒 Acceso restringido")
    st.info("Aplicación privada: ingresa la contraseña para continuar.")
    clave = st.text_input("Contraseña", type="password")
    if clave == "AhoraNorbury2026":
        st.session_state.autenticado = True
        st.rerun()
    elif clave:
        st.error("❌ Contraseña incorrecta")
    st.stop()

# 🔧 LECTURA DE CLAVES
EBAY_APP_ID = st.secrets.get("EBAY_CLIENT_ID", "")
EBAY_CERT_ID = st.secrets.get("EBAY_CLIENT_SECRET", "")
EBAY_DEV_ID = st.secrets.get("EBAY_DEV_ID", "")
EBAY_REFRESH_TOKEN = st.secrets.get("EBAY_REFRESH_TOKEN", "")

# CONFIGURACIÓN GENERAL
st.set_page_config(
    page_title="Asistente Estampillas",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "Asistente personal para tu colección de estampillas"}
)

st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests; default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https:;">

<style>
html, body, .stApp {width:100%!important;max-width:100%!important;overflow-x:hidden!important;margin:0!important;padding:0.5rem!important;}
* {box-sizing:border-box!important;}
.stButton>button {width:100%!important;min-height:48px!important;font-size:16px!important;margin:0.4rem 0!important;}
.stFileUploader, .stCameraInput, .stTextArea, .stCheckbox {width:100%!important;font-size:15px!important;}
h1 {font-size:22px!important;}h2 {font-size:20px!important;}h3 {font-size:18px!important;}
img, .stDataFrame, .stTable {max-width:100%!important;height:auto!important;}
[data-testid="stSidebar"] {display:none!important;}
</style>
""", unsafe_allow_html=True)

# 🔧 API MISTRAL
MISTRAL_API_KEY = st.secrets.get("MISTRAL_API_KEY") or os.getenv("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "pixtral-12b-2409"

def llamar_mistral(mensajes, temperatura=0.0, max_tokens=800):
    if not MISTRAL_API_KEY:
        return "ERROR: MISTRAL_API_KEY no configurada"
    cabeceras = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    mensajes_formateados = []
    for m in mensajes:
        mensajes_formateados.append({"role": m["role"], "content": [{"type": "text", "text": m["content"]}] if isinstance(m["content"], str) else m["content"]})
    datos = {"model": MISTRAL_MODEL, "messages": mensajes_formateados, "temperature": temperatura, "max_tokens": max_tokens}
    try:
        resp = requests.post(MISTRAL_URL, headers=cabeceras, json=datos, timeout=90)
        return resp.json()["choices"][0]["message"]["content"] if resp.ok else f"ERROR API: {resp.status_code}"
    except Exception as e:
        return f"Error conexión: {str(e)}"

# 🔧 EBAY
EBAY_SITIO = "3"
CATEGORIA_EBAY = "260"
MONEDA_EBAY = "GBP"
CAMPO_PUBLICAR = "Publicar en eBay"

def obtener_token_ebay():
    if not all([EBAY_APP_ID, EBAY_CERT_ID, EBAY_REFRESH_TOKEN]): return None
    auth_b64 = base64.b64encode(f"{EBAY_APP_ID}:{EBAY_CERT_ID}".encode()).decode()
    cabeceras = {"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"}
    datos = {"grant_type": "refresh_token", "refresh_token": EBAY_REFRESH_TOKEN, "scope": "https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.item"}
    try:
        resp = requests.post("https://api.ebay.com/identity/v1/oauth2/token", headers=cabeceras, data=datos, timeout=30)
        return resp.json()["access_token"] if resp.ok else None
    except: return None

def publicar_en_ebay(datos):
    tok = obtener_token_ebay()
    if not tok: return False, "Sin token de eBay"
    try:
        precio = float(re.sub(r"[^0-9.]", "", str(datos.get("sale_price_gbp", "0.5")).strip().replace(",", ".")))
    except: precio = 0.5
    if precio <= 0: return False, "Precio inválido"
    titulo = f"Estampilla {datos['country']} {datos['year'] or ''} - {datos['condition']}"[:80]
    desc = f"""País: {datos['country']}
Año: {datos['year'] or 'Sin dato'}
Valor facial: {datos['face_value'] or 'Sin dato'}
Estado: {datos['condition'] or 'Sin dato'}
Detalles: {datos['description'] or 'Sin detalles'}
Envío desde Reino Unido."""
    xml = f"""<?xml version="1.0"?>
    <AddFixedPriceItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
        <RequesterCredentials><eBayAuthToken>{tok}</eBayAuthToken></RequesterCredentials>
        <Item><Title>{titulo}</Title><Description>{desc}</Description><Category>{CATEGORIA_EBAY}</Category>
        <StartPrice currencyID="{MONEDA_EBAY}">{precio}</StartPrice><Quantity>1</Quantity><ListingDuration>GTC</ListingDuration>
        <Country>GB</Country><Currency>{MONEDA_EBAY}</Currency><Location>Reino Unido</Location>
        <ReturnPolicy><ReturnsAcceptedOption>ReturnsAccepted</ReturnsAcceptedOption><RefundOption>MoneyBack</RefundOption>
        <ReturnsWithinOption>Days_30</ReturnsWithinOption><ShippingCostPaidByOption>Buyer</ShippingCostPaidByOption></ReturnPolicy></Item>
    </AddFixedPriceItemRequest>"""
    cab = {"X-EBAY-API-CALL-NAME":"AddFixedPriceItem","X-EBAY-API-APP-NAME":EBAY_APP_ID,"X-EBAY-API-DEV-NAME":EBAY_DEV_ID,
           "X-EBAY-API-CERT-NAME":EBAY_CERT_ID,"X-EBAY-API-SITEID":EBAY_SITIO,"X-EBAY-API-COMPATIBILITY-LEVEL":"967",
           "Authorization":f"Bearer {tok}","Content-Type":"text/xml"}
    try:
        r = requests.post("https://api.ebay.com/ws/api.dll", data=xml.encode("utf-8"), headers=cab, timeout=60)
        if r.status_code!=200: return False, f"Error {r.status_code}"
        ns={"ebay":"urn:ebay:apis:eBLBaseComponents"}
        idv=ET.fromstring(r.text).find("ebay:ItemID",ns)
        return (True,f"✅ Publicado | ID: {idv.text}") if idv is not None else (True,"✅ Publicado")
    except Exception as e: return False, str(e)

# 🔧 AIRTABLE
CONECTADO=False
try:
    api=Api(st.secrets.get("AIRTABLE_API_KEY"))
    tabla=api.table(st.secrets.get("AIRTABLE_BASE_ID"), st.secrets.get("AIRTABLE_TABLA"))
    CONECTADO=True
except: pass

def cargar_base():
    if not CONECTADO: return pd.DataFrame(columns=["id","saved_date","country","year","Face_value","condition","sale_price_gbp","description","Publicar en eBay","ID eBay","image_b64"])
    try:
        return pd.DataFrame([{**{"id":f.get("id")},**f} for f in [r["fields"] for r in tabla.all()]])
    except: return pd.DataFrame()

def guardar_seleccionadas(lista):
    if not CONECTADO or not lista: return
    guardados=0
    for r in lista:
        fecha=datetime.now().isoformat(timespec="seconds")+"Z"
        try: precio=float(re.sub(r"[^0-9.]", "", str(r.get("sale_price_gbp","0.5")).strip().replace(",",".")))
        except: precio=0.5
        anio=str(r.get("year","")).strip() if r.get("year") not in (None,"","-") else ""
        reg=tabla.create({
            "saved_date":fecha,"country":r["country"],"year":anio,"Face_value":r["face_value"],
            "condition":r["condition"],"sale_price_gbp":precio,"description":r["description"],
            "Publicar en eBay":False,"image_b64":r["image_b64"]
        }, typecast=True)
        img_b64=r.get("image_b64")
        if img_b64:
            try: tabla.upload_attachment(reg["id"],"Imagen","estampilla.jpg",base64.b64decode(img_b64),"image/jpeg")
            except Exception as e: st.warning(f"Imagen: {str(e)}")
        guardados+=1
    st.success(f"Guardadas: {guardados}")

def publicar_seleccionadas(lista):
    if not lista: return
    pub=0
    for r in lista:
        anio=str(r.get("year","")).strip() if r.get("year") not in (None,"","-") else ""
        datos={"country":r["country"],"year":anio,"face_value":r["face_value"],"condition":r["condition"],"sale_price_gbp":r["sale_price_gbp"],"description":r["description"]}
        ok,res=publicar_en_ebay(datos)
        if ok:
            st.success(f"✅ {res}")
            if CONECTADO:
                fecha=datetime.now().isoformat(timespec="seconds")+"Z"
                try: precio=float(re.sub(r"[^0-9.]", "", str(r.get("sale_price_gbp","0.5")).strip().replace(",",".")))
                except: precio=0.5
                tabla.create({"saved_date":fecha,"country":datos["country"],"year":anio,"Face_value":datos["face_value"],
                              "condition":datos["condition"],"sale_price_gbp":precio,"description":datos["description"],
                              "Publicar en eBay":False,"ID eBay":res,"image_b64":r["image_b64"]}, typecast=True)
            pub+=1
        else: st.warning(f"No publicado: {res}")
    st.info(f"Publicadas: {pub}")

def reducir_imagen(img):
    if img.mode in ("RGBA","P"):
        fondo=Image.new("RGB",img.size,(255,255,255))
        fondo.paste(img,mask=img.split()[3] if img.mode=="RGBA" else None)
        img=fondo
    elif img.mode!="RGB": img=img.convert("RGB")
    img=img.resize((350,int(img.height*350/img.width)),Image.Resampling.BILINEAR)
    b=io.BytesIO();img.save(b,"JPEG",quality=70);return base64.b64encode(b.getvalue()).decode()

def extraer_json(texto):
    m=re.search(r'\[.*\]|\{.*\}',texto,re.DOTALL);return json.loads(m.group()) if m else None

def analizar_estampa(img,b64):
    ins="Devuelve JSON: [{country,year,face_value,condition,sale_price_gbp(numero ≥0.5),description}]."
    for _ in range(3):
        try:
            time.sleep(1.5)
            res=llamar_mistral([{"role":"user","content":[{"type":"text","text":ins},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}])
            d=extraer_json(res);return d if isinstance(d,list) else [d]
        except: time.sleep(2)
    return [{"country":"Desconocido","year":"-","face_value":"-","condition":"-","sale_price_gbp":0.50,"description":"Error análisis"}]

# 🖥️ INTERFAZ FINAL
st.title("📮 Asistente de Estampillas")
if CONECTADO: st.success("Conectado a Airtable")
df=cargar_base()
for k in ["activar_camara","ver_catalogo"]:
    if k not in st.session_state: st.session_state[k]=False

st.header("🚀 Publicar desde Airtable")
if st.button("🔍 Revisar y publicar"):
    if not CONECTADO: st.warning("Sin conexión Airtable")
    elif not EBAY_APP_ID: st.warning("Falta clave eBay")
    else:
        regs=tabla.all();pub=0;err=[]
        for r in regs:
            if not bool(r["fields"].get(CAMPO_PUBLICAR)): continue
            d={"country":r["fields"].get("country",""),"year":r["fields"].get("year",""),"face_value":r["fields"].get("Face_value",""),
               "condition":r["fields"].get("condition",""),"sale_price_gbp":r["fields"].get("sale_price_gbp","0.5"),"description":r["fields"].get("description","")}
            ok,res=publicar_en_ebay(d)
            if ok: st.success(f"✅ {res}");tabla.update(r["id"],{CAMPO_PUBLICAR:False,"ID eBay":res});pub+=1
            else: err.append(f"{r['id']}: {res}")
        st.info(f"Total:{len(regs)} | Publicadas:{pub}")
        for e in err: st.warning(e)

st.header("📤 Cargar o tomar estampillas")
modo = st.radio("Elige cómo subir:", ["📂 Galería", "📸 Tomar foto"])
archivos = []
if modo == "📂 Galería":
    st.session_state.activar_camara = False
    archivos = st.file_uploader("Selecciona imágenes", type=["jpg","jpeg","png"], accept_multiple_files=True)
else:
    if not st.session_state.activar_camara:
        if st.button("📸 Abrir cámara"):
            st.session_state.activar_camara = True
            st.rerun()
    else:
        foto = st.camera_input("Toma la estampilla")
        if foto:
            archivos.append(foto)
        if st.button("❌ Cerrar cámara"):
            st.session_state.activar_camara = False
            st.rerun()

if archivos:
    guardar_lista=[];pub_lista=[]
    for i,a in enumerate(archivos,1):
        st.subheader(f"📷 Imagen {i}")
        img=Image.open(a);st.image(img,width=300)
        with st.spinner("Analizando..."):
            b64=reducir_imagen(img);datos=analizar_estampa(img,b64)
            st.success(f"{len(datos)} detectadas")
            for n,d in enumerate(datos,1):
                pais=d.get("country","Desconocido");anio=d.get("year","-");val=d.get("face_value","-")
                est=d.get("condition","-");prec=d.get("sale_price_gbp",0.5);desc=d.get("description","")
                try: prec=float(re.sub(r"[^0-9.]","",str(prec).strip().replace(",",".")))
                except: prec=0.5
                # ✅ VUELTO A MOSTRAR VERTICAL, TAL COMO ESTABA
                st.write(f"**País:** {pais}")
                st.write(f"**Año:** {anio}")
                st.write(f"**Valor facial:** {val}")
                st.write(f"**Estado:** {est}")
                prec=st.number_input("Precio GBP",value=max(prec,0.5),min_value=0.5,step=0.05,format="%.2f",key=f"p_{i}_{n}")
                desc=st.text_area("Descripción",desc,key=f"d_{i}_{n}")
                g=st.checkbox("Guardar",True,key=f"g_{i}_{n}")
                p=st.checkbox("Marcar eBay",False,key=f"pub_{i}_{n}")
                reg={"country":pais,"year":anio,"face_value":val,"condition":est,"sale_price_gbp":prec,"description":desc,"image_b64":b64}
                if g: guardar_lista.append(reg)
                if p: pub_lista.append(reg)
    c1,c2=st.columns(2)
    with c1:
        if st.button("📥 Guardar seleccionadas"): guardar_seleccionadas(guardar_lista);df=cargar_base()
    with c2:
        if st.button("📤 Publicar seleccionadas"): publicar_seleccionadas(pub_lista);df=cargar_base()

st.header("📚 Catálogo")
if st.button("Ver/Ocultar"): st.session_state.ver_catalogo=not st.session_state.ver_catalogo
if st.session_state.ver_catalogo and not df.empty:
    m=df.copy()
    m["sale_price_gbp"]=m["sale_price_gbp"].apply(lambda x: f"£{x:.2f} GBP")
    m["Publicar en eBay"]=m["Publicar en eBay"].apply(lambda x:"✅ Sí" if x else "❌ No")
    m["Imagen"]=m["image_b64"].apply(lambda x:f"data:image/jpeg;base64,{x}" if pd.notna(x) else None)
    st.dataframe(m[["id","saved_date","country","year","Face_value","condition","sale_price_gbp","Publicar en eBay","ID eBay","description","Imagen"]],
        column_config={"Imagen":st.column_config.ImageColumn(width="small")},hide_index=True)

st.header("🌍 Buscar referencias")
if st.button("Buscar casas de venta"):
    with st.spinner("Consultando..."):
        res=llamar_mistral([{"role":"user","content":"Lista casas de subasta y tiendas serias de estampillas con sitio web y contacto, actualizado 2026."}],0.1,1200)
        st.markdown(res)

st.download_button("📥 Descargar CSV",df.drop(columns=["image_b64"]).to_csv(index=False).encode("utf-8"),file_name=f"catalogo_{datetime.now().strftime('%Y%m%d')}.csv")