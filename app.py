import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN DE SEGURIDAD (LOGIN) ---
def check_password():
    """Devuelve True si el usuario ingresó las credenciales correctas."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return True

    # Pantalla de Login limpia y minimalista
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso al Sistema Financiero</h2>", unsafe_allow_html=True)
    st.write("---")
    
    col_login, _ = st.columns([1, 1])
    with col_login:
        user_input = st.text_input("Usuario", key="username")
        password_input = st.text_input("Contraseña", type="password", key="password")
        btn_login = st.button("Iniciar Sesión")

    if btn_login:
        # Validar contra los secrets de Streamlit
        if (user_input == st.secrets["credentials"]["usuario"] and 
            password_input == st.secrets["credentials"]["password"]):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("❌ Usuario o contraseña incorrectos")
            
    return False

# Si no está autenticado, detiene la ejecución de la app aquí
if not check_password():
    st.stop()

# --- BOTÓN DE CERRAR SESIÓN EN LA BARRA LATERAL ---
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state["authenticated"] = False
    st.rerun()
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

# Estilos globales de CSS para limpiar márgenes y mejorar fuentes
st.markdown("""
    <style>
    .reportview-container .main .block-container{ padding-top: 2rem; }
    div.stButton > button:first-child {
        background-color: #2e7d32;
        color: white;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

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
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    
    # --- FILTROS EN LA BARRA LATERAL ---
    st.sidebar.header("🔍 Filtros Avanzados")
    
    fecha_min = df['Fecha'].min().date()
    fecha_max = df['Fecha'].max().date()
    
    rango_fechas = st.sidebar.date_input(
        "Selecciona el rango de fechas",
        value=(fecha_min, fecha_max),
        min_value=fecha_min,
        max_value=fecha_max
    )
    
    categorias_disponibles = sorted(df['Categoria'].unique().tolist())
    categorias_seleccionadas = st.sidebar.multiselect(
        "Filtrar por Categoría",
        options=categorias_disponibles,
        default=categorias_disponibles
    )
    
    metodos_disponibles = sorted(df['Metodo'].unique().tolist())
    metodos_seleccionados = st.sidebar.multiselect(
        "Filtrar por Método de Pago",
        options=metodos_disponibles,
        default=metodos_disponibles
    )
    
    # Meta de Presupuesto Mensual configurable desde la barra lateral
    PRESUPUESTO_MENSUAL = st.sidebar.number_input("🎯 Meta Gasto Mensual ($)", min_value=1000.0, value=16000.0, step=500.0)
    
    # --- APLICAR TODOS LOS FILTROS SIMULTÁNEAMENTE ---
    if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
        inicio, fin = rango_fechas
        mask = (df['Fecha'].dt.date >= inicio) & (df['Fecha'].dt.date <= fin)
        df_filtrado = df.loc[mask]
        dias_del_periodo = max((fin - inicio).days, 1)
    else:
        df_filtrado = df
        dias_del_periodo = 1
        
    df_filtrado = df_filtrado[
        df_filtrado['Categoria'].isin(categorias_seleccionadas) & 
        df_filtrado['Metodo'].isin(metodos_seleccionados)
    ]

    # --- 1. Cálculos de KPIs ---
    total_ingresos = df_filtrado[df_filtrado['Tipo'] == 'Ingreso']['Monto'].sum()
    total_gastos = df_filtrado[df_filtrado['Tipo'] == 'Gasto']['Monto'].sum()
    balance = total_ingresos - total_gastos
    
    tasa_ahorro = 0.0
    if total_ingresos > 0:
        tasa_ahorro = ((total_ingresos - total_gastos) / total_ingresos) * 100
        
    gasto_diario = total_gastos / dias_del_periodo

    if balance >= 0:
        color_balance_bg = "#e8f5e9"
        color_balance_txt = "#2e7d32"
    else:
        color_balance_bg = "#ffebee"
        color_balance_txt = "#c62828"
    
    # --- 2. Mostrar KPIs Premium ---
    st.subheader("📊 Resumen General")
    
    kpi_html = f"""
    <div style="display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 10px;">
        <div style="flex: 1; min-width: 200px; background-color: #f8f9fa; border-left: 5px solid #1565c0; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p style="margin:0; font-size: 14px; color: #6c757d; font-weight: bold; text-transform: uppercase;">Total Ingresos</p>
            <h2 style="margin:5px 0 0 0; color: #1565c0; font-size: 26px;">${total_ingresos:,.2f}</h2>
        </div>
        <div style="flex: 1; min-width: 200px; background-color: #f8f9fa; border-left: 5px solid #d32f2f; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p style="margin:0; font-size: 14px; color: #6c757d; font-weight: bold; text-transform: uppercase;">Total Gastos</p>
            <h2 style="margin:5px 0 0 0; color: #d32f2f; font-size: 26px;">${total_gastos:,.2f}</h2>
        </div>
        <div style="flex: 1; min-width: 200px; background-color: {color_balance_bg}; border-left: 5px solid {color_balance_txt}; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p style="margin:0; font-size: 14px; color: #6c757d; font-weight: bold; text-transform: uppercase;">Balance Neto</p>
            <h2 style="margin:5px 0 0 0; color: {color_balance_txt}; font-size: 26px;">${balance:,.2f}</h2>
        </div>
        <div style="flex: 1; min-width: 200px; background-color: #f8f9fa; border-left: 5px solid #ef6c00; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p style="margin:0; font-size: 14px; color: #6c757d; font-weight: bold; text-transform: uppercase;">Tasa de Ahorro</p>
            <h2 style="margin:5px 0 0 0; color: #ef6c00; font-size: 26px;">{tasa_ahorro:.1f}%</h2>
        </div>
        <div style="flex: 1; min-width: 200px; background-color: #f8f9fa; border-left: 5px solid #7e57c2; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p style="margin:0; font-size: 14px; color: #6c757d; font-weight: bold; text-transform: uppercase;">Gasto Promedio Diario</p>
            <h2 style="margin:5px 0 0 0; color: #7e57c2; font-size: 26px;">${gasto_diario:,.2f}</h2>
        </div>
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)
    
    # --- CONTROL DE PRESUPUESTO ---
    porcentaje_gasto = min((total_gastos / PRESUPUESTO_MENSUAL) * 100, 100.0)
    color_barra = "#d32f2f" if porcentaje_gasto >= 90 else "#ef6c00" if porcentaje_gasto >= 70 else "#2e7d32"
    
    st.markdown(f"""
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 14px; font-weight: bold; color: #495057;">
                <span>🎯 Estado del Presupuesto Mensual</span>
                <span>${total_gastos:,.2f} / ${PRESUPUESTO_MENSUAL:,.2f} ({porcentaje_gasto:.1f}%)</span>
            </div>
            <div style="background-color: #e9ecef; border-radius: 4px; height: 12px; width: 100%; overflow: hidden;">
                <div style="background-color: {color_barra}; height: 100%; width: {porcentaje_gasto}%; border-radius: 4px; transition: width 0.5s ease;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # --- 3. Gráficos Interactivos (Fila 1) ---
    st.subheader("📈 Análisis de Distribución y Tendencias")
    col_graf1, col_graf2 = st.columns(2)
    
    df_gastos = df_filtrado[df_filtrado['Tipo'] == 'Gasto']
    
    with col_graf1:
        st.write("**Proporción de Gastos**")
        if not df_gastos.empty:
            fig_pie = px.pie(df_gastos, values='Monto', names='Categoria', 
                             color_discrete_sequence=px.colors.qualitative.Safe)
            fig_pie.update_layout(margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay gastos registrados para este periodo.")
            
    with col_graf2:
        st.write("**Evolución Diaria**")
        df_linea = df_filtrado.copy()
        df_linea['Fecha_Dia'] = df_linea['Fecha'].dt.date
        df_agrupado = df_linea.groupby(['Fecha_Dia', 'Tipo'])['Monto'].sum().reset_index()
        
        if not df_agrupado.empty:
            fig_line = px.line(df_agrupado, x='Fecha_Dia', y='Monto', color='Tipo',
                               color_discrete_map={'Ingreso': '#1565c0', 'Gasto': '#d32f2f'},
                               markers=True)
            fig_line.update_layout(margin=dict(t=10, b=10, l=10, r=10), xaxis_title=None, yaxis_title="Monto ($)")
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("No hay datos suficientes para trazar la tendencia.")

    # --- Gráficos Interactivos (Fila 2) ---
    col_graf3, col_graf4 = st.columns(2)
    
    with col_graf3:
        st.write("**Ranking de Gastos (Mayor a Menor)**")
        if not df_gastos.empty:
            df_bar_cat = df_gastos.groupby('Categoria')['Monto'].sum().reset_index()
            df_bar_cat = df_bar_cat.sort_values(by='Monto', ascending=True)
            
            fig_bar_h = px.bar(df_bar_cat, x='Monto', y='Categoria', orientation='h',
                               labels={'Monto': 'Total Gastado ($)', 'Categoria': 'Categoría'},
                               color='Monto', color_continuous_scale='Reds')
            fig_bar_h.update_layout(margin=dict(t=10, b=10, l=10, r=10), coloraxis_showscale=False)
            st.plotly_chart(fig_bar_h, use_container_width=True)
        else:
            st.info("No hay gastos registrados para generar el ranking.")
            
    with col_graf4:
        st.write("**Comparativa Mensual (Ingresos vs Gastos)**")
        df_mensual = df_filtrado.copy()
        df_mensual['Mes'] = df_mensual['Fecha'].dt.strftime('%Y-%m')
        df_bars_m = df_mensual.groupby(['Mes', 'Tipo'])['Monto'].sum().reset_index()
        
        if not df_bars_m.empty:
            fig_bar_v = px.bar(df_bars_m, x='Mes', y='Monto', color='Tipo', barmode='group',
                               color_discrete_map={'Ingreso': '#1565c0', 'Gasto': '#d32f2f'},
                               labels={'Monto': 'Monto Total ($)', 'Mes': 'Mes'})
            fig_bar_v.update_layout(margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig_bar_v, use_container_width=True)
        else:
            st.info("No hay datos suficientes para la comparativa mensual.")

    # --- 4. Tabla de detalles ---
    st.subheader("📜 Historial de Movimientos")
    st.dataframe(df_filtrado.sort_values(by='Fecha', ascending=False), use_container_width=True)
    
    # Botón de descarga de datos justo debajo de la tabla
    csv = df_filtrado.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Descargar datos filtrados (CSV)",
        data=csv,
        file_name='MisFinanzas_Filtrado.csv',
        mime='text/csv',
    )
    
    # --- 5. Funcionalidad de Eliminación ---
    st.markdown("---")
    st.subheader("🗑️ Eliminar Movimiento")
    
    opciones_borrar = df.reset_index().apply(
        lambda x: f"{x['index']}: {x['Fecha'].strftime('%Y-%m-%d %H:%M')} - {x['Categoria']} (${x['Monto']})", axis=1
    )
    seleccion = st.selectbox("Selecciona el movimiento que deseas eliminar de la nube:", opciones_borrar)

    if st.button("❌ Confirmar y Eliminar"):
        idx = int(seleccion.split(":")[0])
        sheet.delete_rows(idx + 2) 
        st.warning("Movimiento eliminado correctamente de Google Sheets. Recargando...")
        st.rerun()

else:
    st.info("Aún no hay movimientos registrados en la base de datos.")
