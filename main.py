import streamlit as st
import pandas as pd
import plotly.express as px
from itertools import combinations
from collections import Counter
#pip freeze > requirements.txt
#streamlit run main.py

# Configuración de la página
st.set_page_config(page_title="Dashboard de Minería E-commerce", layout="wide")

st.title("📊 Análisis de Ventas y Minería de Datos")
st.markdown("Sube tu archivo .csv o .xlsx para procesar las métricas de negocio.")

# 1. Carga de Archivos
uploaded_file = st.file_uploader("Elige un archivo", type=['csv', 'xlsx'])

if uploaded_file is not None:
    # Cargar datos según extensión
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    ######################################################################################
    # --- FASE DE LIMPIEZA Y PREPROCESAMIENTO ---
    ######################################################################################
    # Definimos las columnas necesarias según tu descripción
    cols_interes = [
        'Name', 'Email', 'Financial Status', 'Paid at', 'Fulfillment Status', 
        'Subtotal', 'Shipping', 'Total', 'Discount Code', 'Discount Amount', 
        'Created at', 'Lineitem quantity', 'Lineitem name', 'Lineitem price', 
        'Lineitem compare at price', 'Shipping Province Name'
    ]
    
    # Asegurarnos de que las columnas existan (case-insensitive para evitar errores de tipeo)
    df.columns = [c.strip() for c in df.columns]
    
    # Rellenar datos faltantes del encabezado del pedido (Forward Fill)
    # Como mencionas que 'Name' se repite pero los datos de pago solo están en la primera fila,
    # usamos ffill() agrupado por el número de pedido para completar la información.
    columnas_a_rellenar = ['Financial Status', 'Paid at', 'Fulfillment Status', 'Subtotal', 
                           'Shipping', 'Total', 'Shipping Province Name', 'Email']
    
    df[columnas_a_rellenar] = df.groupby('Name')[columnas_a_rellenar].ffill()
    
    # Convertir fechas y números
    df['Created at'] = pd.to_datetime(df['Created at'], errors='coerce')
    df['Total'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)
    df['Lineitem quantity'] = pd.to_numeric(df['Lineitem quantity'], errors='coerce').fillna(0)

    # FILTRAR SOLO PEDIDOS PAGADOS
    # Usamos .str.lower() para evitar errores si en el CSV aparece 'Paid' o 'PAID'
    df = df[df['Financial Status'].str.lower() == 'paid']

    ######################################################################################
    # ------------- BARRA LATERAL (FILTROS) -------------
    ######################################################################################
    st.sidebar.header("Filtros de Búsqueda")

    # Filtro 1: Rango de Fechas
    # Obtenemos la fecha mínima y máxima del dataset
    fecha_min = df['Created at'].min().date()
    fecha_max = df['Created at'].max().date()

    rango_fechas = st.sidebar.date_input(
        "Selecciona un rango de fechas",
        value=(fecha_min, fecha_max),
        min_value=fecha_min,
        max_value=fecha_max
    )

    # Filtro 2: Por Ciudad
    ciudades_disponibles = sorted(df['Shipping Province Name'].dropna().unique())
    ciudades_seleccionadas = st.sidebar.multiselect(
        "Filtrar por Ciudad",
        options=ciudades_disponibles,
        default=ciudades_disponibles # Por defecto selecciona todas
    )

    # --- APLICAR FILTROS AL DATAFRAME ---
    # Filtrar por fecha (validando que el usuario haya seleccionado inicio y fin)
    if len(rango_fechas) == 2:
        inicio, fin = rango_fechas
        mask_fecha = (df['Created at'].dt.date >= inicio) & (df['Created at'].dt.date <= fin)
    else:
        mask_fecha = True

    # Filtrar por ciudad
    mask_ciudad = df['Shipping Province Name'].isin(ciudades_seleccionadas)

    # Creamos un nuevo DataFrame filtrado que usaremos para TODO el análisis posterior
    df_filtrado = df[mask_fecha & mask_ciudad]

    # --- FILTRO POR FRECUENCIA DE COMPRA ---
    # 1. Calculamos la frecuencia de compra por email en el set de datos ya filtrado por fecha/ciudad
    frecuencia_clientes = df_filtrado.groupby('Email')['Name'].nunique()
    
    # 2. Obtenemos las opciones disponibles (ej. 1, 2, 5, 10...)
    opciones_frecuencia = sorted(frecuencia_clientes.unique())
    
    frecuencias_seleccionadas = st.sidebar.multiselect(
        "Filtrar por Número de Compras realizadas",
        options=opciones_frecuencia,
        default=opciones_frecuencia,
        help="Selecciona '10' para ver solo clientes que han comprado exactamente 10 veces."
    )

    # 3. Identificamos qué emails cumplen con esa frecuencia
    emails_que_cumplen = frecuencia_clientes[frecuencia_clientes.isin(frecuencias_seleccionadas)].index

    # 4. Aplicamos el filtro final al DataFrame que usan los gráficos
    df_filtrado = df_filtrado[df_filtrado['Email'].isin(emails_que_cumplen)]

    # --- FILTRO POR CÓDIGO DE DESCUENTO ---
    # Limpiamos los valores nulos para que aparezcan como 'Sin Código'
    df_filtrado['Discount Code'] = df_filtrado['Discount Code'].fillna('Sin Código')
    
    codigos_disponibles = sorted(df_filtrado['Discount Code'].unique())
    
    codigos_seleccionados = st.sidebar.multiselect(
        "Filtrar por Código de Descuento",
        options=codigos_disponibles,
        default=codigos_disponibles,
        help="Selecciona uno o varios códigos para ver el comportamiento de esas campañas."
    )

    # Aplicamos el filtro al DataFrame
    df_filtrado = df_filtrado[df_filtrado['Discount Code'].isin(codigos_seleccionados)]

    # --- FILTRO POR PRODUCTO (SELECCIÓN MÚLTIPLE) ---
    st.sidebar.divider()
    productos_disponibles = sorted(df['Lineitem name'].dropna().unique())
    
    productos_seleccionados = st.sidebar.multiselect(
        "Filtrar por Producto(s)",
        options=productos_disponibles,
        default=[], # Vacío por defecto para no filtrar nada al inicio
        help="Muestra los pedidos que contienen al menos uno de los productos seleccionados."
    )

    # Solo aplicamos el filtro si el usuario ha seleccionado algo
    if productos_seleccionados:
        # 1. Identificamos los IDs de pedido ('Name') que contienen CUALQUIERA de los productos elegidos
        pedidos_interes = df[df['Lineitem name'].isin(productos_seleccionados)]['Name'].unique()
        
        # 2. Filtramos el DataFrame principal para mantener solo esos pedidos completos
        df_filtrado = df_filtrado[df_filtrado['Name'].isin(pedidos_interes)]
    

    # --- FILTRO POR TIEMPO DE RECOMPRA (DÍAS MÁXIMOS) ---
    st.sidebar.divider()
    st.sidebar.header("Filtro de Recurrencia")

    # Calculamos los días entre compras internamente para poder filtrar
    df_temp_rec = df_filtrado.groupby('Name').agg({
        'Email': 'first',
        'Created at': 'first'
    }).sort_values(['Email', 'Created at'])

    df_temp_rec['Fecha_Anterior'] = df_temp_rec.groupby('Email')['Created at'].shift(1)
    df_temp_rec['Dias_Entre_Compras'] = (df_temp_rec['Created at'] - df_temp_rec['Fecha_Anterior']).dt.days

    # Definir el límite máximo que el usuario puede escribir
    max_dias_dataset = int(df_temp_rec['Dias_Entre_Compras'].max()) if not df_temp_rec['Dias_Entre_Compras'].dropna().empty else 365

    dias_limite = st.sidebar.number_input(
        "Ver clientes que volvieron en máximo de (días):",
        min_value=1,
        max_value=max_dias_dataset,
        value=max_dias_dataset,
        help="Filtra el informe para mostrar solo a los clientes que recompraron en este rango de tiempo."
    )

    # Identificamos los Emails que cumplen con el criterio de recompra rápida
    # (Buscamos clientes que tengan al menos una recompra <= dias_limite)
    emails_recompra_filtro = df_temp_rec[
        (df_temp_rec['Dias_Entre_Compras'] >= 1) & 
        (df_temp_rec['Dias_Entre_Compras'] <= dias_limite)
    ]['Email'].unique()

    # APLICAR FILTRO GLOBAL: 
    # Si el usuario movió el filtro (es menor al máximo), filtramos el DataFrame principal
    if dias_limite < max_dias_dataset:
        df_filtrado = df_filtrado[df_filtrado['Email'].isin(emails_recompra_filtro)]
        st.sidebar.caption(f"✅ Filtrando {len(emails_recompra_filtro)} clientes recurrentes.")

    ######################################################################################
    # --- Grafica ventas e ingresos por mes ---
    ######################################################################################
    st.divider()
    st.subheader("📅 Evolución Mensual y Crecimiento")
    
    # 1. Preparación de datos
    df_filtrado['Created at'] = pd.to_datetime(df_filtrado['Created at'], errors='coerce')
    df_filtrado['Mes_Anio'] = df_filtrado['Created at'].dt.to_period('M').astype(str)

    # Agrupamos datos base
    df_mensual = df_filtrado.groupby('Mes_Anio').agg({
        'Name': 'nunique',
        'Total': lambda x: df_filtrado.loc[x.index].groupby('Name')['Total'].first().sum()
    }).reset_index()

    df_mensual.columns = ['Mes', 'Cantidad de Pedidos', 'Ingresos Totales']

    # 2. CALCULAR CRECIMIENTO PORCENTUAL
    # Usamos pct_change() y multiplicamos por 100
    df_mensual['Var % Pedidos'] = df_mensual['Cantidad de Pedidos'].pct_change() * 100
    df_mensual['Var % Ingresos'] = df_mensual['Ingresos Totales'].pct_change() * 100

    # --- FILA 1: Gráficas de Totales (Las que ya tenías) ---
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

    # --- FILA 2: Gráficas de Incremento/Decremento % ---
    st.markdown("#### 📈 Variación Porcentual Mensual")
    col_p1, col_p2 = st.columns(2)

    with col_p1:
        # Gráfica de barras para variación de pedidos
        fig_var_ped = px.bar(
            df_mensual.dropna(subset=['Var % Pedidos']), # Quitamos el primer mes porque no tiene anterior
            x='Mes', 
            y='Var % Pedidos',
            title="% Crecimiento Pedidos (vs mes anterior)",
            text=df_mensual['Var % Pedidos'].dropna().apply(lambda x: f'{x:.1f}%'),
            color='Var % Pedidos',
            color_continuous_scale='RdYlGn', # Rojo para negativo, verde para positivo
            color_continuous_midpoint=0
        )
        fig_var_ped.update_traces(textposition='outside')
        st.plotly_chart(fig_var_ped, use_container_width=True)

    with col_p2:
        # Gráfica de barras para variación de ingresos
        fig_var_ing = px.bar(
            df_mensual.dropna(subset=['Var % Ingresos']),
            x='Mes', 
            y='Var % Ingresos',
            title="% Crecimiento Ingresos (vs mes anterior)",
            text=df_mensual['Var % Ingresos'].dropna().apply(lambda x: f'{x:.1f}%'),
            color='Var % Ingresos',
            color_continuous_scale='RdYlGn',
            color_continuous_midpoint=0
        )
        fig_var_ing.update_traces(textposition='outside')
        st.plotly_chart(fig_var_ing, use_container_width=True)
    
    ######################################################################################
    # --- ANÁLISIS DE TICKET PROMEDIO MENSUAL Y VARIACIÓN ---
    ######################################################################################
    st.markdown("#### 💸 Ticket Promedio Mensual y Variación %")

    # 1. Preparar datos de Ticket Promedio por Mes
    # Agrupamos por Pedido (Name) y Mes para obtener el Total de cada venta única
    df_tickets = df_filtrado.groupby(['Mes_Anio', 'Name'])['Total'].first().reset_index()

    # Ahora calculamos el promedio de esos totales por mes
    df_ticket_mensual = df_tickets.groupby('Mes_Anio')['Total'].mean().reset_index()
    df_ticket_mensual.columns = ['Mes', 'Ticket Promedio']

    # 2. Calcular Variación Porcentual del Ticket Promedio
    df_ticket_mensual['Var % Ticket'] = df_ticket_mensual['Ticket Promedio'].pct_change() * 100

    # --- RENDERIZADO DE GRÁFICAS ---
    col_t1, col_t2 = st.columns(2)

    with col_t1:
        # Histograma de frecuencia (Evolución del Ticket)
        fig_ticket_evol = px.bar(
            df_ticket_mensual, 
            x='Mes', 
            y='Ticket Promedio',
            title="Evolución Ticket Promedio ($)",
            text_auto='.2s',
            color_discrete_sequence=['#00CC96']
        )
        fig_ticket_evol.update_layout(yaxis_tickformat='$')
        st.plotly_chart(fig_ticket_evol, use_container_width=True)

    with col_t2:
        # Variación % del Ticket Promedio
        fig_var_ticket = px.bar(
            df_ticket_mensual.dropna(subset=['Var % Ticket']),
            x='Mes',
            y='Var % Ticket',
            title="% Cambio en Ticket Promedio (vs mes anterior)",
            text=df_ticket_mensual['Var % Ticket'].dropna().apply(lambda x: f'{x:.1f}%'),
            color='Var % Ticket',
            color_continuous_scale='RdYlGn',
            color_continuous_midpoint=0
        )
        fig_var_ticket.update_traces(textposition='outside')
        st.plotly_chart(fig_var_ticket, use_container_width=True)
    

    
    st.divider()
    ######################################################################################
    # --- KPI'S PRINCIPALES ---
    ######################################################################################
    st.header("📈 Indicadores Clave (KPIs)")
    col1, col2, col3 = st.columns(3)
    
    # Ticket Promedio: Basado en pedidos únicos (usando el máximo del 'Total' por 'Name')
    ventas_unicas = df_filtrado.groupby('Name')['Total'].first()
    ticket_promedio = ventas_unicas.mean()
    
    # --- CÁLCULO DE RECURRENCIA POR USUARIO ---
    # Contamos cuántos pedidos únicos ('Name') tiene cada 'Email'
    compras_por_usuario = df_filtrado.groupby('Email')['Name'].nunique()
    
    max_compras = compras_por_usuario.max()
    promedio_compras = compras_por_usuario.mean()

    # Calculando la cantidad de ítems por pedido (usando el máximo de 'Lineitem quantity' por 'Name')
    items_por_pedido = df_filtrado.groupby('Name')['Lineitem quantity'].sum()
    
    promedio_items = items_por_pedido.mean()
    max_items = items_por_pedido.max()
    # 2. Encontrar el 'Name' (Número de pedido) que tiene ese máximo
    pedido_record_name = items_por_pedido.idxmax() if not items_por_pedido.empty else "N/A"

    # Segunda fila de KPIs (Nuevos indicadores)
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


    st.divider()
    ######################################################################################
    # --- ANÁLISIS DE PRODUCTOS Y CIUDADES ---
    ######################################################################################
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🏆 Top 10 Productos Más Vendidos")
        top_productos = df_filtrado.groupby('Lineitem name')['Lineitem quantity'].sum().sort_values(ascending=True).tail(10).reset_index()
        fig_prod = px.bar(top_productos, x='Lineitem quantity', y='Lineitem name', orientation='h', color='Lineitem quantity')
        st.plotly_chart(fig_prod, use_container_width=True)

    with col_right:
        st.subheader("📍 Ciudades con más Envíos")
        top_ciudades = df_filtrado.groupby('Shipping Province Name')['Name'].nunique().sort_values(ascending=False).head(10).reset_index()
        top_ciudades.columns = ['Ciudad', 'Número de Pedidos']
        fig_city = px.pie(top_ciudades, values='Número de Pedidos', names='Ciudad', hole=0.4)
        st.plotly_chart(fig_city, use_container_width=True)

    ######################################################################################
    # --- MINERÍA DE DATOS: COMBINACIONES MÁS VENDIDAS ---
    ######################################################################################
    st.divider()
    st.subheader("🛒 Análisis de Canasta (Combinaciones Comunes)")
    st.info("Este análisis muestra qué productos suelen comprarse juntos en el mismo pedido.")

    # 1. Control para que el usuario elija el tamaño de la combinación
    n_combinacion = st.slider(
        "Selecciona el número de productos por combinación", 
        min_value=2, 
        max_value=7, 
        value=2,
        help="2 para pares, 3 para tríos, etc. Ten en cuenta que a mayor número, habrá menos coincidencias."
    )

    # Crear una lista de productos por cada 'Name' (pedido)
    pedidos_lista = df_filtrado.groupby('Name')['Lineitem name'].apply(list).tolist()
    
    # Contar combinaciones de productos
    combinaciones_contadas = Counter()
    for pedido in pedidos_lista:
        # Solo procesamos si el pedido tiene al menos el número de ítems solicitado
        if len(set(pedido)) >= n_combinacion:
            # Generamos las combinaciones dinámicamente usando n_combinacion
            combos = combinations(sorted(set(pedido)), n_combinacion)
            combinaciones_contadas.update(combos)

    if combinaciones_contadas:
        # Tomamos las 15 más comunes
        df_combinaciones = pd.DataFrame(combinaciones_contadas.most_common(15), columns=['Combinación', 'Frecuencia'])
        
        # Unimos los nombres de los productos con un " + " dinámicamente
        df_combinaciones['Combinación'] = df_combinaciones['Combinación'].apply(lambda x: " + ".join(x))
        
        # Crear gráfico
        fig_comb = px.bar(
            df_combinaciones, 
            x='Frecuencia', 
            y='Combinación', 
            orientation='h', 
            color='Frecuencia', 
            color_continuous_scale='Viridis',
            title=f"Top combinaciones de {n_combinacion} productos"
        )
        # Invertir el eje Y para que la más frecuente esté arriba
        fig_comb.update_layout(yaxis={'categoryorder':'total ascending'})
        
        st.plotly_chart(fig_comb, use_container_width=True)
    else:
        st.warning(f"No se encontraron combinaciones de {n_combinacion} productos en los pedidos filtrados.")
    
    ######################################################################################
    # --- ANÁLISIS DE RECURRENCIA (TIEMPO ENTRE COMPRAS) ---
    ######################################################################################
    st.divider()
    st.subheader("⏱️ Análisis de Tiempo entre Compras")

    # 1. Preparar datos: Un registro por pedido único, ordenado por fecha
    df_pedidos_tiempo = df_filtrado.groupby('Name').agg({
        'Email': 'first',
        'Created at': 'first'
    }).sort_values(['Email', 'Created at'])

    # 2. Calcular la diferencia de días entre pedidos del mismo cliente
    df_pedidos_tiempo['Fecha_Anterior'] = df_pedidos_tiempo.groupby('Email')['Created at'].shift(1)
    df_pedidos_tiempo['Dias_Entre_Compras'] = (df_pedidos_tiempo['Created at'] - df_pedidos_tiempo['Fecha_Anterior']).dt.days

    # --- FILTRO CLAVE: Solo registros con 1 día o más ---
    df_recompras_validas = df_pedidos_tiempo[df_pedidos_tiempo['Dias_Entre_Compras'] >= 1].copy()

    if not df_recompras_validas.empty:
        # --- ELIMINACIÓN DE VALORES ATÍPICOS (MÉTODO IQR) ---
        Q1 = df_recompras_validas['Dias_Entre_Compras'].quantile(0.25)
        Q3 = df_recompras_validas['Dias_Entre_Compras'].quantile(0.75)
        IQR = Q3 - Q1
        
        # Definimos los límites (1.5 es el estándar de la industria)
        limite_inferior = Q1 - 1.5 * IQR
        limite_superior = Q3 + 1.5 * IQR
        
        # Aplicamos el filtro para limpiar los datos
        df_recompras_limpio = df_recompras_validas[
            (df_recompras_validas['Dias_Entre_Compras'] >= limite_inferior) & 
            (df_recompras_validas['Dias_Entre_Compras'] <= limite_superior)
        ].copy()

        # 3. Cálculos de métricas usando el DataFrame LIMPIO
        avg_dias = df_recompras_limpio['Dias_Entre_Compras'].mean()
        min_dias = df_recompras_limpio['Dias_Entre_Compras'].min()
        max_dias = df_recompras_limpio['Dias_Entre_Compras'].max()

        # Identificar al cliente récord (se mantiene del original o del limpio)
        id_min_recompra = df_recompras_limpio['Dias_Entre_Compras'].idxmin()
        cliente_record_email = df_recompras_limpio.loc[id_min_recompra, 'Email']
        
        # Mostrar métricas
        col_t1, col_t2, col_t3 = st.columns(3)
        col_t1.metric("Tiempo Promedio (Sin Atípicos)", f"{avg_dias:.1f} días")
        col_t2.metric("Mínimo entre Compras", f"{int(min_dias)} días")
        col_t3.metric("Máximo (Filtrado)", f"{int(max_dias)} días")
        
        # 4. Configuración del Histograma (Usando df_recompras_limpio)
        fig_dist_tiempo = px.histogram(
            df_recompras_limpio, 
            x='Dias_Entre_Compras',
            title=f"Distribución de Recompras (Excluyendo valores > {int(limite_superior)} días)",
            labels={'Dias_Entre_Compras': 'Días entre pedidos', 'count': 'Frecuencia'},
            color_discrete_sequence=['#AB63FA'],
            text_auto=True
        )
        
        # Ajuste dinámico de los Bins según el nuevo máximo
        fig_dist_tiempo.update_traces(xbins=dict(start=0, end=max_dias + 5, size=5))
        fig_dist_tiempo.update_layout(bargap=0.1, xaxis=dict(tickmode='linear', tick0=0, dtick=5))

        st.plotly_chart(fig_dist_tiempo, use_container_width=True)
        
        st.caption(f"💡 Se han excluido automáticamente los valores por encima de {int(limite_superior)} días para no sesgar el promedio.")
    


    ######################################################################################
    # --- ANÁLISIS DE CÓDIGOS DE DESCUENTO (FRECUENCIA Y %) ---
    ######################################################################################
    st.divider()
    st.subheader("🎟️ Uso de Códigos de Descuento")

    # 1. Preparar los datos (un registro por pedido para no duplicar por ítems)
    df_cupones = df_filtrado.groupby('Name')['Discount Code'].first().reset_index()
    
    # 2. Contar frecuencias
    conteo_cupones = df_cupones['Discount Code'].value_counts().reset_index()
    conteo_cupones.columns = ['Código', 'Cantidad']
    
    # 3. Calcular el porcentaje
    total_pedidos = conteo_cupones['Cantidad'].sum()
    conteo_cupones['Porcentaje (%)'] = (conteo_cupones['Cantidad'] / total_pedidos) * 100

    # 4. Crear el gráfico con Plotly
    fig_cupones = px.bar(
        conteo_cupones, 
        x='Código', 
        y='Cantidad',
        text=conteo_cupones['Porcentaje (%)'].apply(lambda x: f'{x:.1f}%'),
        title="Frecuencia de Uso de Cupones",
        labels={'Cantidad': 'Número de Pedidos', 'Código': 'Código de Descuento'},
        color='Cantidad',
        color_continuous_scale='Blues'
    )

    # Ajustar el diseño para que el texto del porcentaje se vea arriba de las barras
    fig_cupones.update_traces(textposition='outside')
    fig_cupones.update_layout(yaxis_title="Cantidad de Pedidos", xaxis_tickangle=-45)

    st.plotly_chart(fig_cupones, use_container_width=True)

    # Opcional: Mostrar una tabla pequeña con el desglose exacto
    with st.expander("Ver tabla de detalles de cupones"):
        st.dataframe(conteo_cupones.style.format({'Porcentaje (%)': '{:.2f}%'}), use_container_width=True)
    

    ######################################################################################
    # Calculos para mostrar en las recomendaciones estategicas
    ######################################################################################
    # Identificar el pedido con el mayor monto total
    # Agrupamos por 'Name' y tomamos el primer 'Total' (ya que el total es por pedido, no por ítem)
    ventas_por_pedido = df_filtrado.groupby('Name')['Total'].first()
    
    if not ventas_por_pedido.empty:
        mayor_monto = ventas_por_pedido.max()
        pedido_mas_caro_name = ventas_por_pedido.idxmax()
    else:
        mayor_monto = 0
        pedido_mas_caro_name = "N/A"
    
    # Identificar el pedido con el mayor monto total
    # Agrupamos por 'Name' y tomamos el primer 'Total' (ya que el total es por pedido, no por ítem)
    ventas_por_pedido = df_filtrado.groupby('Name')['Total'].first()
    
    if not ventas_por_pedido.empty:
        mayor_monto = ventas_por_pedido.max()
        pedido_mas_caro_name = ventas_por_pedido.idxmax()
    else:
        mayor_monto = 0
        pedido_mas_caro_name = "N/A"
    
    ######################################################################################
    # --- RECOMENDACIONES ESTRATÉGICAS ---
    ######################################################################################
    st.divider()
    st.subheader("💡 Sugerencias Estratégicas")
    
    # Filtramos para excluir 'Sin Código' antes de contar
    cupones_reales = df_filtrado[df_filtrado['Discount Code'] != 'Sin Código']['Discount Code']
    top_cupo = cupones_reales.value_counts().head(1)
    
    st.markdown(f"""
    1. **Fidelización:** Tienes **{df_filtrado['Email'].nunique()}** clientes únicos. Podrías implementar una campaña de email marketing para los que aceptan marketing ({(df_filtrado['Accepts Marketing'] == 'yes').sum()} personas).
    2. **Combinacion mas vendida:** Si la combinación más frecuente es **'{df_combinaciones.iloc[0]['Combinación'] if not df_combinaciones.empty else 'N/A'}'**.
    3. **Conversión:** El código de descuento más usado es **'{top_cupo.index[0] if not top_cupo.empty else 'Ninguno'}'**.
    4. **Número de Pedido con Más Ítems en una sola compra:** **{pedido_record_name}**
    5. **Cliente que realizó la recompra en menos tiempo:** **{cliente_record_email}**
    6. **Venta Récord (Monto):** El pedido con el mayor ingreso fue el **{pedido_mas_caro_name}** por un total de **${mayor_monto:,.2f}**.
    """)
    

else:
    st.warning("👈 Por favor, sube un archivo para comenzar el análisis.")