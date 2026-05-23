import os
import datetime
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fpdf import FPDF
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import json

def generar_enviar_reporte():
    print("Iniciando proceso de reporte mensual...")
    
    # 1. Conexión a Google Sheets usando variables de entorno de GitHub
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(os.environ["GCP_SERVICE_ACCOUNT"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("MisFinanzas").sheet1
    
    data = sheet.get_all_records()
    if not data:
        print("No hay datos en la hoja.")
        return

    # 2. Filtrar datos del mes actual
    df = pd.DataFrame(data)
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    
    hoy = datetime.datetime.now()
    # Filtramos movimientos del año y mes corriente
    df_mes = df[(df['Fecha'].dt.year == hoy.year) & (df['Fecha'].dt.month == hoy.month)]
    
    if df_mes.empty:
        print("No hay movimientos registrados en este mes.")
        return

    # 3. Cálculos Financieros
    total_ingresos = df_mes[df_mes['Tipo'] == 'Ingreso']['Monto'].sum()
    total_gastos = df_mes[df_mes['Tipo'] == 'Gasto']['Monto'].sum()
    balance = total_ingresos - total_gastos
    tasa_ahorro = ((total_ingresos - total_gastos) / total_ingresos * 100) if total_ingresos > 0 else 0.0
    
    dias_mes = hoy.day
    gasto_diario = total_gastos / dias_mes

    # Gastos por categoría ordenados de mayor a menor
    df_gastos = df_mes[df_mes['Tipo'] == 'Gasto'].groupby('Categoria')['Monto'].sum().reset_index()
    df_gastos = df_gastos.sort_values(by='Monto', ascending=False)

    # 4. Construcción del PDF Elegante
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    
    # Encabezado Ejecutivo
    pdf.set_fill_color(30, 41, 59) # Azul Pizarra #1e293b
    pdf.rect(0, 0, 210, 40, "F")
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "REPORTE FINANCIERO EJECUTIVO", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    mes_nombre = hoy.strftime('%B %Y').upper()
    pdf.cell(0, 5, f"CIERRE MENSUAL: {mes_nombre}", ln=True, align="C")
    
    pdf.ln(20)
    pdf.set_text_color(30, 41, 59)
    
    # Grid de KPIs principales
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "1. Resumen de Estado de Resultados", ln=True)
    pdf.set_font("Helvetica", "", 10)
    
    # Fila de métricas
    pdf.cell(45, 10, f"Total Ingresos: ${total_ingresos:,.2f}", border=1, align="C")
    pdf.cell(5, 10, "") # Espacio
    pdf.cell(45, 10, f"Total Gastos: ${total_gastos:,.2f}", border=1, align="C")
    pdf.cell(5, 10, "")
    pdf.cell(45, 10, f"Balance Neto: ${balance:,.2f}", border=1, align="C")
    pdf.cell(5, 10, "")
    pdf.cell(35, 10, f"Tasa Ahorro: {tasa_ahorro:.1f}%", border=1, align="C")
    pdf.ln(15)

    # Análisis de eficiencia
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "2. Analitica de Flujo de Caja", ln=True)
    pdf.set_font("Helvetica", "", 10.5)
    
    salud_msg = "SUPERAVITARIO" if balance >= 0 else "DEFICITARIO"
    analisis_texto = (
        f"Durante el periodo correspondiente a {hoy.strftime('%B')}, el sistema registro un comportamiento {salud_msg}. "
        f"El indice de gasto promedio diario se situo en ${gasto_diario:,.2f} por jornada. "
        f"Se logro una retencion neta de capital del {tasa_ahorro:.1f}% sobre el total de los ingresos percibidos."
    )
    pdf.multi_cell(0, 6, analisis_texto)
    pdf.ln(10)

    # Tabla de Distribución de Gastos
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "3. Distribucion Detallada de Egresos", ln=True)
    pdf.ln(2)
    
    # Encabezados de Tabla
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(241, 245, 249) # Gris sutil
    pdf.cell(90, 8, " Categoria de Gasto", border=1, fill=True)
    pdf.cell(90, 8, " Monto Consolidado ($)", border=1, fill=True, align="R")
    pdf.ln(8)
    
    pdf.set_font("Helvetica", "", 10)
    for _, row in df_gastos.iterrows():
        pdf.cell(90, 8, f" {row['Categoria']}", border=1)
        pdf.cell(90, 8, f"${row['Monto']:,.2f} ", border=1, align="R")
        pdf.ln(8)
        
    # Guardar archivo temporal
    pdf_filename = f"Reporte_Financiero_{hoy.strftime('%Y_%m')}.pdf"
    pdf.output(pdf_filename)
    print("PDF generado con exito.")

    # 5. Envío Automatizado por Correo Electrónico (SMTP)
    remitente = os.environ["CORREO_REMITENTE"]
    destinatario = os.environ["CORREO_DESTINATARIO"]
    password = os.environ["CORREO_PASSWORD"] # Contraseña de aplicación de Gmail

    msg = MIMEMultipart()
    msg['From'] = remitente
    msg['To'] = destinatario
    msg['Subject'] = f"📊 Cierre Financiero Mensual Consolidado - {hoy.strftime('%B %Y')}"

    cuerpo = f"Hola,\n\nAdjunto encontraras el Reporte Financiero Ejecutivo automatizado correspondiente al cierre del mes de {hoy.strftime('%B %Y')}.\n\nSaludos,\nTu Sistema Automatizado de Finanzas."
    msg.attach(MIMEText(cuerpo, 'plain'))

    # Adjuntar el archivo PDF
    with open(pdf_filename, "rb") as adjunto:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(adjunto.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename= {pdf_filename}")
        msg.attach(part)

    # Conexión segura con el servidor de Gmail
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(remitente, password)
    server.sendmail(remitente, destinatario, msg.as_string())
    server.quit()
    print("Reporte enviado con éxito al correo electrónico.")

if __name__ == "__main__":
    generar_enviar_reporte()
