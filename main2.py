"""
Dashboard de Análisis de Ventas E-commerce
============================================
Fuente de datos: Google Sheets (via drive.py -> actualizar())
Ejecutar con: streamlit run main.py
"""

from drive import actualizar
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from itertools import combinations
from collections import Counter

# ─── CONFIGURACIÓN DE PÁGINA ───────────────────────────────────────────────────
st.set_page_config(page_title="Dashboard de Minería E-commerce", layout="wide")
st.title("📊 Análisis de Ventas y Minería de Datos")
st.markdown("Datos cargados automáticamente.")

# ─── CARGA DE DATOS ─────────────────────────────────────────────────────────────
df_raw = actualizar()

if df_raw is None:
    st.warning("⚠️ No se pudieron cargar los datos. Verifica la conexión.")
    st.stop()  # Detiene la ejecución limpiamente si no hay datos

######################################################################################
# FASE 1: LIMPIEZA Y PREPROCESAMIENTO
######################################################################################

# Limpiar espacios en blanco de nombres de columnas
df_raw.columns = [c.strip() for c in df_raw.columns]

# --- Forward Fill de campos del encabezado del pedido ---
# Los pedidos con varios ítems repiten el campo 'Name', pero los datos del encabezado
# (estado de pago, total, ciudad, etc.) solo aparecen en la primera fila del pedido.
# Usamos groupby + ffill para propagar esos datos a las filas siguientes del mismo pedido.
df_raw = df_raw.replace(r'^\s*$', np.nan, regex=True)
df_raw['Name'] = df_raw['Name'].ffill()  # Asegura que 'Name' esté completo para el groupby
COLUMNAS_FILL = [
    'Financial Status', 'Paid at', 'Fulfillment Status', 'Accepts Marketing',
    'Subtotal', 'Shipping', 'Total', 'Shipping Province Name', 'Discount Code', 'Discount Amount'
]
df_raw[COLUMNAS_FILL] = df_raw.groupby('Name')[COLUMNAS_FILL].ffill()

# --- Conversión de tipos ---
df_raw['Created at'] = pd.to_datetime(df_raw['Created at'], format='ISO8601', utc=True)
df_raw['Total'] = pd.to_numeric(df_raw['Total'], errors='coerce').fillna(0)
df_raw['Lineitem quantity'] = pd.to_numeric(df_raw['Lineitem quantity'], errors='coerce').fillna(0)

# --- Filtrar solo pedidos pagados ---
# Comparación en minúsculas para no depender del formato exacto del dato ('Paid', 'paid', 'PAID')
df_raw = df_raw[df_raw['Financial Status'].str.lower() == 'paid']

# --- Limpiar columna de productos ---
df_raw['Lineitem name'] = df_raw['Lineitem name'].astype(str).str.strip()
df_raw = df_raw[~df_raw['Lineitem name'].isin(['nan', ''])]  # Eliminar filas sin producto válido

# --- Normalizar códigos de descuento ---
# Reemplazamos nulos con 'Sin Código' una sola vez aquí para no repetirlo en varias secciones
df_raw['Discount Code'] = df_raw['Discount Code'].fillna('Sin Código').replace('', 'Sin Código')

######################################################################################
# FASE 2: BARRA LATERAL — FILTROS INTERACTIVOS
######################################################################################
st.sidebar.header("Filtros de Búsqueda")

# ── Filtro 1: Rango de Fechas ────────────────────────────────────────────────────
fecha_min = df_raw['Created at'].min().date()
fecha_max = df_raw['Created at'].max().date()

rango_fechas = st.sidebar.date_input(
    "Selecciona un rango de fechas",
    value=(fecha_min, fecha_max),
    min_value=fecha_min,
    max_value=fecha_max
)

# ── Filtro 2: Ciudad ─────────────────────────────────────────────────────────────
ciudades_disponibles = sorted(df_raw['Shipping Province Name'].dropna().unique())
ciudades_seleccionadas = st.sidebar.multiselect(
    "Filtrar por Ciudad",
    options=ciudades_disponibles,
    default=ciudades_disponibles
)

# ── Aplicar filtros de fecha y ciudad ────────────────────────────────────────────
if len(rango_fechas) == 2:
    inicio, fin = rango_fechas
    mask_fecha = (df_raw['Created at'].dt.date >= inicio) & (df_raw['Created at'].dt.date <= fin)
else:
    mask_fecha = pd.Series(True, index=df_raw.index)

mask_ciudad = df_raw['Shipping Province Name'].isin(ciudades_seleccionadas)
df_filtrado = df_raw[mask_fecha & mask_ciudad].copy()

# ── Filtro 3: Frecuencia de Compra ───────────────────────────────────────────────
# Calculamos cuántas compras únicas hizo cada cliente dentro del rango filtrado
frecuencia_clientes = df_filtrado.groupby('Email')['Name'].nunique()
opciones_frecuencia = sorted(frecuencia_clientes.unique())

frecuencias_seleccionadas = st.sidebar.multiselect(
    "Filtrar por Número de Compras realizadas",
    options=opciones_frecuencia,
    default=opciones_frecuencia,
    help="Selecciona '10' para ver solo clientes que han comprado exactamente 10 veces."
)

emails_que_cumplen = frecuencia_clientes[frecuencia_clientes.isin(frecuencias_seleccionadas)].index
df_filtrado = df_filtrado[df_filtrado['Email'].isin(emails_que_cumplen)]

# ── Filtro 4: Código de Descuento ────────────────────────────────────────────────
codigos_disponibles = sorted(df_filtrado['Discount Code'].unique())

codigos_seleccionados = st.sidebar.multiselect(
    "Filtrar por Código de Descuento",
    options=codigos_disponibles,
    default=codigos_disponibles,
    help="Selecciona uno o varios códigos para ver el comportamiento de esas campañas."
)
df_filtrado = df_filtrado[df_filtrado['Discount Code'].isin(codigos_seleccionados)]

# ── Filtro 5: Producto ───────────────────────────────────────────────────────────
st.sidebar.divider()
productos_disponibles = sorted(df_raw['Lineitem name'].dropna().unique())

productos_seleccionados = st.sidebar.multiselect(
    "Filtrar por Producto(s)",
    options=productos_disponibles,
    default=[],
    help="Muestra los pedidos que contienen al menos uno de los productos seleccionados."
)

if productos_seleccionados:
    # Identificamos los pedidos que contienen alguno de los productos elegidos
    pedidos_con_producto = df_raw[df_raw['Lineitem name'].isin(productos_seleccionados)]['Name'].unique()
    df_filtrado = df_filtrado[df_filtrado['Name'].isin(pedidos_con_producto)]

# ── Filtro 6: Tiempo Máximo de Recompra (días) ───────────────────────────────────
st.sidebar.divider()
st.sidebar.header("Filtro de Recurrencia")

# Calculamos días entre compras para construir el slider dinámico
df_temp_rec = (
    df_filtrado.groupby('Name')
    .agg(Email=('Email', 'first'), fecha=('Created at', 'first'))
    .sort_values(['Email', 'fecha'])
)
df_temp_rec['Fecha_Anterior'] = df_temp_rec.groupby('Email')['fecha'].shift(1)
df_temp_rec['Dias_Entre_Compras'] = (df_temp_rec['fecha'] - df_temp_rec['Fecha_Anterior']).dt.days

dias_validos = df_temp_rec['Dias_Entre_Compras'].dropna()
max_dias_dataset = int(dias_validos.max()) if not dias_validos.empty else 365

dias_limite = st.sidebar.number_input(
    "Ver clientes que volvieron en máximo de (días):",
    min_value=1,
    max_value=max_dias_dataset,
    value=max_dias_dataset,
    help="Filtra el informe para mostrar solo a los clientes que recompraron en este rango de tiempo."
)

# Aplicar filtro de recurrencia solo si el usuario redujo el valor del máximo
if dias_limite < max_dias_dataset:
    emails_recompra = df_temp_rec[
        (df_temp_rec['Dias_Entre_Compras'] >= 1) &
        (df_temp_rec['Dias_Entre_Compras'] <= dias_limite)
    ]['Email'].unique()
    df_filtrado = df_filtrado[df_filtrado['Email'].isin(emails_recompra)]
    st.sidebar.caption(f"✅ Filtrando {len(emails_recompra)} clientes recurrentes.")

######################################################################################
# FASE 3: COLUMNAS AUXILIARES CALCULADAS UNA SOLA VEZ
######################################################################################

# Columna de mes-año sin zona horaria (necesaria para múltiples gráficos y filtros)
df_filtrado = df_filtrado.copy()
df_filtrado['Mes_Anio'] = df_filtrado['Created at'].dt.tz_localize(None).dt.to_period('M').astype(str)

######################################################################################
# SECCIÓN: EVOLUCIÓN MENSUAL Y CRECIMIENTO
######################################################################################
st.divider()
st.subheader("📅 Evolución Mensual y Crecimiento")

# Agrupamos a nivel de pedido para no contar el mismo pedido múltiples veces (por sus ítems)
df_mensual = df_filtrado.groupby('Mes_Anio').agg(
    Pedidos=('Name', 'nunique'),
    # Tomamos el primer 'Total' por pedido para no sumar el mismo pedido n veces
    Ingresos=('Total', lambda x: df_filtrado.loc[x.index].groupby('Name')['Total'].first().sum())
).reset_index()
df_mensual.columns = ['Mes', 'Cantidad de Pedidos', 'Ingresos Totales']

# Variación porcentual mes a mes
df_mensual['Var % Pedidos'] = df_mensual['Cantidad de Pedidos'].pct_change() * 100
df_mensual['Var % Ingresos'] = df_mensual['Ingresos Totales'].pct_change() * 100

col_v1, col_v2 = st.columns(2)
with col_v1:
    fig_pedidos = px.bar(df_mensual, x='Mes', y='Cantidad de Pedidos',
                         title="Pedidos por Mes", text_auto=True, color_discrete_sequence=['#636EFA'])
    st.plotly_chart(fig_pedidos, use_container_width=True)

with col_v2:
    fig_ingresos = px.line(df_mensual, x='Mes', y='Ingresos Totales',
                           title="Ingresos Totales por Mes", markers=True, color_discrete_sequence=['#EF553B'])
    fig_ingresos.update_layout(yaxis_tickformat='$')
    st.plotly_chart(fig_ingresos, use_container_width=True)

st.markdown("#### 📈 Variación Porcentual Mensual")
col_p1, col_p2 = st.columns(2)

# Función auxiliar para crear gráficas de variación % (evita repetición de código)
def grafica_variacion(df, col_y, titulo):
    """Genera un gráfico de barras con escala RdYlGn para variación porcentual mensual."""
    df_clean = df.dropna(subset=[col_y])
    return px.bar(
        df_clean,
        x='Mes', y=col_y,
        title=titulo,
        text=df_clean[col_y].apply(lambda x: f'{x:.1f}%'),
        color=col_y,
        color_continuous_scale='RdYlGn',
        color_continuous_midpoint=0
    )

with col_p1:
    fig_var_ped = grafica_variacion(df_mensual, 'Var % Pedidos', "% Crecimiento Pedidos (vs mes anterior)")
    fig_var_ped.update_traces(textposition='outside')
    st.plotly_chart(fig_var_ped, use_container_width=True)

with col_p2:
    fig_var_ing = grafica_variacion(df_mensual, 'Var % Ingresos', "% Crecimiento Ingresos (vs mes anterior)")
    fig_var_ing.update_traces(textposition='outside')
    st.plotly_chart(fig_var_ing, use_container_width=True)

######################################################################################
# SECCIÓN: TICKET PROMEDIO MENSUAL Y VARIACIÓN
######################################################################################
st.markdown("#### 💸 Ticket Promedio Mensual y Variación %")

# Un registro por pedido (no por ítem) para calcular el promedio correcto
df_tickets = df_filtrado.groupby(['Mes_Anio', 'Name'])['Total'].first().reset_index()
df_ticket_mensual = df_tickets.groupby('Mes_Anio')['Total'].mean().reset_index()
df_ticket_mensual.columns = ['Mes', 'Ticket Promedio']
df_ticket_mensual['Var % Ticket'] = df_ticket_mensual['Ticket Promedio'].pct_change() * 100

col_t1, col_t2 = st.columns(2)
with col_t1:
    fig_ticket_evol = px.bar(
        df_ticket_mensual, x='Mes', y='Ticket Promedio',
        title="Evolución Ticket Promedio ($)",
        text_auto='.2s', color_discrete_sequence=['#00CC96']
    )
    fig_ticket_evol.update_layout(yaxis_tickformat='$')
    st.plotly_chart(fig_ticket_evol, use_container_width=True)

with col_t2:
    fig_var_ticket = grafica_variacion(df_ticket_mensual, 'Var % Ticket', "% Cambio en Ticket Promedio (vs mes anterior)")
    fig_var_ticket.update_traces(textposition='outside')
    st.plotly_chart(fig_var_ticket, use_container_width=True)

######################################################################################
# SECCIÓN: NUEVOS CLIENTES VS RECURRENTES (RETENCIÓN)
######################################################################################
st.divider()
st.subheader("👥 Análisis de Nuevos Clientes y Retención")

# Usamos df_raw (sin filtros) para detectar la primera compra histórica real de cada cliente
df_primeras_compras = (
    df_raw.groupby('Email')['Created at']
    .min()
    .dt.tz_localize(None)
    .dt.to_period('M')
    .reset_index()
)
df_primeras_compras.columns = ['Email', 'Mes_Primer_Compra']

# Unimos con el DataFrame filtrado para clasificar cada pedido como Nuevo o Recurrente
df_retencion = df_filtrado.merge(df_primeras_compras, on='Email', how='left')
df_retencion['Mes_Pedido_Period'] = df_retencion['Created at'].dt.tz_localize(None).dt.to_period('M')
df_retencion['Tipo_Cliente'] = np.where(
    df_retencion['Mes_Pedido_Period'] == df_retencion['Mes_Primer_Compra'],
    'Nuevo', 'Recurrente'
)

df_segmentado = df_retencion.groupby(['Mes_Anio', 'Tipo_Cliente'])['Name'].nunique().reset_index()
df_segmentado.columns = ['Mes', 'Tipo de Cliente', 'Cantidad de Pedidos']

col_ret1, col_ret2 = st.columns(2)
with col_ret1:
    fig_segmentos = px.bar(
        df_segmentado, x='Mes', y='Cantidad de Pedidos', color='Tipo de Cliente',
        title="Nuevos vs. Recurrentes (Por Pedidos)",
        barmode='stack',
        color_discrete_map={'Nuevo': '#636EFA', 'Recurrente': '#00CC96'},
        text_auto=True
    )
    st.plotly_chart(fig_segmentos, use_container_width=True)

with col_ret2:
    # Calcular tasa de retención mensual (% de pedidos de clientes recurrentes)
    df_pivot = df_segmentado.pivot(index='Mes', columns='Tipo de Cliente', values='Cantidad de Pedidos').fillna(0)
    if 'Recurrente' not in df_pivot.columns: df_pivot['Recurrente'] = 0
    if 'Nuevo' not in df_pivot.columns: df_pivot['Nuevo'] = 0
    df_pivot['Total'] = df_pivot['Nuevo'] + df_pivot['Recurrente']
    df_pivot['% Retención'] = (df_pivot['Recurrente'] / df_pivot['Total']) * 100

    fig_rate = px.line(
        df_pivot.reset_index(), x='Mes', y='% Retención',
        title="Tasa de Retención Mensual (%)",
        markers=True, color_discrete_sequence=['#AB63FA']
    )
    fig_rate.update_layout(yaxis_range=[0, 100])
    fig_rate.update_traces(
        text=df_pivot['% Retención'].apply(lambda x: f'{x:.1f}%'),
        hovertemplate='%{x}<br>Retención: %{y:.1f}%'
    )
    st.plotly_chart(fig_rate, use_container_width=True)

######################################################################################
# SECCIÓN: KPIs PRINCIPALES
######################################################################################
st.divider()
st.header("📈 Indicadores Clave (KPIs)")

# Agrupamos por pedido una sola vez para usar en varios KPIs
ventas_unicas = df_filtrado.groupby('Name')['Total'].first()
ticket_promedio = ventas_unicas.mean()

compras_por_usuario = df_filtrado.groupby('Email')['Name'].nunique()
max_compras = compras_por_usuario.max()
promedio_compras = compras_por_usuario.mean()

items_por_pedido = df_filtrado.groupby('Name')['Lineitem quantity'].sum()
promedio_items = items_por_pedido.mean()
max_items = items_por_pedido.max()
pedido_record_name = items_por_pedido.idxmax() if not items_por_pedido.empty else "N/A"

col1, col2, col3 = st.columns(3)
col4, col5, col6 = st.columns(3)

col1.metric("Ventas Totales", f"${ventas_unicas.sum():,.2f}")
col2.metric("Ticket Promedio", f"${ticket_promedio:,.2f}")
col3.metric("Total Pedidos", len(ventas_unicas))
col4.metric("Clientes Únicos", len(compras_por_usuario))
col5.metric("Promedio Compras por Cliente", f"{promedio_compras:.2f}")
col6.metric("Máximo de Compras (Cliente Top)", int(max_compras))

col7, col8 = st.columns(2)
col7.metric("Promedio Ítems por Pedido", f"{promedio_items:.1f}")
col8.metric("Máximo Ítems en un Pedido", int(max_items))

######################################################################################
# SECCIÓN: TOP PRODUCTOS Y CIUDADES
######################################################################################
st.divider()
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🏆 Top 10 Productos Más Vendidos")
    top_productos = (
        df_filtrado.groupby('Lineitem name')['Lineitem quantity']
        .sum().sort_values(ascending=True).tail(10).reset_index()
    )
    fig_prod = px.bar(
        top_productos, x='Lineitem quantity', y='Lineitem name',
        orientation='h', color='Lineitem quantity'
    )
    st.plotly_chart(fig_prod, use_container_width=True)

with col_right:
    st.subheader("📍 Ciudades con más Envíos")
    top_ciudades = (
        df_filtrado.groupby('Shipping Province Name')['Name']
        .nunique().sort_values(ascending=False).head(10).reset_index()
    )
    top_ciudades.columns = ['Ciudad', 'Número de Pedidos']
    fig_city = px.pie(top_ciudades, values='Número de Pedidos', names='Ciudad', hole=0.4)
    st.plotly_chart(fig_city, use_container_width=True)

######################################################################################
# SECCIÓN: MINERÍA DE CANASTA (COMBINACIONES MÁS VENDIDAS)
######################################################################################
st.divider()
st.subheader("🛒 Análisis de Canasta (Combinaciones Comunes)")
st.info("Este análisis muestra qué productos suelen comprarse juntos en el mismo pedido.")

n_combinacion = st.slider(
    "Selecciona el número de productos por combinación",
    min_value=2, max_value=7, value=2,
    help="2 para pares, 3 para tríos, etc. A mayor número, habrá menos coincidencias."
)

# Construir lista de productos únicos por pedido (sets para evitar duplicados)
pedidos_lista = (
    df_filtrado.groupby('Name')['Lineitem name']
    .apply(lambda x: list(set(x.astype(str).str.strip())))
    .tolist()
)

# Contar todas las combinaciones de tamaño n_combinacion
combinaciones_contadas = Counter(
    combo
    for pedido in pedidos_lista
    if len(pedido) >= n_combinacion
    for combo in combinations(sorted(pedido), n_combinacion)
)

if combinaciones_contadas:
    df_combinaciones = pd.DataFrame(
        combinaciones_contadas.most_common(15),
        columns=['Combinación', 'Frecuencia']
    )
    df_combinaciones['Combinación'] = df_combinaciones['Combinación'].apply(lambda x: " + ".join(x))

    fig_comb = px.bar(
        df_combinaciones, x='Frecuencia', y='Combinación', orientation='h',
        color='Frecuencia', color_continuous_scale='Viridis',
        title=f"Top combinaciones de {n_combinacion} productos"
    )
    fig_comb.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_comb, use_container_width=True)
else:
    df_combinaciones = pd.DataFrame(columns=['Combinación', 'Frecuencia'])
    st.warning(f"No se encontraron combinaciones de {n_combinacion} productos en los pedidos filtrados.")

######################################################################################
# SECCIÓN: ANÁLISIS DE RECURRENCIA (TIEMPO ENTRE COMPRAS)
######################################################################################
st.divider()
st.subheader("⏱️ Análisis de Tiempo entre Compras")

# Un registro por pedido ordenado por cliente y fecha
df_pedidos_tiempo = (
    df_filtrado.groupby('Name')
    .agg(Email=('Email', 'first'), fecha=('Created at', 'first'))
    .sort_values(['Email', 'fecha'])
)
df_pedidos_tiempo['Fecha_Anterior'] = df_pedidos_tiempo.groupby('Email')['fecha'].shift(1)
df_pedidos_tiempo['Dias_Entre_Compras'] = (df_pedidos_tiempo['fecha'] - df_pedidos_tiempo['Fecha_Anterior']).dt.days

# Solo recompras reales (>= 1 día entre pedidos)
df_recompras_validas = df_pedidos_tiempo[df_pedidos_tiempo['Dias_Entre_Compras'] >= 1].copy()

if not df_recompras_validas.empty:
    # Eliminar valores atípicos usando el método IQR (estándar estadístico)
    Q1 = df_recompras_validas['Dias_Entre_Compras'].quantile(0.25)
    Q3 = df_recompras_validas['Dias_Entre_Compras'].quantile(0.75)
    IQR = Q3 - Q1
    limite_inferior = Q1 - 1.5 * IQR
    limite_superior = Q3 + 1.5 * IQR

    df_recompras_limpio = df_recompras_validas[
        (df_recompras_validas['Dias_Entre_Compras'] >= limite_inferior) &
        (df_recompras_validas['Dias_Entre_Compras'] <= limite_superior)
    ].copy()

    avg_dias = df_recompras_limpio['Dias_Entre_Compras'].mean()
    min_dias = df_recompras_limpio['Dias_Entre_Compras'].min()
    max_dias = df_recompras_limpio['Dias_Entre_Compras'].max()

    id_min_recompra = df_recompras_limpio['Dias_Entre_Compras'].idxmin()
    cliente_record_email = df_recompras_limpio.loc[id_min_recompra, 'Email']

    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric("Tiempo Promedio (Sin Atípicos)", f"{avg_dias:.1f} días")
    col_t2.metric("Mínimo entre Compras", f"{int(min_dias)} días")
    col_t3.metric("Máximo (Filtrado)", f"{int(max_dias)} días")

    fig_dist_tiempo = px.histogram(
        df_recompras_limpio, x='Dias_Entre_Compras',
        title=f"Distribución de Recompras (Excluyendo valores > {int(limite_superior)} días)",
        labels={'Dias_Entre_Compras': 'Días entre pedidos', 'count': 'Frecuencia'},
        color_discrete_sequence=['#AB63FA'], text_auto=True
    )
    fig_dist_tiempo.update_traces(xbins=dict(start=0, end=max_dias + 5, size=5))
    fig_dist_tiempo.update_layout(bargap=0.1, xaxis=dict(tickmode='linear', tick0=0, dtick=5))
    st.plotly_chart(fig_dist_tiempo, use_container_width=True)
    st.caption(f"💡 Se han excluido automáticamente los valores por encima de {int(limite_superior)} días para no sesgar el promedio.")
else:
    # Si no hay recompras, definimos un valor seguro para la sección de recomendaciones
    cliente_record_email = "N/A"

######################################################################################
# SECCIÓN: ANÁLISIS DE CÓDIGOS DE DESCUENTO
######################################################################################
st.divider()
st.subheader("🎟️ Uso de Códigos de Descuento")

# Un registro por pedido para no duplicar por ítems
df_cupones = df_filtrado.groupby('Name')['Discount Code'].first().reset_index()
conteo_cupones = df_cupones['Discount Code'].value_counts().reset_index()
conteo_cupones.columns = ['Código', 'Cantidad']
conteo_cupones['Porcentaje (%)'] = (conteo_cupones['Cantidad'] / conteo_cupones['Cantidad'].sum()) * 100

fig_cupones = px.bar(
    conteo_cupones, x='Código', y='Cantidad',
    text=conteo_cupones['Porcentaje (%)'].apply(lambda x: f'{x:.1f}%'),
    title="Frecuencia de Uso de Cupones",
    labels={'Cantidad': 'Número de Pedidos', 'Código': 'Código de Descuento'},
    color='Cantidad', color_continuous_scale='Blues'
)
fig_cupones.update_traces(textposition='outside')
fig_cupones.update_layout(yaxis_title="Cantidad de Pedidos", xaxis_tickangle=-45)
st.plotly_chart(fig_cupones, use_container_width=True)

with st.expander("Ver tabla de detalles de cupones"):
    st.dataframe(conteo_cupones.style.format({'Porcentaje (%)': '{:.2f}%'}), use_container_width=True)

######################################################################################
# SECCIÓN: RECOMENDACIONES ESTRATÉGICAS
######################################################################################
st.divider()
st.subheader("💡 Sugerencias Estratégicas")

# Pedido con mayor monto (calculado una sola vez)
ventas_por_pedido = df_filtrado.groupby('Name')['Total'].first()
if not ventas_por_pedido.empty:
    mayor_monto = ventas_por_pedido.max()
    pedido_mas_caro_name = ventas_por_pedido.idxmax()
else:
    mayor_monto = 0
    pedido_mas_caro_name = "N/A"

# Código de descuento más usado (excluyendo 'Sin Código')
cupones_reales = df_filtrado[df_filtrado['Discount Code'] != 'Sin Código']['Discount Code']
top_cupon = cupones_reales.value_counts().head(1)

# Combinación más frecuente (tomada del análisis de canasta calculado arriba)
combinacion_top = df_combinaciones.iloc[0]['Combinación'] if not df_combinaciones.empty else 'N/A'

st.markdown(f"""
1. **Fidelización:** Tienes **{df_filtrado['Email'].nunique()}** clientes únicos. Podrías implementar una campaña de email marketing para los que aceptan marketing ({(df_filtrado['Accepts Marketing'] == 'yes').sum()} personas).
2. **Combinacion mas vendida:** Si la combinación más frecuente es **'{combinacion_top}'**.
3. **Conversión:** El código de descuento más usado es **'{top_cupon.index[0] if not top_cupon.empty else 'Ninguno'}'**.
4. **Número de Pedido con Más Ítems en una sola compra:** **{pedido_record_name}**
5. **Cliente que realizó la recompra en menos tiempo:** **{cliente_record_email}**
6. **Venta Récord (Monto):** El pedido con el mayor ingreso fue el **{pedido_mas_caro_name}** por un total de **${mayor_monto:,.2f}**.
""")