🤖 Trading Automation Bot – Forex EUR/USD

Este proyecto es una automatización de las operaciones de un trader rentable en el mercado Forex, específicamente en el par EUR/USD. Se basa en una simulación en tiempo real donde se procesan los precios uno a uno y se aplica una estrategia de trading. Además, cuenta con una función generar_grafico que permite visualizar gráficamente las operaciones realizadas en un día concreto.

🚀 Funcionalidades

✔ Simulación de streaming: Procesamiento secuencial de precios como si fuera un mercado en vivo.

✔ Automatización de operaciones: Apertura y cierre de trades según la estrategia definida.

✔ Visualización de operaciones: Función generar_grafico que muestra qué ha hecho el bot en un día específico.

✔ Optimización de parámetros: Se pueden ajustar distintos valores de la estrategia para mejorar la rentabilidad.

📌 Tecnologías utilizadas y su propósito
1️⃣ MetaTrader 5 (MetaTrader5)
📌 Propósito: API para conectar con la plataforma de trading MetaTrader 5.
✅ Se usa para obtener datos del mercado, ejecutar órdenes y monitorear posiciones.

2️⃣ datetime, timezone y timedelta
📌 Propósito: Manejo de fechas y tiempos en diferentes zonas horarias.
✅ Se usa para sincronizar operaciones de trading con la hora del mercado.

3️⃣ pandas (pandas)
📌 Propósito: Manipulación y análisis de datos estructurados en formato tabular.
✅ Se usa para organizar datos de precios, generar estadísticas y alimentar modelos.

4️⃣ mplfinance (mplfinance)
📌 Propósito: Visualización de gráficos financieros (velas, líneas, etc.).
✅ Se usa para graficar los movimientos del mercado y analizar tendencias.

5️⃣ matplotlib (matplotlib.pyplot)
📌 Propósito: Creación de gráficos y visualización de datos.
✅ Se usa en conjunto con mplfinance para agregar detalles a los gráficos.
