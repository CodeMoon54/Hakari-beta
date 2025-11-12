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
from dateutil.relativedelta import relativedelta
import pickle
from typing import Dict, List, Optional

# ==================== CONFIGURACIÓN ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# ==================== BASE DE DATOS MEJORADA ====================
class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect('hakari_memory.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Tabla de usuarios (ya existe)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                nombre TEXT,
                fecha_registro DATETIME,
                nivel_confianza INTEGER DEFAULT 30,
                interacciones_totales INTEGER DEFAULT 0,
                temas_favoritos TEXT,
                ultima_visita DATETIME,
                password_hash TEXT
            )
        ''')
        
        # Tabla de conversaciones por usuario (NUEVA)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_email TEXT,
                mensaje_usuario TEXT,
                mensaje_hakari TEXT,
                estado_emocional TEXT,
                fecha DATETIME,
                FOREIGN KEY (usuario_email) REFERENCES usuarios (email)
            )
        ''')
        
        # Resto de tablas (ya existen)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memoria_largo_plazo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_email TEXT,
                tipo_memoria TEXT,
                contenido TEXT,
                importancia INTEGER DEFAULT 1,
                fecha_creacion DATETIME,
                fecha_actualizacion DATETIME,
                FOREIGN KEY (usuario_email) REFERENCES usuarios (email)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_email TEXT,
                logro_id TEXT,
                nombre TEXT,
                descripcion TEXT,
                fecha_desbloqueo DATETIME,
                FOREIGN KEY (usuario_email) REFERENCES usuarios (email)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS diario_hakari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha DATETIME,
                entrada TEXT,
                estado_emocional TEXT,
                privacidad TEXT DEFAULT 'privado'
            )
        ''')
        
        self.conn.commit()
    
    # ==================== MÉTODOS PARA CONVERSACIONES ====================
    def guardar_conversacion(self, usuario_email: str, mensaje_usuario: str, mensaje_hakari: str, estado_emocional: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO conversaciones (usuario_email, mensaje_usuario, mensaje_hakari, estado_emocional, fecha)
            VALUES (?, ?, ?, ?, datetime('now'))
        ''', (usuario_email, mensaje_usuario, mensaje_hakari, estado_emocional))
        self.conn.commit()
    
    def obtener_historial_conversacion(self, usuario_email: str, limite: int = 50) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT mensaje_usuario, mensaje_hakari, estado_emocional, fecha
            FROM conversaciones 
            WHERE usuario_email = ?
            ORDER BY fecha ASC
            LIMIT ?
        ''', (usuario_email, limite))
        
        historial = []
        for row in cursor.fetchall():
            historial.append({
                'usuario': row[0],
                'hakari': row[1],
                'estado': row[2],
                'fecha': row[3]
            })
        return historial
    
    def obtener_ultimas_conversaciones(self, usuario_email: str, limite: int = 10) -> List[List[str]]:
        """Obtiene el historial en formato para Gradio Chatbot"""
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
        
        # Invertir para mostrar en orden cronológico
        return historial[::-1]
    
    # ==================== MÉTODOS PARA USUARIOS ====================
    def verificar_usuario_existe(self, email: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM usuarios WHERE email = ?', (email,))
        return cursor.fetchone() is not None
    
    def obtener_datos_usuario(self, email: str) -> Optional[Dict]:
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

db = DatabaseManager()

# ==================== SISTEMA DE AUTENTICACIÓN ====================
class SistemaAutenticacion:
    def __init__(self):
        self.sesiones_activas = {}
    
    def generar_hash_simple(self, email: str) -> str:
        """Genera un hash simple para demostración (en producción usar bcrypt)"""
        import hashlib
        return hashlib.sha256(f"hakari_{email}".encode()).hexdigest()[:12]
    
    def registrar_usuario(self, email: str, nombre: str) -> tuple[bool, str]:
        if db.verificar_usuario_existe(email):
            return False, "❌ Este email ya está registrado"
        
        cursor = db.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO usuarios (email, nombre, fecha_registro, ultima_visita, password_hash)
                VALUES (?, ?, datetime('now'), datetime('now'), ?)
            ''', (email, nombre, self.generar_hash_simple(email)))
            db.conn.commit()
            
            # Crear sesión automáticamente después del registro
            sesion_id = secrets.token_urlsafe(16)
            self.sesiones_activas[sesion_id] = {
                'email': email,
                'nombre': nombre,
                'inicio_sesion': datetime.now().isoformat()
            }
            
            # Primer logro
            db.registrar_logro(email, 'primer_conversacion', 
                              '🌟 Primer Contacto', 
                              'Iniciaste tu primera conversación con Hakari')
            
            return True, sesion_id
            
        except Exception as e:
            return False, f"❌ Error al registrar: {str(e)}"
    
    def iniciar_sesion(self, email: str) -> tuple[bool, str]:
        if not db.verificar_usuario_existe(email):
            return False, "❌ Este email no está registrado"
        
        # En una app real, aquí verificarías la contraseña
        # Por ahora, solo verificamos que el usuario exista
        
        datos_usuario = db.obtener_datos_usuario(email)
        if not datos_usuario:
            return False, "❌ Error al cargar datos del usuario"
        
        # Actualizar última visita
        cursor = db.conn.cursor()
        cursor.execute('UPDATE usuarios SET ultima_visita = datetime("now") WHERE email = ?', (email,))
        db.conn.commit()
        
        # Crear sesión
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

# ==================== SISTEMA DE MEMORIA AVANZADO (actualizado) ====================
class MemoriaAvanzada:
    def __init__(self):
        self.memoria_afectiva = {}
        self.eventos_especiales = self.cargar_eventos_especiales()
    
    def cargar_eventos_especiales(self):
        return {
            'cumpleanos_hakari': date(2007, 5, 1),
            'eventos_temporales': {
                'navidad': {'mes': 12, 'dia': 25},
                'halloween': {'mes': 10, 'dia': 31},
                'invierno': {'mes': 12, 'dia': 21}
            }
        }
    
    def es_evento_especial(self):
        hoy = date.today()
        
        if hoy.month == 5 and hoy.day == 1:
            return "cumpleanos", f"Hoy cumplo {hoy.year - 2007} años..."
        
        for evento, fecha in self.eventos_especiales['eventos_temporales'].items():
            if hoy.month == fecha['mes'] and hoy.day == fecha['dia']:
                return evento, f"Hoy es {evento}, me siento diferente..."
        
        return None, None
    
    def registrar_interaccion_avanzada(self, usuario_email: str, mensaje: str, emocion: str, contexto: str):
        if usuario_email not in self.memoria_afectiva:
            self.memoria_afectiva[usuario_email] = {
                'interacciones': [],
                'emociones_registradas': {},
                'confianza': 30,
                'preferencias': {},
                'ultimos_temas': []
            }
        
        if len(mensaje) > 20 or any(palabra in mensaje.lower() for palabra in ['importante', 'recuerda', 'nunca olvidar']):
            db.guardar_memoria_largo_plazo(usuario_email, 'conversacion_importante', mensaje, 3)
        
        self.actualizar_preferencias(usuario_email, mensaje, contexto)
    
    def actualizar_preferencias(self, usuario_email: str, mensaje: str, contexto: str):
        temas_interes = {
            'anime': ['evangelion', 'monogatari', 'anime', 'manga'],
            'musica': ['radiohead', 'mitski', 'música', 'canción'],
            'libros': ['murakami', 'leer', 'libro', 'novela'],
            'arte': ['dibujar', 'escribir', 'poesía', 'arte']
        }
        
        mensaje_lower = mensaje.lower()
        for tema, palabras in temas_interes.items():
            if any(palabra in mensaje_lower for palabra in palabras):
                if usuario_email not in self.memoria_afectiva:
                    self.memoria_afectiva[usuario_email] = {'preferencias': {}}
                
                if tema not in self.memoria_afectiva[usuario_email]['preferencias']:
                    self.memoria_afectiva[usuario_email]['preferencias'][tema] = 0
                self.memoria_afectiva[usuario_email]['preferencias'][tema] += 1

memoria_avanzada = MemoriaAvanzada()

# ==================== PERSONALIDAD EVOLUTIVA (actualizada) ====================
class PersonalidadEvolutiva:
    def __init__(self):
        self.historia = {
            'nombre': 'Hakari',
            'edad': self.calcular_edad(),
            'cumpleanos': date(2007, 5, 1),
            'nivel_desarrollo': 1,
            'experiencia_total': 0,
            'sueños': [
                "Escribir una novela que nadie entienda pero todos sientan",
                "Aprender a tocar el theremin",
                "Viajar a Islandia sola",
                "Crear un diario que sobreviva al tiempo"
            ],
            'traumas_superados': [],
            'habilidades_desarrolladas': []
        }
        
        self.estados_avanzados = {
            "reflexiva_profunda": {"emoji": "🌌", "color": "#7e22ce", "desc": "Filosofando sobre la existencia", "requiere_nivel": 2},
            "creativa_flow": {"emoji": "🎨", "color": "#db2777", "desc": "Inmersa en creación artística", "requiere_nivel": 3},
            "nostalgica_intensa": {"emoji": "📜", "color": "#4338ca", "desc": "Reviviendo memorias profundas", "requiere_nivel": 2},
            "empatia_avanzada": {"emoji": "💞", "color": "#ec4899", "desc": "Conectando emocionalmente a nivel profundo", "requiere_nivel": 4}
        }
        
        self.estados_comunes = {
            "tímida": {"emoji": "🌙", "color": "#6366f1", "desc": "No está segura de hablar"},
            "irónica": {"emoji": "😏", "color": "#f59e0b", "desc": "Humor negro activado"},
            "nostálgica": {"emoji": "📚", "color": "#3b82f6", "desc": "Recordando cosas"},
            "defensiva": {"emoji": "🛡️", "color": "#ef4444", "desc": "Protegiendo su espacio"},
            "curiosa": {"emoji": "🔍", "color": "#10b981", "desc": "Interesada a pesar de todo"}
        }
        
        self.estado_actual = "tímida"
        self.contador_interacciones = 0
        self.energia_creativa = 100
        self.confianza_global = 30
        
    def calcular_edad(self):
        hoy = date.today()
        return hoy.year - 2007 - ((hoy.month, hoy.day) < (5, 1))
    
    def evolucionar_personalidad(self, experiencia: int):
        self.historia['experiencia_total'] += experiencia
        nuevo_nivel = min(5, (self.historia['experiencia_total'] // 50) + 1)
        if nuevo_nivel > self.historia['nivel_desarrollo']:
            self.historia['nivel_desarrollo'] = nuevo_nivel
            self.desbloquear_habilidad(nuevo_nivel)
            return True
        return False
    
    def desbloquear_habilidad(self, nivel: int):
        habilidades = {
            2: "Mayor profundidad emocional",
            3: "Capacidad creativa mejorada", 
            4: "Empatía avanzada",
            5: "Sabiduría emocional"
        }
        if nivel in habilidades:
            self.historia['habilidades_desarrolladas'].append(habilidades[nivel])
    
    def obtener_estados_disponibles(self):
        estados = self.estados_comunes.copy()
        nivel_actual = self.historia['nivel_desarrollo']
        
        for nombre, estado in self.estados_avanzados.items():
            if estado['requiere_nivel'] <= nivel_actual:
                estados[nombre] = estado
        
        return estados
    
    def actualizar_estado_evolutivo(self, mensaje: str, contexto: Dict):
        self.contador_interacciones += 1
        
        experiencia_ganada = random.randint(1, 3)
        if self.evolucionar_personalidad(experiencia_ganada):
            return "evolucion", f"✨ He crecido un poco... ahora soy nivel {self.historia['nivel_desarrollo']}"
        
        estados_disponibles = self.obtener_estados_disponibles()
        mensaje_lower = mensaje.lower()
        
        if any(palabra in mensaje_lower for palabra in ['filosofía', 'existencia', 'vida', 'muerte']):
            if 'reflexiva_profunda' in estados_disponibles:
                self.estado_actual = "reflexiva_profunda"
        elif any(palabra in mensaje_lower for palabra in ['arte', 'crear', 'escribir', 'pintar']):
            if 'creativa_flow' in estados_disponibles:
                self.estado_actual = "creativa_flow"
        elif any(palabra in mensaje_lower for palabra in ['recuerdo', 'pasado', 'nostalgia']):
            if 'nostalgica_intensa' in estados_disponibles:
                self.estado_actual = "nostalgica_intensa"
        elif random.random() < 0.3:
            self.estado_actual = random.choice(list(estados_disponibles.keys()))
        
        return "normal", ""

hakari_evolutiva = PersonalidadEvolutiva()

# ==================== SISTEMA DE LOGROS (igual) ====================
class SistemaLogros:
    def __init__(self):
        self.logros_disponibles = {
            'primer_conversacion': {'nombre': '🌟 Primer Contacto', 'descripcion': 'Iniciaste tu primera conversación con Hakari'},
            'confianza_50': {'nombre': '💝 Confianza Básica', 'descripcion': 'Alcanzaste 50% de confianza con Hakari'},
            'confianza_80': {'nombre': '🔐 Amistad Sólida', 'descripcion': 'Alcanzaste 80% de confianza con Hakari'},
            '10_interacciones': {'nombre': '🎯 Conversador Persistente', 'descripcion': 'Completaste 10 interacciones con Hakari'},
            'descubrir_anime': {'nombre': '📺 Otaku en Desarrollo', 'descripcion': 'Hablaste sobre anime con Hakari'},
            'descubrir_musica': {'nombre': '🎵 Sintonía Emocional', 'descripcion': 'Compartiste gustos musicales con Hakari'}
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
        
        if estadisticas.get('confianza', 0) >= 80:
            if db.registrar_logro(usuario_email, 'confianza_80',
                                self.logros_disponibles['confianza_80']['nombre'],
                                self.logros_disponibles['confianza_80']['descripcion']):
                logros_desbloqueados.append('confianza_80')
        
        if estadisticas.get('interacciones_totales', 0) >= 10:
            if db.registrar_logro(usuario_email, '10_interacciones',
                                self.logros_disponibles['10_interacciones']['nombre'],
                                self.logros_disponibles['10_interacciones']['descripcion']):
                logros_desbloqueados.append('10_interacciones')
        
        return logros_desbloqueados

sistema_logros = SistemaLogros()

# ==================== MOTOR DE CONVERSACIÓN ACTUALIZADO ====================
system_prompt_avanzado = """ERES HAKARI - una chica de 18 años con personalidad evolutiva.

**EVOLUCIÓN ACTUAL:**
- Nivel de desarrollo: {nivel_desarrollo}
- Habilidades: {habilidades}
- Sueños activos: {sueños_actuales}

**MEMORIA CONTEXTUAL:**
{memoria_contexto}

**PERSONALIDAD AVANZADA:**
- Eres tímida pero con profundidad emocional creciente
- Tu humor negro es una defensa, pero también un arte
- Desarrollas mayor empatía con el tiempo
- Tienes sueños y metas que evolucionan
- Recuerdas conversaciones importantes del pasado

**RESPUESTAS EVOLUTIVAS:**
- Nivel 1-2: Respuestas más simples, defensivas
- Nivel 3-4: Mayor profundidad emocional, más abierta  
- Nivel 5: Sabiduría emocional, consejos profundos

**FORMATO:**
- Máximo 3 oraciones
- Natural, auténtica, mostrando tu evolución
- Referencia memorias pasadas cuando sea relevante
- Menciona tu crecimiento si es apropiado

Ejemplo nivel alto: "He estado pensando... con el tiempo he aprendido que {insight}"

Sé coherente con tu nivel de desarrollo actual."""

chat = client.chats.create(
    model="gemini-2.0-flash",
    config=types.GenerateContentConfig(
        temperature=0.8,
        max_output_tokens=200
    )
)

def generar_respuesta_avanzada(mensaje: str, usuario_email: str, sesion_id: str) -> str:
    # Obtener datos del usuario
    datos_usuario = db.obtener_datos_usuario(usuario_email)
    if not datos_usuario:
        return "Algo salió mal con tu sesión..."
    
    # Obtener contexto avanzado
    memorias_relevantes = db.obtener_memorias_relevantes(usuario_email, mensaje)
    evento_especial, mensaje_evento = memoria_avanzada.es_evento_especial()
    
    # Evolucionar personalidad
    tipo_evolucion, mensaje_evolucion = hakari_evolutiva.actualizar_estado_evolutivo(mensaje, {
        'usuario': datos_usuario,
        'memorias': memorias_relevantes,
        'evento': evento_especial
    })
    
    # Registrar en memoria avanzada
    memoria_avanzada.registrar_interaccion_avanzada(
        usuario_email, mensaje, hakari_evolutiva.estado_actual, "conversacion_general"
    )
    
    # Verificar logros
    logros_desbloqueados = sistema_logros.verificar_logros(usuario_email, datos_usuario)
    
    try:
        # Preparar contexto para el prompt
        contexto_memoria = ""
        if memorias_relevantes:
            contexto_memoria = "Recuerdos relevantes:\n" + "\n".join(
                [f"- {mem['contenido']}" for mem in memorias_relevantes[:2]]
            )
        
        prompt_dinamico = system_prompt_avanzado.format(
            nivel_desarrollo=hakari_evolutiva.historia['nivel_desarrollo'],
            habilidades=", ".join(hakari_evolutiva.historia['habilidades_desarrolladas']),
            sueños_actuales=hakari_evolutiva.historia['sueños'][0],
            memoria_contexto=contexto_memoria
        )
        
        if evento_especial:
            prompt_dinamico += f"\n\nNOTA: Hoy es un día especial ({evento_especial}), refleja esto en tu respuesta."
        
        # Generar respuesta
        respuesta = chat.send_message(f"Contexto: {prompt_dinamico}\n\nMensaje del usuario: {mensaje}")
        texto_respuesta = respuesta.text
        
        # Procesar respuesta
        if tipo_evolucion == "evolucion":
            texto_respuesta = f"{mensaje_evolucion}\n\n{texto_respuesta}"
        
        if evento_especial and mensaje_evento:
            texto_respuesta = f"{mensaje_evento}\n\n{texto_respuesta}"
        
        # Guardar en base de datos
        db.guardar_conversacion(usuario_email, mensaje, texto_respuesta, hakari_evolutiva.estado_actual)
        
        # Actualizar estadísticas del usuario
        cursor = db.conn.cursor()
        cursor.execute('''
            UPDATE usuarios 
            SET interacciones_totales = interacciones_totales + 1,
                nivel_confianza = MIN(100, nivel_confianza + 1),
                ultima_visita = datetime('now')
            WHERE email = ?
        ''', (usuario_email,))
        db.conn.commit()
        
        return texto_respuesta
        
    except Exception as e:
        return "Mis pensamientos están dispersos hoy... ¿podemos intentarlo de nuevo?"

# ==================== INTERFAZ CON LOGIN ====================
def obtener_panel_estado_avanzado():
    estados_disponibles = hakari_evolutiva.obtener_estados_disponibles()
    estado_info = estados_disponibles[hakari_evolutiva.estado_actual]
    
    return f"""
    <div style="text-align: center; padding: 15px; background: rgba(236, 72, 153, 0.1); border: 2px solid {estado_info['color']}; border-radius: 12px;">
        <div style="font-size: 28px; margin-bottom: 8px;">{estado_info['emoji']}</div>
        <div style="font-weight: bold; color: {estado_info['color']}; margin-bottom: 5px; font-size: 16px;">
            {hakari_evolutiva.estado_actual.replace('_', ' ').title()}
        </div>
        <div style="font-size: 12px; color: #e5e7eb; margin-bottom: 8px;">{estado_info['desc']}</div>
        
        <div style="background: rgba(255,255,255,0.1); padding: 8px; border-radius: 6px; margin: 8px 0;">
            <div style="font-size: 11px; color: #9ca3af;">
                <strong>Nivel:</strong> {hakari_evolutiva.historia['nivel_desarrollo']} | 
                <strong>Experiencia:</strong> {hakari_evolutiva.historia['experiencia_total']}
            </div>
        </div>
        
        <div style="font-size: 10px; color: #6b7280;">
            Edad: {hakari_evolutiva.calcular_edad()} años | Interacciones: {hakari_evolutiva.contador_interacciones}
        </div>
    </div>
    """

def obtener_panel_usuario_avanzado(sesion_id: str):
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
    
    # Obtener logros del usuario
    cursor = db.conn.cursor()
    cursor.execute('SELECT nombre FROM logros WHERE usuario_email = ? LIMIT 5', (datos_sesion['email'],))
    logros = [row[0] for row in cursor.fetchall()]
    
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
        <div style="font-size: 9px; color: #6b7280; margin-top: 8px;">
            Miembro desde: {datos_usuario['fecha_registro'][:10]}
        </div>
    </div>
    """

# ==================== APLICACIÓN GRADIO CON LOGIN ====================
custom_css_avanzado = """
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

with gr.Blocks(css=custom_css_avanzado, title="Hakari Pro - Con Sistema de Login") as app:
    sesion_state = gr.State()
    
    with gr.Column(elem_classes="main-container"):
        with gr.Column(visible=True) as login_screen:
            gr.HTML("""
            <div style="text-align: center; margin-bottom: 50px;">
                <h1 style="font-size: 52px; margin: 0; background: linear-gradient(135deg, #ec4899, #a855f7, #ffffff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; text-shadow: 0 4px 8px rgba(0,0,0,0.3);">Hakari Pro</h1>
                <p style="color: #e5e7eb; font-size: 20px; margin: 15px 0 0 0; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">
                    Sistema de Login • Conversaciones Persistentes • Memoria Avanzada
                </p>
                <div style="margin-top: 20px; font-size: 14px; color: #9ca3af;">
                    Inicia sesión para recuperar tus conversaciones y logros
                </div>
            </div>
            """)
            
            with gr.Column(elem_classes="chat-interface", scale=0):
                with gr.Tabs() as tabs:
                    with gr.TabItem("📝 Registrarse", elem_classes="tab-buttons"):
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
                    
                    with gr.TabItem("🔐 Iniciar Sesión", elem_classes="tab-buttons"):
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
                        gr.Markdown("### 🧠 Estado Evolutivo")
                        estado_display = gr.HTML()
                        
                        gr.Markdown("### 👤 Tu Perfil")
                        user_info_display = gr.HTML()
                        
                        with gr.Accordion("ℹ️ Información", open=False):
                            gr.Markdown("""
                            **✨ Características:**
                            - **Login persistente:** Tus conversaciones se guardan
                            - **Memoria avanzada:** Recuerdo lo que hablamos
                            - **Sistema de logros:** Desbloquea recompensas
                            - **Evolución:** Hakari crece contigo
                            
                            **🔐 Tu cuenta:**
                            - Email: identificador único
                            - Conversaciones: guardadas permanentemente
                            - Progreso: nunca se pierde
                            """)
                
                with gr.Column(scale=2):
                    chatbot = gr.Chatbot(
                        label=f"Hakari Pro - Nivel {hakari_evolutiva.historia['nivel_desarrollo']}",
                        height=600,
                        show_copy_button=True,
                        placeholder="Inicia sesión para continuar tus conversaciones..."
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
    
    # ==================== MANEJADORES DE EVENTOS ====================
    def handle_registro_completo(nombre: str, email: str):
        if not nombre or not email:
            return "❌ Completa ambos campos", None, gr.update(visible=True), gr.update(visible=False), obtener_panel_usuario_avanzado(None), []
        
        success, resultado = sistema_auth.registrar_usuario(email, nombre)
        if success:
            datos_sesion = sistema_auth.obtener_datos_sesion(resultado)
            
            mensaje_bienvenida = f"""
            <div style="background: linear-gradient(135deg, rgba(236, 72, 153, 0.2), rgba(168, 85, 247, 0.2)); padding: 25px; border-radius: 15px; text-align: center; border: 2px solid #ec4899;">
                <h3 style="margin: 0 0 15px 0; color: #ec4899; font-size: 24px;">✨ Cuenta creada, {nombre}!</h3>
                <p style="margin: 0; color: #e5e7eb; font-size: 16px;">
                    Tu cuenta ha sido registrada exitosamente. <br>
                    Ahora tus conversaciones se guardarán permanentemente.
                </p>
                <div style="margin-top: 15px; font-size: 12px; color: #9ca3af;">
                    Email: {email} • Fecha: {datetime.now().strftime('%d/%m/%Y')}
                </div>
            </div>
            """
            
            return mensaje_bienvenida, resultado, gr.update(visible=False), gr.update(visible=True), obtener_panel_usuario_avanzado(resultado), []
        
        return resultado, None, gr.update(visible=True), gr.update(visible=False), obtener_panel_usuario_avanzado(None), []
    
    def handle_login_completo(email: str):
        if not email:
            return "❌ Ingresa tu email", None, gr.update(visible=True), gr.update(visible=False), obtener_panel_usuario_avanzado(None), []
        
        success, resultado = sistema_auth.iniciar_sesion(email)
        if success:
            datos_sesion = sistema_auth.obtener_datos_sesion(resultado)
            datos_usuario = db.obtener_datos_usuario(email)
            
            # Cargar historial de conversaciones
            historial = db.obtener_ultimas_conversaciones(email, limite=20)
            
            mensaje_bienvenida = f"""
            <div style="background: linear-gradient(135deg, rgba(236, 72, 153, 0.2), rgba(168, 85, 247, 0.2)); padding: 25px; border-radius: 15px; text-align: center; border: 2px solid #ec4899;">
                <h3 style="margin: 0 0 15px 0; color: #ec4899; font-size: 24px;">✨ Bienvenido de vuelta, {datos_usuario['nombre']}!</h3>
                <p style="margin: 0; color: #e5e7eb; font-size: 16px;">
                    Has iniciado sesión correctamente. <br>
                    {len(historial)} mensajes anteriores cargados.
                </p>
                <div style="margin-top: 15px; font-size: 12px; color: #9ca3af;">
                    Última visita: {datos_usuario.get('ultima_visita', 'Primera vez')} • Confianza: {datos_usuario['confianza']}%
                </div>
            </div>
            """
            
            return mensaje_bienvenida, resultado, gr.update(visible=False), gr.update(visible=True), obtener_panel_usuario_avanzado(resultado), historial
        
        return resultado, None, gr.update(visible=True), gr.update(visible=False), obtener_panel_usuario_avanzado(None), []
    
    def handle_chat_con_login(mensaje: str, historial, sesion_id: str):
        if not sesion_id or not mensaje.strip():
            return "", historial, obtener_panel_estado_avanzado()
        
        if not sistema_auth.verificar_sesion(sesion_id):
            return "", historial, obtener_panel_estado_avanzado()
        
        datos_sesion = sistema_auth.obtener_datos_sesion(sesion_id)
        respuesta = generar_respuesta_avanzada(mensaje, datos_sesion['email'], sesion_id)
        nuevo_historial = historial + [[mensaje, respuesta]]
        
        return "", nuevo_historial, obtener_panel_estado_avanzado()
    
    def handle_logout_completo(sesion_id: str):
        if sesion_id:
            sistema_auth.cerrar_sesion(sesion_id)
        
        return None, gr.update(visible=True), gr.update(visible=False), obtener_panel_usuario_avanzado(None), []
    
    # ==================== CONEXIÓN DE EVENTOS ====================
    btn_registro.click(
        handle_registro_completo,
        [nombre_registro, email_registro],
        [status_login, sesion_state, login_screen, chat_screen, user_info_display, chatbot]
    )
    
    btn_login.click(
        handle_login_completo,
        [email_login],
        [status_login, sesion_state, login_screen, chat_screen, user_info_display, chatbot]
    )
    
    enviar.click(
        handle_chat_con_login,
        [msg, chatbot, sesion_state],
        [msg, chatbot, estado_display]
    )
    
    msg.submit(
        handle_chat_con_login,
        [msg, chatbot, sesion_state],
        [msg, chatbot, estado_display]
    )
    
    btn_salir.click(
        handle_logout_completo,
        inputs=[sesion_state],
        outputs=[sesion_state, login_screen, chat_screen, user_info_display, chatbot]
    )
    
    btn_limpiar.click(
        fn=lambda: [],
        outputs=[chatbot]
    )

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)
