#pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib pandas python-dotenv

from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

# Construimos el diccionario de credenciales
'''
creds_dict = {
    "type": os.getenv("GOOGLE_SHEETS_TYPE"),
    "project_id": os.getenv("GOOGLE_SHEETS_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_SHEETS_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_SHEETS_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.getenv("GOOGLE_SHEETS_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_SHEETS_CLIENT_ID"),
    "auth_uri": os.getenv("GOOGLE_SHEETS_AUTH_URI"),
    "token_uri": os.getenv("GOOGLE_SHEETS_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("GOOGLE_SHEETS_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("GOOGLE_SHEETS_CLIENT_X509_CERT_URL"),
    "universe_domain": "googleapis.com"
}
'''
creds_dict = {
    "type": st.secrets["GOOGLE_SHEETS_TYPE"],
    "project_id": st.secrets["GOOGLE_SHEETS_PROJECT_ID"],
    "private_key_id": st.secrets["GOOGLE_SHEETS_PRIVATE_KEY_ID"],
    "private_key": st.secrets["GOOGLE_SHEETS_PRIVATE_KEY"].replace('\\n', '\n'),
    "client_email": st.secrets["GOOGLE_SHEETS_CLIENT_EMAIL"],
    "client_id": st.secrets["GOOGLE_SHEETS_CLIENT_ID"],
    "auth_uri": st.secrets["GOOGLE_SHEETS_AUTH_URI"],
    "token_uri": st.secrets["GOOGLE_SHEETS_TOKEN_URI"],
    "auth_provider_x509_cert_url": st.secrets["GOOGLE_SHEETS_AUTH_PROVIDER_X509_CERT_URL"],
    "client_x509_cert_url": st.secrets["GOOGLE_SHEETS_CLIENT_X509_CERT_URL"],
    "universe_domain": "googleapis.com"
}

# Definir el scope
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Nueva forma de autenticar (Recomendada)
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# Abrir la hoja de cálculo usando el ID y el nombre de la pestaña
#spreadsheet = client.open_by_key(os.getenv("SPREADSHEET_ID"))
spreadsheet = client.open_by_key(st.secrets["SPREADSHEET_ID"])


def extraer_Datos(hoja):

    """
    Envía una petición a la API de Google Cloud para extraer datos sobre una hoja.

    Parámetros:
        hoja (str): se debe indicar el nombre de la hoja y el rango inicial y final, por
                                    Ejemplo: Citas

    Retorna:
        df: dataframe con los datos en la hoja de calculo y Respuesta 'Datos Extraidos con Exito' o mensaje de error.
    """
    sheet = spreadsheet.worksheet(f"{hoja}")
    try:
        # Extraemos los datos de la hoja de calculo
        data = sheet.get_all_values() # Trae todo como una lista de listas
        
        # Creamos el DataFrame: la primera fila son las cabeceras
        df = pd.DataFrame(data[1:], columns=data[0]) 

        print(f"\nDatos Extraidos de {hoja} con Exito")
        return df
    except Exception as e:
        print(f"\nOcurrió un error al intentar extraer los datos de {hoja}:\n {e}")
        return None

def cargar_datos(nombre_hoja, df):
    """
    Limpia la hoja de cálculo desde A2 hacia abajo y carga un DataFrame.
    
    Parámetros:
    - nombre_hoja (str): El nombre de la pestaña.
    - df (pd.DataFrame): El DataFrame con la información a subir.
    """
    try:
        sheet = spreadsheet.worksheet(nombre_hoja)
        
        # 1. Obtener el número total de filas para saber qué borrar
        # Si la hoja está vacía (solo encabezados), esto evita errores.
        num_filas = sheet.row_count
        
        if num_filas > 1:
            # Borramos desde la fila 2 hasta el final de la hoja
            # 'A2:Z' limpiará todas las columnas hasta la última fila existente
            sheet.batch_clear([f'A2:R{num_filas}'])
            print("\nDatos antiguos eliminados (encabezados preservados).")

        # 2. Preparar los datos del DataFrame para gspread
        # Convertimos NaN a strings vacíos para evitar errores de JSON y pasamos a lista
        valores = df.fillna("").values.tolist()

        # 3. Insertar los datos empezando en A2
        if valores:
            sheet.update(range_name='A2', values=valores)
            print(f"\nÉxito: Se han cargado {len(valores)} filas en '{nombre_hoja}'.")
        else:
            print("\nEl DataFrame está vacío, no hay datos para cargar.")

    except Exception as e:
        print(f"\nOcurrió un error al intentar cargar los datos:\n {e}")

def limpiar_datos_hoja(nombre_hoja):
    """
    Borra todo el contenido de la hoja a partir de la fila A2.
    """
    try:
        sheet = spreadsheet.worksheet(nombre_hoja)
        # Obtenemos el número total de filas actuales para definir el rango
        num_filas = sheet.row_count
        
        if num_filas > 1:
            # Borramos desde A2 hasta la última columna (Z) y última fila
            sheet.batch_clear([f'A2:R{num_filas}'])
            print(f"\nHoja '{nombre_hoja}' limpiada correctamente.")
    except Exception as e:
        print(f"\nError al intentar limpiar la hoja: {e}")

def actualizar():
    """
    FUNCION PRINCIPAL: Orquesta la extracción, procesamiento, carga y limpieza de datos entre las hojas "Ordenes" y "Ordenes_Recientes".
    Retorna el Dataframe con los datos de las ordenas de compras
    """
    try:
        # 1. Extracción
        df1 = extraer_Datos("Ordenes")
        df2 = extraer_Datos("Ordenes_Recientes")

        # 2. Procesamiento
        # Concatenamos poniendo df2 primero para que 'keep=first' mantenga lo nuevo si hay choques
        df = pd.concat([df2, df1], ignore_index=True)
        df = df.drop_duplicates(keep='first')

        # 3. Carga
        cargar_datos("Ordenes", df)
        
        # 4. Acción posterior (Solo se ejecuta si lo anterior no dio error)
        limpiar_datos_hoja("Ordenes_Recientes")
        print("\nProceso completado: Datos integrados y hoja reciente limpiada.")

        return df

    except Exception as e:
        print(f"Error detectado: {e}")
        print("La limpieza de 'Ordenes_Recientes' se canceló para evitar pérdida de datos.")

