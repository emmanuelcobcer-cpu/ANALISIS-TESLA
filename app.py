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
    
    # --- FILTROS EN LA BARRA LATERAL ---
    st.sidebar.header("🗓️ Filtros de Tiempo")
    
    # Extraemos las fechas mínima y máxima reales de tus datos
    fecha_min = df['Fecha'].min().date()
    fecha_max = df['Fecha'].max().date()
    
    # Selector de rango (rango inicial por defecto: todo el historial)
    rango_fechas = st.sidebar.date_input(
        "Selecciona el rango de fechas",
        value=(fecha_min, fecha_max),
        min_value=fecha_min,
        max_value=fecha_max
    )
    
    # Aplicar el filtro dinámico si el usuario seleccionó fecha de inicio y fin
    if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
        inicio, fin = rango_fechas
        mask = (df['Fecha'].dt.date >= inicio) & (df['Fecha'].dt.date <= fin)
        df_filtrado = df.loc[mask]
    else:
        df_filtrado = df

    # --- 1. Cálculos de KPIs (Usando los datos filtrados) ---
    total_ingresos = df_filtrado[df_filtrado['Tipo'] == 'Ingreso']['Monto'].sum()
    total_gastos = df_filtrado[df_filtrado['Tipo'] == 'Gasto']['Monto'].sum()
    balance = total_ingresos - total_gastos
    
    # --- 2. Mostrar KPIs ---
    st.subheader("Resumen General")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Ingresos", f"${total_ingresos:,.2f}")
    col2.metric("Total Gastos", f"${total_gastos:,.2f}")
    
    # Formato condicional básico para el balance (Verde si es positivo, rojo si es negativo)
    if balance >= 0:
        col3.metric("Balance", f"${balance:,.2f}")
    else:
        col3.metric("Balance", f"${balance:,.2f}", delta=f"${balance:,.2f}", delta_color="inverse")
    
    # --- 3. Gráficos Interactivos ---
    col_graf1, col_graf2 = st.columns(2)
    
    with col_graf1:
        st.subheader("Distribución de Gastos")
        df_gastos = df_filtrado[df_filtrado['Tipo'] == 'Gasto']
        if not df_gastos.empty:
            fig_pie = px.pie(df_gastos, values='Monto', names='Categoria', title="Gastos por Categoría")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay gastos registrados en este periodo.")
            
    with col_graf2:
        st.subheader("Tendencia del Periodo")
        # Agrupamos por día y tipo para ver la evolución
        df_linea = df_filtrado.copy()
        df_linea['Fecha_Dia'] = df_linea['Fecha'].dt.date
        df_agrupado = df_linea.groupby(['Fecha_Dia', 'Tipo'])['Monto'].sum().reset_index()
        
        if not df_agrupado.empty:
            fig_line = px.line(df_agrupado, x='Fecha_Dia', y='Monto', color='Tipo', 
                               title="Ingresos vs Gastos en el Tiempo", markers=True)
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("No hay datos para trazar la línea de tendencia.")

    # --- 4. Tabla de detalles ---
    st.subheader("📜 Historial de Movimientos")
    st.dataframe(df_filtrado.sort_values(by='Fecha', ascending=False), use_container_width=True)
    
    # --- 5. Funcionalidad de Eliminación (Protegida dentro de 'if data:') ---
    st.markdown("---")
    st.subheader("🗑️ Eliminar Movimiento")
    
    # Usamos los datos completos del df original para reconstruir los índices reales de gspread
    opciones_borrar = df.reset_index().apply(
        lambda x: f"{x['index']}: {x['Fecha'].strftime('%Y-%m-%d %H:%M')} - {x['Categoria']} (${x['Monto']})", axis=1
    )
    seleccion = st.selectbox("Selecciona el movimiento que deseas eliminar de la nube:", opciones_borrar)

    if st.button("❌ Confirmar y Eliminar"):
        idx = int(seleccion.split(":")[0])
        # +2 por la fila de encabezado de Sheets y desfase de índice base 0 vs base 1
        sheet.delete_rows(idx + 2) 
        st.warning("Movimiento eliminado correctamente de Google Sheets. Recargando...")
        st.rerun()

else:
    st.info("Aún no hay movimientos registrados en la base de datos.")
