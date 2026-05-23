import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Configuración de Google Sheets ---
def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # Nombre de tu hoja de cálculo
    return client.open("MisFinanzas").sheet1

def guardar_movimiento(tipo, categoria, monto, metodo, comentarios):
    sheet = conectar_gsheets()
    fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([fecha, tipo, categoria, float(monto), metodo, comentarios])
    return True

# --- Interfaz Visual ---
st.set_page_config(page_title="Control de Finanzas", layout="wide")
st.title("💰 Control de Finanzas Personales")

with st.expander("➕ Agregar nuevo movimiento"):
    with st.form("nuevo_movimiento"):
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox("Tipo", ["Ingreso", "Gasto"])
            categoria = st.selectbox("Categoría", ["Alimentación", "Transporte", "Vivienda", "Salud", "Ocio", "Otros"])
        with col2:
            monto = st.number_input("Monto", min_value=0.0, step=0.01)
            metodo = st.selectbox("Método de Pago", ["Efectivo", "Tarjeta", "Transferencia"])
        
        comentarios = st.text_area("Comentarios (Opcional)")
        submit = st.form_submit_button("Guardar Movimiento")

if submit:
    if categoria and monto > 0:
        guardar_movimiento(tipo, categoria, monto, metodo, comentarios)
        st.success("¡Registro guardado en la nube!")
        st.rerun()
    else:
        st.error("Por favor, ingresa una categoría y un monto válido.")

# --- Dashboard desde Google Sheets ---
st.divider()
sheet = conectar_gsheets()
data = sheet.get_all_records()

if data:
    df = pd.DataFrame(data)
    # Aseguramos que la columna Fecha sea tipo datetime
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    
    # 1. Cálculos de KPIs
    total_ingresos = df[df['Tipo'] == 'Ingreso']['Monto'].sum()
    total_gastos = df[df['Tipo'] == 'Gasto']['Monto'].sum()
    balance = total_ingresos - total_gastos
    
    # 2. Mostrar KPIs
    st.subheader("Resumen General")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Ingresos", f"${total_ingresos:,.2f}")
    col2.metric("Total Gastos", f"${total_gastos:,.2f}")
    col3.metric("Balance", f"${balance:,.2f}")
    
    # 3. Gráfico de Pastel (Distribución de gastos)
    st.subheader("Distribución de Gastos")
    df_gastos = df[df['Tipo'] == 'Gasto']
    if not df_gastos.empty:
        fig = px.pie(df_gastos, values='Monto', names='Categoria', title="Gastos por Categoría")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aún no hay gastos registrados para graficar.")

    # 4. Tabla de detalles
    st.subheader("Historial de Movimientos")
    st.dataframe(df.sort_values(by='Fecha', ascending=False), use_container_width=True)
    # --- Funcionalidad de Eliminación ---
st.subheader("🗑️ Eliminar Movimiento")
# Creamos una lista de los movimientos para seleccionar cuál borrar
opciones_borrar = df.reset_index().apply(lambda x: f"{x['index']}: {x['Fecha']} - {x['Categoria']} (${x['Monto']})", axis=1)
seleccion = st.selectbox("Selecciona el movimiento a borrar", opciones_borrar)

if st.button("Eliminar seleccionado"):
    # Obtenemos el índice (el número que sale al principio de la fila)
    idx = int(seleccion.split(":")[0])
    # +2 porque Google Sheets tiene fila de encabezado (1) y los índices de gspread empiezan en 1
    sheet.delete_rows(idx + 2) 
    st.warning("Movimiento eliminado. Recargando...")
    st.rerun()

else:
    st.info("Aún no hay movimientos registrados.")
