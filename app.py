from flask import Flask, render_template, request, redirect, url_for, session, send_file
import os
import re
from docx import Document
import pdfplumber
from openai import OpenAI

app = Flask(__name__)
app.secret_key = "clave_super_secreta_123"

# 🔐 LOGIN
USUARIO = os.getenv("USER", "Johan")
PASSWORD = os.getenv("PASS", "1234")

# 🤖 IA CONFIG
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
base_url=os.getenv("OPENAI_BASE_URL")
)

# 🔐 LOGIN ROUTE
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form.get('usuario')
        password = request.form.get('password')

        if user == USUARIO and password == PASSWORD:
            session['login'] = True
            return redirect(url_for('index'))
        else:
            error = "Usuario o contraseña incorrectos"

    return render_template('login.html', error=error)

# 🔒 PROTEGER RUTAS
@app.before_request
def proteger():
    rutas_libres = ['login', 'static']
    if request.endpoint not in rutas_libres:
        if not session.get('login'):
            return redirect(url_for('login'))

# 🚪 LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 🏠 HOME
@app.route('/')
def index():
    return render_template('index.html')

# 📄 EXTRAER TEXTO PDF
def extraer_texto_pdf(file):
    texto = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto += page.extract_text() or ""
    return texto

# 🧠 EXTRAER SECCIONES IA
def extraer_seccion(contenido, nombre):
    try:
        patron = rf"---{nombre}---(.*?)(?=---|$)"
        match = re.search(patron, contenido, re.DOTALL)
        if match:
            return match.group(1).strip()
        return "No disponible"
    except:
        return "No disponible"

# 📄 CONVERTIR
@app.route('/convert', methods=['POST'])
def convert():
    archivo = request.files['file']
    usar_ia = request.form.get("usar_ia") == "on"
    usar_portada = request.form.get("usar_portada") == "on"
    instruccion = request.form.get("instruccion")

    tema = request.form.get("tema")
    nombre = request.form.get("nombre")
    materia = request.form.get("materia")
    profesor = request.form.get("profesor")
    colegio = request.form.get("colegio")

    texto = ""

    if archivo.filename.endswith(".pdf"):
        texto = extraer_texto_pdf(archivo)
    else:
        texto = archivo.read().decode("utf-8", errors="ignore")

    contenido = texto

    if usar_ia and texto.strip():
        try:
            prompt = f"""
Analiza el siguiente documento.

Responde EXACTAMENTE con este formato:

---INTENCION---
...
---PARTES---
...
---ANTES---
...
---DESPUES---
...
---CAMBIOS---
...
---SUGERENCIAS---
...

NO agregues texto fuera de las secciones.

Instrucciones del usuario: {instruccion}

Texto:
{texto}
"""

            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": "Eres un experto en redacción académica y normas APA 7."},
                    {"role": "user", "content": prompt}
                ]
            )

            contenido = response.choices[0].message.content

        except Exception as e:
            contenido = texto

    analisis = {
        "intencion": extraer_seccion(contenido, "INTENCION"),
        "partes": extraer_seccion(contenido, "PARTES"),
        "antes": extraer_seccion(contenido, "ANTES"),
        "despues": extraer_seccion(contenido, "DESPUES"),
        "cambios": extraer_seccion(contenido, "CAMBIOS"),
        "sugerencias": extraer_seccion(contenido, "SUGERENCIAS")
    }

    # 📄 GENERAR WORD
    doc = Document()

    if usar_portada:
        doc.add_paragraph(tema)
        doc.add_paragraph(nombre)
        doc.add_paragraph(materia)
        doc.add_paragraph(profesor)
        doc.add_paragraph(colegio)
        doc.add_page_break()

    doc.add_paragraph(analisis["despues"])

    nombre_archivo = archivo.filename.rsplit(".", 1)[0] + "_APA.docx"
    ruta = os.path.join("output", nombre_archivo)

    os.makedirs("output", exist_ok=True)
    doc.save(ruta)

    return render_template("preview.html", analisis=analisis, archivo=nombre_archivo)

# ⬇ DESCARGA
@app.route('/download/<nombre>')
def download(nombre):
    return send_file(os.path.join("output", nombre), as_attachment=True)

# 🚀 RENDER
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
