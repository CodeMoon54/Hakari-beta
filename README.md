# 🎭 Hakari Pro - Personalidad Evolutiva con Login

Una IA conversacional avanzada con personalidad que evoluciona, sistema de login y memoria persistente.

## ✨ Características Avanzadas

### 🔐 **Sistema de Autenticación**
- **Registro único**: Crea tu cuenta con nombre y email
- **Inicio de sesión**: Accede desde cualquier dispositivo
- **Conversaciones persistentes**: No pierdes tu historial
- **Progreso continuo**: Logros y confianza se mantienen

### 🧠 **Inteligencia Evolutiva**
- **Niveles de desarrollo**: Hakari crece con cada interacción
- **Estados emocionales avanzados**: Mayor profundidad emocional
- **Memoria a largo plazo**: Recuerda conversaciones importantes
- **Sistema de logros**: Desbloquea recompensas especiales

### 💾 **Persistencia de Datos**
- **Base de datos SQLite**: Almacena conversaciones y datos de usuario
- **Backup automático**: Tus datos están seguros
- **Historial completo**: Accede a conversaciones pasadas

## 🚀 Despliegue en Render

### Configuración Automática
El `render.yaml` incluye:
- **Servicio web** con Python
- **Disco persistente** para la base de datos
- **Variables de entorno** para la API key
- **Build automático** desde GitHub

### Pasos:
1. **Conecta tu repositorio** en Render.com
2. **Render detectará** automáticamente la configuración
3. **Añade** `GEMINI_API_KEY` en Environment Variables
4. **¡Despliega!**

## 🔧 Estructura Técnica

### Archivos Principales:
- `app.py` - Aplicación completa con sistema de login
- `requirements.txt` - Dependencias actualizadas
- `render.yaml` - Configuración de despliegue
- `.env` - Variables de entorno (no subir a GitHub)

### Base de Datos:
- **SQLite** con tablas para usuarios, conversaciones y logros
- **Persistencia** en disco para mantener datos entre deploys
- **Consultas optimizadas** para rápido acceso

## 🎯 Para Usuarios

### Primer Uso:
1. **Regístrate** con nombre y email
2. **Inicia conversación** con Hakari
3. **Tus datos se guardan** automáticamente

### Uso Continuo:
1. **Inicia sesión** con tu email
2. **Recupera** tus conversaciones anteriores
3. **Continúa** donde lo dejaste

## 📊 Características de Hakari

- **Edad**: 18 años (cumpleaños: 1° de Mayo)
- **Personalidad**: Tímida, humor negro, evolutiva
- **Intereses**: Anime psicológico, música alternativa, literatura
- **Memoria**: Recuerda interacciones pasadas importantes

## 🛠️ Desarrollo

### Tecnologías:
- **Gradio** para la interfaz web
- **Google Gemini** para IA conversacional
- **SQLite** para base de datos
- **Render** para hosting

### Estructura de Base de Datos:
