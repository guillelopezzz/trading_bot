# Trading Automation Bot – Forex EUR/USD

Este proyecto es una solución de automatización de operaciones de trading en el mercado Forex, específicamente para el par EUR/USD. El sistema simula un entorno de trading en tiempo real, procesando precios secuencialmente y aplicando una estrategia de trading definida. Además, incluye una función de visualización gráfica que permite analizar las operaciones realizadas en un día específico.

## Funcionalidades principales

Simulación de streaming: Procesamiento secuencial de precios, replicando un entorno de mercado en tiempo real.

Automatización de operaciones: Ejecución automática de apertura y cierre de trades basados en la estrategia implementada.

Visualización de operaciones: Función generar_grafico que permite visualizar gráficamente las operaciones realizadas en un día específico.

Optimización de parámetros: Capacidad para ajustar los parámetros de la estrategia con el fin de mejorar la rentabilidad y el rendimiento.

## Tecnologías utilizadas y su propósito

### MetaTrader 5 (MetaTrader5)

Propósito: Conexión con la plataforma de trading MetaTrader 5.

Uso: Obtención de datos de mercado en tiempo real, ejecución de órdenes y monitoreo de posiciones.

### Módulos de manejo de tiempo (datetime, timezone, timedelta)

Propósito: Gestión de fechas y tiempos en diferentes zonas horarias.

Uso: Sincronización de operaciones de trading con la hora del mercado y manejo de eventos temporales.

### Pandas (pandas)
   
Propósito: Manipulación y análisis de datos estructurados en formato tabular.

Uso: Organización de datos de precios, generación de estadísticas y preparación de datos para su análisis.

### Mplfinance (mplfinance)
   
Propósito: Visualización de gráficos financieros (velas, líneas, etc.).

Uso: Representación gráfica de los movimientos del mercado y análisis de tendencias.

### Matplotlib (matplotlib.pyplot)
   
Propósito: Creación de gráficos y visualización de datos.

Uso: Complemento a mplfinance para agregar detalles y personalización en los gráficos generados.

## Ejemplo de visualización

La función generar_grafico mostrará un gráfico como este:

15/10/2024:

![trade_15-10-2024](https://github.com/user-attachments/assets/da0c73ab-5425-49c5-83f5-91d62b5eab23)

Donde las líneas horizontales representan los puntos clave del retroceso de Fibonacci, el rectángulo gris representa el Stop Loss y el azul el Take Profit.

## Advertencia

Este proyecto no está terminado y puede contener errores. No debe usarse en cuentas reales sin pruebas exhaustivas. El trading conlleva riesgos y puede generar pérdidas.

## Futuras mejoras

Implementar modelos de Deep Learning (redes recurrentes) para optimizar la estrategia.

Mejorar la eficiencia con procesamiento en paralelo.
