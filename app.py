import os
import gradio as gr
from google import genai
from google.genai import types
import random
import secrets
import re
import sqlite3
import json
import requests
from datetime import datetime, date, timedelta
import pickle
from typing import Dict, List, Optional

# ==================== CONFIGURACIÓN ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# ==================== BASE DE DATOS SIMPLIFICADA ====================
class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect('hakari_memory.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Tabla de usuarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                nombre TEXT,
                fecha_registro DATETIME,
                nivel_confianza INTEGER DEFAULT 30,
                interacciones_totales INTEGER DEFAULT 0,
                ultima_visita DATETIME
            )
        ''')
        
        # Tabla de conversaciones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_email TEXT,
                mensaje_usuario TEXT,
                mensaje_hakari TEXT,
                estado_emocional TEXT,
                fecha DATETIME
            )
        ''')
        
        # Tabla de logros
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_email TEXT,
                logro_id TEXT,
                nombre TEXT,
                descripcion TEXT,
                fecha_desbloqueo DATETIME
            )
        ''')
        
        self.conn.commit()
    
    def guardar_conversacion(self, usuario_email: str, mensaje_usuario: str, mensaje_hakari: str, estado_emocional: str):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO conversaciones (usuario_email, mensaje_usuario, mensaje_hakari, estado_emocional, fecha)
                VALUES (?, ?, ?, ?, datetime('now'))
            ''', (usuario_email, mensaje_usuario, mensaje_hakari, estado_emocional))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error guardando conversación: {e}")
            return False
    
    def obtener_ultimas_conversaciones(self, usuario_email: str, limite: int = 10) -> List[List[str]]:
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT mensaje_usuario, mensaje_hakari
                FROM conversaciones 
                WHERE usuario_email = ?
                ORDER BY fecha DESC
                LIMIT ?
            ''', (usuario_email, limite))
            
            historial = []
            for row in cursor.fetchall():
                historial.append([row[0], row[1]])
            
            return historial[::-1]  # Invertir para orden cronológico
        except Exception as e:
            print(f"Error obteniendo conversaciones: {e}")
            return []
    
    def verificar_usuario_existe(self, email: str) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT id FROM usuarios WHERE email = ?', (email,))
            return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error verificando usuario: {e}")
            return False
    
    def obtener_datos_usuario(self, email: str) -> Optional[Dict]:
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT nombre, nivel_confianza, interacciones_totales, fecha_registro
                FROM usuarios WHERE email = ?
            ''', (email,))
            
            result = cursor.fetchone()
            if result:
                return {
                    'nombre': result[0],
                    'confianza': result[1],
                    'interacciones_totales': result[2],
                    'fecha_registro': result[3]
                }
            return None
        except Exception as e:
            print(f"Error obteniendo datos usuario: {e}")
            return None
    
    def registrar_usuario(self, email: str, nombre: str) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO usuarios (email, nombre, fecha_registro, ultima_visita)
                VALUES (?, ?, datetime('now'), datetime('now'))
            ''', (email, nombre))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error registrando usuario: {e}")
            return False
    
    def actualizar_estadisticas(self, email: str):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE usuarios 
                SET interacciones_totales = interacciones_totales + 1,
                    nivel_confianza = MIN(100, nivel_confianza + 1),
                    ultima_visita = datetime('now')
                WHERE email = ?
            ''', (email,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error actualizando estadísticas: {e}")
            return False
    
    def registrar_logro(self, usuario_email: str, logro_id: str, nombre: str, descripcion: str) -> bool:
        try:
            cursor = self.conn.cursor()
            # Verificar si ya existe
            cursor.execute('SELECT id FROM logros WHERE usuario_email = ? AND logro_id = ?', (usuario_email, logro_id))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO logros (usuario_email, logro_id, nombre, descripcion, fecha_desbloqueo)
                    VALUES (?, ?, ?, ?, datetime('now'))
                ''', (usuario_email, logro_id, nombre, descripcion))
                self.conn.commit()
                return True
            return False
        except Exception as e:
            print(f"Error registrando logro: {e}")
            return False
    
    def obtener_logros_usuario(self, usuario_email: str) -> List[str]:
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT nombre FROM logros WHERE usuario_email = ? LIMIT 5', (usuario_email,))
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error obteniendo logros: {e}")
            return []

db = DatabaseManager()

# ==================== SISTEMA DE AUTENTICACIÓN SIMPLIFICADO ====================
class SistemaAutenticacion:
    def __init__(self):
        self.sesiones_activas = {}
    
    def registrar_usuario(self, email: str, nombre: str) -> tuple[bool, str]:
        if db.verificar_usuario_existe(email):
            return False, "❌ Este email ya está registrado"
        
        if db.registrar_usuario(email, nombre):
            sesion_id = secrets.token_urlsafe(16)
            self.sesiones_activas[sesion_id] = {
                'email': email,
                'nombre': nombre,
                'inicio_sesion': datetime.now().isoformat()
            }
            
            # Primer logro
            db.registrar_logro(email, 'primer_conversacion', '🌟 Primer Contacto', 'Iniciaste tu primera conversación con Hakari')
            
            return True, sesion_id
        
        return False, "❌ Error al registrar usuario"
    
    def iniciar_sesion(self, email: str) -> tuple[bool, str]:
        if not db.verificar_usuario_existe(email):
            return False, "❌ Este email no está registrado"
        
        datos_usuario = db.obtener_datos_usuario(email)
        if not datos_usuario:
            return False, "❌ Error al cargar datos del usuario"
        
        sesion_id = secrets.token_urlsafe(16)
        self.sesiones_activas[sesion_id] = {
            'email': email,
            'nombre': datos_usuario['nombre'],
            'inicio_sesion': datetime.now().isoformat()
        }
        
        return True, sesion_id
    
    def verificar_sesion(self, sesion_id: str) -> bool:
        return sesion_id in self.sesiones_activas
    
    def obtener_datos_sesion(self, sesion_id: str) -> Optional[Dict]:
        return self.sesiones_activas.get(sesion_id)
    
    def cerrar_sesion(self, sesion_id: str):
        if sesion_id in self.sesiones_activas:
            del self.sesiones_activas[sesion_id]

sistema_auth = SistemaAutenticacion()

# ==================== PERSONALIDAD HAKARI SIMPLIFICADA ====================
class PersonalidadHakari:
    def __init__(self):
        self.estado_actual = "tímida"
        self.estados = {
            "tímida": {"emoji": "🌙", "color": "#6366f1", "desc": "No está segura de hablar"},
            "irónica": {"emoji": "😏", "color": "#f59e0b", "desc": "Humor negro activado"},
            "nostálgica": {"emoji": "📚", "color": "#3b82f6", "desc": "Recordando cosas"},
            "defensiva": {"emoji": "🛡️", "color": "#ef4444", "desc": "Protegiendo su espacio"},
            "curiosa": {"emoji": "🔍", "color": "#10b981", "desc": "Interesada a pesar de todo"}
        }
        self.contador = 0
    
    def calcular_edad(self):
        hoy = date.today()
        cumple = date(2007, 5, 1)
        return hoy.year - cumple.year - ((hoy.month, hoy.day) < (cumple.month, cumple.day))
    
    def actualizar_estado(self, mensaje: str):
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

hakari = PersonalidadHakari()

# ==================== SISTEMA DE LOGROS ====================
class SistemaLogros:
    def __init__(self):
        self.logros_disponibles = {
            'primer_conversacion': {'nombre': '🌟 Primer Contacto', 'descripcion': 'Iniciaste tu primera conversación con Hakari'},
            'confianza_50': {'nombre': '💝 Confianza Básica', 'descripcion': 'Alcanzaste 50% de confianza con Hakari'},
            '10_interacciones': {'nombre': '🎯 Conversador Persistente', 'descripcion': 'Completaste 10 interacciones con Hakari'},
            'descubrir_anime': {'nombre': '📺 Otaku en Desarrollo', 'descripcion': 'Hablaste sobre anime con Hakari'}
        }
    
    def verificar_logros(self, usuario_email: str, estadisticas: Dict):
        logros_desbloqueados = []
        
        if estadisticas.get('interacciones_totales', 0) >= 1:
            if db.registrar_logro(usuario_email, 'primer_conversacion', 
                                self.logros_disponibles['primer_conversacion']['nombre'],
                                self.logros_disponibles['primer_conversacion']['descripcion']):
                logros_desbloqueados.append('primer_conversacion')
        
        if estadisticas.get('confianza', 0) >= 50:
            if db.registrar_logro(usuario_email, 'confianza_50',
                                self.logros_disponibles['confianza_50']['nombre'],
                                self.logros_disponibles['confianza_50']['descripcion']):
                logros_desbloqueados.append('confianza_50')
        
        if estadisticas.get('interacciones_totales', 0) >= 10:
            if db.registrar_logro(usuario_email, '10_interacciones',
                                self.logros_disponibles['10_interacciones']['nombre'],
                                self.logros_disponibles['10_interacciones']['descripcion']):
                logros_desbloqueados.append('10_interacciones')
        
        return logros_desbloqueados

sistema_logros = SistemaLogros()

# ==================== MOTOR DE CONVERSACIÓN ====================
system_prompt = "ERES HAKARI - una chica de 18 años compleja y real. Eres tímida pero con momentos de claridad intelectual. Usas humor seco y negro como mecanismo de defensa. Te gusta el anime psicológico, la música alternativa y leer. Eres impredecible: puedes pasar de emocional a fría en segundos. Responde máximo 2-3 oraciones. Sé natural, auténtica, no demasiado amable."

try:
    chat = client.chats.create(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.8,
            max_output_tokens=150
        )
    )
except Exception as e:
    print(f"Error inicializando Gemini: {e}")
    chat = None

def generar_respuesta_simple(mensaje: str, usuario_email: str, sesion_id: str) -> str:
    # Actualizar estado de Hakari
    estado = hakari.actualizar_estado(mensaje)
    
    # Actualizar estadísticas del usuario
    db.actualizar_estadisticas(usuario_email)
    
    # Verificar logros
    datos_usuario = db.obtener_datos_usuario(usuario_email)
    if datos_usuario:
        sistema_logros.verificar_logros(usuario_email, datos_usuario)
    
    try:
        if not chat:
            return "⚠️ El sistema de IA no está disponible en este momento. ¿Podemos hablar igual?"
        
        respuesta = chat.send_message(f"Responde breve y natural: {mensaje}")
        texto_respuesta = respuesta.text
        
        # Guardar conversación
        db.guardar_conversacion(usuario_email, mensaje, texto_respuesta, estado)
        
        return texto_respuesta
        
    except Exception as e:
        print(f"Error generando respuesta: {e}")
        return "💫 Mis pensamientos están dispersos hoy... ¿podemos intentarlo de nuevo?"

# ==================== INTERFAZ GRADIO ====================
def obtener_panel_estado():
    estado_info = hakari.estados[hakari.estado_actual]
    return f"""
    <div style="text-align: center; padding: 15px; background: rgba(236, 72, 153, 0.1); border: 2px solid {estado_info['color']}; border-radius: 12px;">
        <div style="font-size: 28px; margin-bottom: 8px;">{estado_info['emoji']}</div>
        <div style="font-weight: bold; color: {estado_info['color']}; margin-bottom: 5px; font-size: 16px;">
            {hakari.estado_actual.title()}
        </div>
        <div style="font-size: 12px; color: #e5e7eb; margin-bottom: 8px;">{estado_info['desc']}</div>
        <div style="font-size: 10px; color: #6b7280;">
            Edad: {hakari.calcular_edad()} años | Interacciones: {hakari.contador}
        </div>
    </div>
    """

def obtener_panel_usuario(sesion_id: str):
    if not sesion_id or not sistema_auth.verificar_sesion(sesion_id):
        return """
        <div style="background: #374151; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #ec4899;">
            <div style="font-weight: bold; color: #e5e7eb;">👤 No has iniciado sesión</div>
        </div>
        """
    
    datos_sesion = sistema_auth.obtener_datos_sesion(sesion_id)
    datos_usuario = db.obtener_datos_usuario(datos_sesion['email'])
    
    if not datos_usuario:
        return """
        <div style="background: #374151; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #ec4899;">
            <div style="font-weight: bold; color: #e5e7eb;">👤 Error al cargar datos</div>
        </div>
        """
    
    # Obtener logros
    logros = db.obtener_logros_usuario(datos_sesion['email'])
    
    logros_html = ""
    if logros:
        logros_html = f"""
        <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #4b5563;">
            <div style="font-size: 11px; color: #9ca3af; margin-bottom: 5px;"><strong>Logros:</strong></div>
            <div style="font-size: 10px; color: #d946ef;">{' • '.join(logros)}</div>
        </div>
        """
    
    return f"""
    <div style="background: rgba(236, 72, 153, 0.1); padding: 15px; border-radius: 10px; border: 1px solid #ec4899;">
        <div style="font-weight: bold; color: #ec4899; font-size: 14px;">👤 {datos_usuario['nombre']}</div>
        <div style="font-size: 11px; color: #e5e7eb; margin: 5px 0;">{datos_sesion['email']}</div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px; font-size: 10px; color: #9ca3af; margin: 8px 0;">
            <div>
                <strong>Confianza:</strong><br>
                <div style="background: #374151; border-radius: 3px; overflow: hidden;">
                    <div style="background: #ec4899; width: {datos_usuario['confianza']}%; height: 6px;"></div>
                </div>
                {datos_usuario['confianza']}%
            </div>
            <div>
                <strong>Interacciones:</strong><br>
                {datos_usuario['interacciones_totales']}
            </div>
        </div>
        {logros_html}
    </div>
    """

# ==================== APLICACIÓN GRADIO ====================
custom_css = """
.gradio-container {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: linear-gradient(135deg, #1e1b4b 0%, #3730a3 100%);
    min-height: 100vh;
    color: white;
}
.main-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
}
.chat-interface {
    background: rgba(30, 27, 75, 0.8);
    backdrop-filter: blur(10px);
    border: 2px solid #ec4899;
    border-radius: 20px;
    box-shadow: 0 20px 40px rgba(236, 72, 153, 0.3);
    overflow: hidden;
}
.gr-box {
    border: 1px solid #ec4899 !important;
    background: #312e81 !important;
}
.gr-textbox input, .gr-textbox textarea {
    background: #312e81 !important;
    color: white !important;
    border: 1px solid #ec4899 !important;
    border-radius: 10px !important;
}
.gr-button {
    background: linear-gradient(135deg, #ec4899, #d946ef) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}
.gr-button:hover {
    background: linear-gradient(135deg, #d946ef, #ec4899) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 5px 15px rgba(236, 72, 153, 0.4) !important;
}
.gr-chatbot {
    background: #312e81 !important;
    border: 1px solid #ec4899 !important;
    border-radius: 15px !important;
}
.tab-buttons {
    background: rgba(236, 72, 153, 0.1) !important;
    border-radius: 10px !important;
    padding: 10px !important;
}
"""

with gr.Blocks(css=custom_css, title="Hakari - Con Sistema de Login") as app:
    sesion_state = gr.State()
    
    with gr.Column(elem_classes="main-container"):
        with gr.Column(visible=True) as login_screen:
            gr.HTML("""
            <div style="text-align: center; margin-bottom: 50px;">
                <h1 style="font-size: 52px; margin: 0; background: linear-gradient(135deg, #ec4899, #a855f7, #ffffff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; text-shadow: 0 4px 8px rgba(0,0,0,0.3);">Hakari</h1>
                <p style="color: #e5e7eb; font-size: 20px; margin: 15px 0 0 0; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">
                    Sistema de Login • Conversaciones Guardadas
                </p>
            </div>
            """)
            
            with gr.Column(elem_classes="chat-interface", scale=0):
                with gr.Tabs() as tabs:
                    with gr.TabItem("📝 Registrarse"):
                        gr.Markdown("### 🚀 Crear cuenta nueva")
                        with gr.Row():
                            nombre_registro = gr.Textbox(
                                label="Tu nombre", 
                                placeholder="¿Cómo te llamas?",
                                scale=2
                            )
                        with gr.Row():
                            email_registro = gr.Textbox(
                                label="Tu email", 
                                placeholder="tu.email@ejemplo.com",
                                scale=2
                            )
                        btn_registro = gr.Button(
                            "🎭 Crear Cuenta", 
                            variant="primary", 
                            size="lg"
                        )
                    
                    with gr.TabItem("🔐 Iniciar Sesión"):
                        gr.Markdown("### 🔑 Acceder a cuenta existente")
                        with gr.Row():
                            email_login = gr.Textbox(
                                label="Tu email", 
                                placeholder="tu.email@ejemplo.com",
                                scale=2
                            )
                        btn_login = gr.Button(
                            "🚀 Iniciar Sesión", 
                            variant="primary", 
                            size="lg"
                        )
                
                status_login = gr.HTML()
        
        with gr.Column(visible=False) as chat_screen:
            with gr.Row(equal_height=True):
                with gr.Column(scale=1, min_width=350):
                    with gr.Column():
                        gr.Markdown("### 🧠 Estado de Hakari")
                        estado_display = gr.HTML()
                        
                        gr.Markdown("### 👤 Tu Perfil")
                        user_info_display = gr.HTML()
                
                with gr.Column(scale=2):
                    chatbot = gr.Chatbot(
                        label=f"Hakari - {hakari.calcular_edad()} años",
                        height=600,
                        show_copy_button=True,
                        placeholder="Escribe un mensaje para Hakari..."
                    )
                    
                    with gr.Row():
                        msg = gr.Textbox(
                            placeholder="Escribe tu mensaje aquí...",
                            scale=8,
                            container=False,
                            lines=2
                        )
                        enviar = gr.Button("✨ Enviar", scale=1, variant="primary")
                    
                    with gr.Row():
                        btn_limpiar = gr.Button("🧹 Limpiar Chat", variant="secondary")
                        btn_salir = gr.Button("🚪 Cerrar Sesión", variant="secondary")
                    
                    status_chat = gr.HTML()
    
    # ==================== MANEJADORES ====================
    def handle_registro(nombre: str, email: str):
        if not nombre or not email:
            return "❌ Completa ambos campos", None, gr.update(visible=True), gr.update(visible=False), obtener_panel_usuario(None), []
        
        success, resultado = sistema_auth.registrar_usuario(email, nombre)
        if success:
            # Cargar historial vacío para nuevo usuario
            historial = []
            
            mensaje_bienvenida = f"""
            <div style="background: linear-gradient(135deg, rgba(236, 72, 153, 0.2), rgba(168, 85, 247, 0.2)); padding: 25px; border-radius: 15px; text-align: center; border: 2px solid #ec4899;">
                <h3 style="margin: 0 0 15px 0; color: #ec4899; font-size: 24px;">✨ Cuenta creada, {nombre}!</h3>
                <p style="margin: 0; color: #e5e7eb; font-size: 16px;">
                    Bienvenido a Hakari. Tus conversaciones se guardarán automáticamente.
                </p>
            </div>
            """
            
            return mensaje_bienvenida, resultado, gr.update(visible=False), gr.update(visible=True), obtener_panel_usuario(resultado), historial
        
        return resultado, None, gr.update(visible=True), gr.update(visible=False), obtener_panel_usuario(None), []
    
    def handle_login(email: str):
        if not email:
            return "❌ Ingresa tu email", None, gr.update(visible=True), gr.update(visible=False), obtener_panel_usuario(None), []
        
        success, resultado = sistema_auth.iniciar_sesion(email)
        if success:
            # Cargar historial de conversaciones
            datos_sesion = sistema_auth.obtener_datos_sesion(resultado)
            historial = db.obtener_ultimas_conversaciones(datos_sesion['email'], limite=20)
            datos_usuario = db.obtener_datos_usuario(email)
            
            mensaje_bienvenida = f"""
            <div style="background: linear-gradient(135deg, rgba(236, 72, 153, 0.2), rgba(168, 85, 247, 0.2)); padding: 25px; border-radius: 15px; text-align: center; border: 2px solid #ec4899;">
                <h3 style="margin: 0 0 15px 0; color: #ec4899; font-size: 24px;">✨ Bienvenido de vuelta, {datos_usuario['nombre']}!</h3>
                <p style="margin: 0; color: #e5e7eb; font-size: 16px;">
                    {len(historial)} mensajes anteriores cargados.
                </p>
            </div>
            """
            
            return mensaje_bienvenida, resultado, gr.update(visible=False), gr.update(visible=True), obtener_panel_usuario(resultado), historial
        
        return resultado, None, gr.update(visible=True), gr.update(visible=False), obtener_panel_usuario(None), []
    
    def handle_chat(mensaje: str, historial, sesion_id: str):
        if not sesion_id or not mensaje.strip():
            return "", historial, obtener_panel_estado()
        
        if not sistema_auth.verificar_sesion(sesion_id):
            return "", historial, obtener_panel_estado()
        
        datos_sesion = sistema_auth.obtener_datos_sesion(sesion_id)
        respuesta = generar_respuesta_simple(mensaje, datos_sesion['email'], sesion_id)
        nuevo_historial = historial + [[mensaje, respuesta]]
        
        return "", nuevo_historial, obtener_panel_estado()
    
    def handle_logout(sesion_id: str):
        if sesion_id:
            sistema_auth.cerrar_sesion(sesion_id)
        
        return None, gr.update(visible=True), gr.update(visible=False), obtener_panel_usuario(None), []
    
    # ==================== CONEXIÓN ====================
    btn_registro.click(
        handle_registro,
        [nombre_registro, email_registro],
        [status_login, sesion_state, login_screen, chat_screen, user_info_display, chatbot]
    )
    
    btn_login.click(
        handle_login,
        [email_login],
        [status_login, sesion_state, login_screen, chat_screen, user_info_display, chatbot]
    )
    
    enviar.click(
        handle_chat,
        [msg, chatbot, sesion_state],
        [msg, chatbot, estado_display]
    )
    
    msg.submit(
        handle_chat,
        [msg, chatbot, sesion_state],
        [msg, chatbot, estado_display]
    )
    
    btn_salir.click(
        handle_logout,
        inputs=[sesion_state],
        outputs=[sesion_state, login_screen, chat_screen, user_info_display, chatbot]
    )
    
    btn_limpiar.click(
        fn=lambda: [],
        outputs=[chatbot]
    )

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)
