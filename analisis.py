import pandas as pd
import datetime
import os

# Nombre del archivo que funcionará como tu base de datos
ARCHIVO = "mis_finanzas.csv"

def guardar_movimiento(tipo, categoria, monto, metodo, comentarios):
    # Definimos la estructura del nuevo registro
    nuevo_registro = {
        'Fecha': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Tipo': tipo,
        'Categoria': categoria,
        'Monto': float(monto),
        'Metodo': metodo,
        'Comentarios': comentarios
    }
    
    # Si el archivo no existe, lo creamos
    if not os.path.exists(ARCHIVO):
        df = pd.DataFrame([nuevo_registro])
        df.to_csv(ARCHIVO, index=False)
    else:
        # Si ya existe, leemos, agregamos y guardamos
        df = pd.read_csv(ARCHIVO)
        df = pd.concat([df, pd.DataFrame([nuevo_registro])], ignore_index=True)
        df.to_csv(ARCHIVO, index=False)
    
    return True

