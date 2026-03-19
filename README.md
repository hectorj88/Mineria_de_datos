# 📊 Dashboard de Minería de Datos E-commerce

Este es un dashboard interactivo desarrollado en **Python** utilizando **Streamlit**. Está diseñado para procesar reportes de ventas (archivos `.csv` o `.xlsx`) de plataformas de comercio electrónico, permitiendo realizar análisis de KPIs, comportamiento de clientes y minería de asociaciones (Market Basket Analysis).

## 🚀 Características Principales

* **Limpieza Automática:** Procesa y rellena datos faltantes (ffill) agrupados por pedido.
* **KPIs de Negocio:** Visualización instantánea de Ventas Totales, Ticket Promedio, Tasa de Recurrencia y más.
* **Análisis Temporal:** Gráficos de evolución mensual con cálculo de crecimiento **MoM (Month-over-Month)**.
* **Minería de Datos:** Identificación de combinaciones de productos más frecuentes mediante el algoritmo de combinaciones de la cesta de compra.
* **Filtros Dinámicos:** Segmentación por rango de fechas, ciudades, frecuencia de compra, códigos de descuento y tiempo de recompra.
* **Análisis de Fidelización:** Seguimiento del uso de cupones y tiempos de retorno de clientes.

## 🛠️ Tecnologías Utilizadas

* [Python](https://www.python.org/) - Lenguaje principal.
* [Streamlit](https://streamlit.io/) - Framework para la interfaz web interactiva.
* [Pandas](https://pandas.pydata.org/) - Manipulación y limpieza de datos.
* [Plotly Express](https://plotly.com/python/plotly-express/) - Gráficos dinámicos y visualizaciones.
* [Itertools/Collections](https://docs.python.org/3/library/collections.html) - Minería de combinaciones de productos.

## 📦 Instalación y Uso

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/hectorj88/Mineria_de_datos.git
   cd Mineria_de_datos

2. **Crear un entorno virtual (opcional pero recomendado):**
   ```bash
   python -m venv venv
    source venv/bin/activate  # En Windows: venv\Scripts\activate

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt

4. **Ejecutar la aplicación:**
   ```bash
   streamlit run main.py

## 📋 Formato de Datos Requerido
### El dashboard espera columnas específicas como:

* Name (ID del pedido)
* Lineitem name (Nombre del producto)
* Financial Status (Filtra automáticamente por 'paid')
* Total, Created at, Email, Shipping Province Name, entre otras.

## 💡 Sugerencias Estratégicas
El sistema genera automáticamente una sección de Sugerencias Estratégicas al final del análisis, destacando:

* El cliente con la recompra más rápida.
* La combinación de productos ganadora para crear "Bundles" o combos.
* El cupón con mayor tasa de conversión.
* Récords de ventas y volumen de ítems.
##

Desarrollado con ❤️ por Hector Rosas