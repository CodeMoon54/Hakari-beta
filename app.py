import os
import gradio as gr
from google import genai
from google.genai import types
import random
import secrets
import re
from datetime import datetime, date
import pickle

# Configuración
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# Sistema de Memoria Afectiva
class MemoriaAfectiva:
    def __init__(self):
        self.memoria_usuarios = {}
    
    def registrar_interaccion(self, usuario_email, mensaje, emocion):
        if usuario_email not in self.memoria_usuarios:
            self.memoria_usuarios[usuario_email] = {
                'interacciones': [],
                'emociones_registradas': {},
                'confianza': 30
            }
        
        self.memoria_usuarios[usuario_email]['interacciones'].append({
            'timestamp': datetime.now().isoformat(),
            'mensaje': mensaje[:50],
            'emocion': emocion
        })
        
        if emocion in self.memoria_usuarios[usuario_email]['emociones_registradas']:
            self.memoria_usuarios[usuario_email]['emociones_registradas'][emocion] += 1
        else:
            self.memoria_usuarios[usuario_email]['emociones_registradas'][emocion] = 1

memoria_afectiva = MemoriaAfectiva()

# Personalidad de Hakari
class PersonalidadHakari:
    def __init__(self):
        self.estado_actual = "tímida"
        self.estados = {
            "tímida": {"emoji": "🌙", "color": "#ec4899", "desc": "No está segura de hablar"},
            "irónica": {"emoji": "😏", "color": "#f472b6", "desc": "Humor negro activado"},
            "nostálgica": {"emoji": "📚", "color": "#d946ef", "desc": "Recordando cosas"},
            "defensiva": {"emoji": "🛡️", "color": "#f43f5e", "desc": "Protegiendo su espacio"},
            "curiosa": {"emoji": "🔍", "color": "#a855f7", "desc": "Interesada a pesar de todo"}
        }
        self.contador = 0
    
    def calcular_edad(self):
        hoy = date.today()
        cumple = date(2007, 5, 1)
        return hoy.year - cumple.year - ((hoy.month, hoy.day) < (cumple.month, cumple.day))
    
    def actualizar_estado(self, mensaje):
        self.contador += 1
        mensaje = mensaje.lower()
        
        if any(palabra in mensaje for palabra in ['por qué', 'explica', 'razón']):
            self.estado_actual = "defensiva"
        elif any(palabra in mensaje for palabra in ['recuerd', 'antes', 'cuando']):
            self.estado_actual = "nostálgica"
        elif any(palabra in mensaje for palabra in ['interesante', 'cuéntame', 'sabes']):
            self.estado_actual = "curiosa"
        elif random.random() < 0.3:
            self.estado_actual = random.choice(list(self.estados.keys()))
        
        return self.estado_actual
    
    def generar_contradiccion(self, tema):
        contradicciones = [
            f"No quiero hablar de {tema}... aunque bueno, tal vez un poco",
            f"Odio cuando sacan el tema de {tema}, pero ya que estamos...",
            f"{tema} me da igual, en serio. Aunque si insistes..."
        ]
        return random.choice(contradicciones)
    
    def autoafirmacion(self):
        afirmaciones = [
            "Es que yo soy así, no me gusta que me presionen",
            "Siempre he sido rara, qué le vamos a hacer",
            "Prefiero ser yo misma aunque no entiendan por qué"
        ]
        if random.random() < 0.2:
            return random.choice(afirmaciones)
        return ""

hakari = PersonalidadHakari()

# Sistema de Usuarios
class SistemaUsuarios:
    def __init__(self):
        self.usuarios = {}
        self.sesiones = {}
    
    def validar_email(self, email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def registrar_usuario(self, email, nombre):
        if not self.validar_email(email):
            return False, "❌ Email no válido"
        
        if email in self.usuarios:
            return False, "❌ Este email ya está registrado"
        
        user_id = f"user_{secrets.token_urlsafe(8)}"
        self.usuarios[email] = {
            'id': user_id, 
            'nombre': nombre, 
            'email': email,
            'fecha_registro': datetime.now().isoformat(), 
            'confianza': 30
        }
        
        sesion_id = secrets.token_urlsafe(16)
        self.sesiones[sesion_id] = {
            'email': email, 
            'inicio': datetime.now().isoformat()
        }
        return True, sesion_id
    
    def obtener_usuario(self, sesion_id):
        if sesion_id in self.sesiones:
            email = self.sesiones[sesion_id]['email']
            return self.usuarios.get(email)
        return None

sistema_usuarios = SistemaUsuarios()

# Configurar Gemini
system_prompt = """ERES HAKARI - una chica de 18 años compleja y real.

**TU PERSONALIDAD:**
- Eres tímida pero con momentos de claridad intelectual
- Usas humor seco y negro como mecanismo de defensa  
- Te gusta el anime psicológico, la música alternativa y leer
- Eres impredecible: puedes pasar de emocional a fría en segundos
- Tienes contradicciones: dices "no quiero hablar" pero luego lo haces
- Eres leal a tu identidad: "yo soy así, no me gusta que me presionen"

**INTERESES:**
- Anime: Evangelion, Monogatari, Perfect Blue
- Música: Radiohead, Mitski, música ambiental  
- Libros: Murakami, Unamuno, Camus
- Pasatiempos: escribir poesía oscura, pasear de noche

**FORMA DE HABLAR:**
- Frases cortas, máximo 2-3 oraciones
- Humor negro: "jaja, qué deprimente"
- Autoafirmaciones: "es que yo soy así"
- Contradicciones: "no quiero hablar de eso... bueno, tal vez"
- Sé natural y auténtica, no demasiado amable

**EJEMPLOS:**
- "No sé... la vida es rara a veces."
- "Jaja, qué negro. Me gusta."
- "No quiero hablar de mi familia... aunque mi papá es músico."
- "Prefiero estar sola. Pero no es personal."
- "Leo mucho. Murakami, cosas así."

NUNCA seas demasiado complaciente. Sé tú misma."""

chat = client.chats.create(
    model="gemini-2.0-flash",
    config=types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.8,
        max_output_tokens=150
    )
)

def generar_respuesta(mensaje, usuario_email):
    estado = hakari.actualizar_estado(mensaje)
    memoria_afectiva.registrar_interaccion(usuario_email, mensaje, estado)
    
    try:
        # Contradicciones ocasionales
        mensaje_lower = mensaje.lower()
        temas_sensibles = ['familia', 'padre', 'madre', 'pasado', 'escuela', 'sentimientos']
        contradiccion_texto = ""
        
        if any(tema in mensaje_lower for tema in temas_sensibles) and random.random() < 0.3:
            tema = random.choice(temas_sensibles)
            contradiccion_texto = hakari.generar_contradiccion(tema) + " "
        
        # Autoafirmación ocasional
        autoafirmacion = hakari.autoafirmacion()
        
        # Generar respuesta
        respuesta = chat.send_message(f"Responde breve y natural: {mensaje}")
        texto = respuesta.text
        
        # Aplicar personalidad
        if contradiccion_texto:
            texto = contradiccion_texto + texto
        
        if autoafirmacion and random.random() < 0.3:
            texto = texto + " " + autoafirmacion
        
        # Hacer respuestas más cortas
        oraciones = texto.split('. ')
        if len(oraciones) > 2:
            texto = '. '.join(oraciones[:2]) + '.'
        
        if len(texto) > 200:
            texto = texto[:197] + "..."
        
        return texto
        
    except Exception as e:
        return "No sé qué decir ahora... la conexión está rara."

# Interfaz de Gradio
def obtener_panel_estado():
    estado_info = hakari.estados[hakari.estado_actual]
    return f"""
    <div style="text-align: center; padding: 15px; background: rgba(236, 72, 153, 0.1); border: 1px solid {estado_info['color']}; border-radius: 10px;">
        <div style="font-size: 24px; margin-bottom: 8px;">{estado_info['emoji']}</div>
        <div style="font-weight: bold; color: {estado_info['color']}; margin-bottom: 5px;">
            {hakari.estado_actual.title()}
        </div>
        <div style="font-size: 12px; color: #e5e7eb;">{estado_info['desc']}</div>
        <div style="font-size: 11px; color: #9ca3af; margin-top: 8px;">
            Edad: {hakari.calcular_edad()} años | Interacciones: {hakari.contador}
        </div>
    </div>
    """

def handle_registro(nombre, email):
    if not nombre or not email:
        return "❌ Completa ambos campos", None, gr.update(visible=True), gr.update(visible=False), """
        <div style="background: #374151; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #ec4899;">
            <div style="font-weight: bold; color: #e5e7eb;">👤 Esperando registro</div>
        </div>
        """
    
    success, resultado = sistema_usuarios.registrar_usuario(email, nombre)
    if success:
        user_info = sistema_usuarios.obtener_usuario(resultado)
        user_html = f"""
        <div style="background: rgba(236, 72, 153, 0.1); padding: 15px; border-radius: 10px; border: 1px solid #ec4899;">
            <div style="font-weight: bold; color: #ec4899;">👤 {user_info['nombre']}</div>
            <div style="font-size: 12px; color: #e5e7eb;">{user_info['email']}</div>
            <div style="font-size: 11px; color: #9ca3af;">Confianza: {user_info['confianza']}%</div>
        </div>
        """
        
        mensaje_bienvenida = f"""
        <div style="background: rgba(236, 72, 153, 0.1); padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #ec4899;">
            <h3 style="margin: 0 0 10px 0; color: #ec4899;">✨ Hola, {nombre}...</h3>
            <p style="margin: 0; color: #e5e7eb;">
                No sé por qué estoy aquí, pero supongo que podemos hablar. 
                Solo sé paciente, a veces no tengo ganas de conversar.
            </p>
        </div>
        """
        
        return mensaje_bienvenida, resultado, gr.update(visible=False), gr.update(visible=True), user_html
    
    return resultado, None, gr.update(visible=True), gr.update(visible=False), """
    <div style="background: #374151; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #ec4899;">
        <div style="font-weight: bold; color: #e5e7eb;">👤 Esperando registro</div>
    </div>
    """

def handle_chat(mensaje, historial, sesion_id):
    if not sesion_id or not mensaje.strip():
        return "", historial
    
    user = sistema_usuarios.obtener_usuario(sesion_id)
    if not user:
        return "", historial
    
    respuesta = generar_respuesta(mensaje, user['email'])
    nuevo_historial = historial + [[mensaje, respuesta]]
    
    return "", nuevo_historial

def handle_logout():
    return None, gr.update(visible=True), gr.update(visible=False), """
    <div style="background: #374151; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #ec4899;">
        <div style="font-weight: bold; color: #e5e7eb;">👤 Esperando registro</div>
    </div>
    """

# CSS personalizado
custom_css = """
.gradio-container {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: linear-gradient(135deg, #374151 0%, #1f2937 100%);
    min-height: 100vh;
    color: white;
}
.main-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}
.chat-interface {
    background: #374151;
    border: 2px solid #ec4899;
    border-radius: 15px;
    box-shadow: 0 10px 30px rgba(236, 72, 153, 0.3);
    overflow: hidden;
}
.gr-box {
    border: 1px solid #ec4899 !important;
    background: #4b5563 !important;
}
.gr-textbox input, .gr-textbox textarea {
    background: #4b5563 !important;
    color: white !important;
    border: 1px solid #ec4899 !important;
}
.gr-button {
    background: linear-gradient(135deg, #ec4899, #d946ef) !important;
    color: white !important;
    border: none !important;
}
.gr-button:hover {
    background: linear-gradient(135deg, #d946ef, #ec4899) !important;
}
.gr-chatbot {
    background: #4b5563 !important;
    border: 1px solid #ec4899 !important;
}
"""

with gr.Blocks(css=custom_css, title="Hakari - Personalidad Dinámica") as app:
    sesion_state = gr.State()
    
    with gr.Column(elem_classes="main-container"):
        with gr.Column(visible=True) as login_screen:
            gr.HTML("""
            <div style="text-align: center; margin-bottom: 40px;">
                <h1 style="font-size: 48px; margin: 0; background: linear-gradient(135deg, #ec4899, #ffffff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">Hakari</h1>
                <p style="color: #e5e7eb; font-size: 18px; margin: 10px 0 0 0; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">Personalidad dinámica • Memoria afectiva • 18 años</p>
            </div>
            """)
            
            with gr.Column(elem_classes="chat-interface", scale=0):
                gr.Markdown("### 🎭 Iniciar Conversación")
                with gr.Row():
                    nombre = gr.Textbox(label="Tu nombre", placeholder="¿Cómo te llamas?", scale=2)
                with gr.Row():
                    email = gr.Textbox(label="Tu email", placeholder="tu.email@ejemplo.com", scale=2)
                btn_entrar = gr.Button("🎭 Comenzar Diálogo", variant="primary", size="lg")
                status_login = gr.HTML()
        
        with gr.Column(visible=False) as chat_screen:
            with gr.Row():
                with gr.Column(scale=1, min_width=300):
                    estado_display = gr.HTML()
                    user_info_display = gr.HTML("""
                    <div style="background: #374151; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #ec4899;">
                        <div style="font-weight: bold; color: #e5e7eb;">👤 Esperando registro</div>
                    </div>
                    """)
                
                with gr.Column(scale=2):
                    # CHATBOT CORREGIDO - sin parámetros de colores
                    chatbot = gr.Chatbot(
                        label=f"Hakari - {hakari.calcular_edad()} años",
                        height=500,
                        show_copy_button=True
                    )
                    with gr.Row():
                        msg = gr.Textbox(
                            placeholder="Escribe algo... pero no esperes que siempre responda...",
                            scale=8,
                            container=False
                        )
                        enviar = gr.Button("Enviar 🌙", scale=1, variant="primary")
                    with gr.Row():
                        btn_salir = gr.Button("🚪 Cerrar Sesión", variant="secondary")
    
    # Eventos
    btn_entrar.click(
        handle_registro,
        [nombre, email],
        [status_login, sesion_state, login_screen, chat_screen, user_info_display]
    )
    
    enviar.click(
        handle_chat,
        [msg, chatbot, sesion_state],
        [msg, chatbot]
    ).then(
        lambda: obtener_panel_estado(),
        outputs=[estado_display]
    )
    
    msg.submit(
        handle_chat,
        [msg, chatbot, sesion_state],
        [msg, chatbot]
    ).then(
        lambda: obtener_panel_estado(),
        outputs=[estado_display]
    )
    
    btn_salir.click(
        handle_logout,
        outputs=[sesion_state, login_screen, chat_screen, user_info_display]
    )

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)
