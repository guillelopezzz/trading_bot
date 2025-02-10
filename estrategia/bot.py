import numpy as np
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
from datetime import time
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from tqdm import tqdm

class Algorithm:
    """
    Clase base para representar un algoritmo genérico.
    Puedes extender esta clase para implementar algoritmos específicos.
    """

    def __init__(self, dia, mes, anio, max_session, min_session, start_session=(2, 0), end_session=(8, 55), pips = 2, max_pips = 10.8):
        """
        Constructor de la clase Algorithm.
        """
        self.start_session = start_session
        self.end_session = end_session
        self.max_session = max_session
        self.min_session = min_session
        self.max1 = []
        self.min1 = []
        self.lowfibonacci_compras = None
        self.highfibonacci_ventas = None
        self.highfibonacci_compras = None
        self.lowfibonacci_ventas = None
        self.rotura_compras = False
        self.rotura_ventas = False
        self.buscarcompras = False
        self.buscarventas = False
        self.fibonacci_compras = None
        self.fibonacci_ventas = None
        self.precio_compra_inicial = None
        self.precio_venta_inicial = None
        self.precio_compra_final = None
        self.precio_venta_final = None
        self.stoploss_compra = None
        self.takeprofit_compra = None
        self.stoploss_venta = None
        self.takeprofit_venta = None
        self.operacion_finalizada_compra = False
        self.operacion_finalizada_venta = False
        self.pips = pips # Número de pips por debajo/encima del mínimo/máximo de Fibonacci
        self.max_pips = max_pips # Máximo número de pips para el SL (si lo supera no se hace la operación)
        self.hora_inicio_operacion_compra = None
        self.hora_fin_operacion_compra = None
        self.hora_inicio_operacion_venta = None
        self.hora_fin_operacion_venta = None
        self.horas = {'hora_ruptura_sesion': None, 'hora_primer_fibonacci_compras': None, 'hora_segundo_fibonacci_compras': None, 'hora_primer_fibonacci_ventas': None, 'hora_segundo_fibonacci_ventas': None}
        self.fecha = (dia, mes, anio)
        self.max_antes_min = None
        self.min_antes_max = None
        self.highfibonacci_compras_anterior = float('-inf')
        self.lowfibonacci_ventas_anterior = float('inf')
        self.parar_busqueda_high_fibo = False
        self.parar_busqueda_low_fibo = False
        self.conjunto_fechas_maxmin_compra = set()
        self.conjunto_fechas_maxmin_venta = set()
        self.pausa_compra = False
        self.pausa_venta = False

    def fibonacci(self, price1, price2, direction, level):
        """
        Calcula el retroceso de Fibonacci al nivel level.

        :param price1: Precio de referencia 1 (float).
        :param price2: Precio de referencia 2 (float).
        :param direction: Dirección del cálculo ('up' para hacia arriba, 'down' para hacia abajo) (str).
        :return: Nivel de retroceso de Fibonacci al nivel level (float).
        """
        if direction == 'up':
            # Cálculo para un retroceso alcista
            return price1 - (price1 - price2) * (1 - level)
        elif direction == 'down':
            # Cálculo para un retroceso bajista
            return price1 + (price2 - price1) * (1 - level)
        
    def _reiniciar(self, tipo):
        """
        Reinicia las variables de compra o de venta para no hacer operaciones simultáneas

        """
        if tipo == 'compra' and not self.operacion_finalizada_compra:
            self.pausa_compra = True
            self.rotura_compras = False
            self.highfibonacci_compras = None
            self.highfibonacci_compras_anterior = float('-inf')
            self.horas['hora_segundo_fibonacci_compras'] = None
            self.fibonacci_compras = None

        if tipo == 'venta' and not self.operacion_finalizada_venta:
            self.pausa_venta = True
            self.rotura_ventas = False
            self.highfibonacci_ventas = None
            self.highfibonacci_ventas_anterior = float('inf')
            self.horas['hora_segundo_fibonacci_ventas'] = None
            self.fibonacci_compras = None

    def _process_data(self, new_data, last_three_candles):
        if not (self.operacion_finalizada_compra and self.operacion_finalizada_venta):
            # el dato viene en formato tick, ¿qué nos interesa? Nos interesa el precio bid y la hora. Aunque realmente solo nos interesa la hora de 01:00 a 07:55
            # también se necesitan las 3 últimas velas de temporalidad 5 minutos para poder hallar máximos y mínimos
            df_last_three_candles = pd.DataFrame(last_three_candles)
            #try:
            # Convertir el timestamp a una hora legible
            tick_time = datetime.fromtimestamp(new_data['time'], tz=timezone.utc)  # Asegura que la hora esté en UTC
            # Haremos una serie de condiciones para saber qué es lo que debemos hacer con el nuevo dato
            # Fase 1: 01:00-07:55, simplemente debemos identificar máximo y mínimo
            # Fase 3: buscamos máximo o mínimo
            if not self.rotura_compras:
                if df_last_three_candles['high'][0] <= df_last_three_candles['high'][1] >= df_last_three_candles['high'][2]:
                    if df_last_three_candles['time'][1] not in self.conjunto_fechas_maxmin_compra:
                        self.conjunto_fechas_maxmin_compra.add(df_last_three_candles['time'][1])
                        self.max1.append((df_last_three_candles['high'][1], df_last_three_candles['time'][1]))

            if not self.rotura_ventas:
                if df_last_three_candles['low'][0] >= df_last_three_candles['low'][1] <= df_last_three_candles['low'][2]:
                    if df_last_three_candles['time'][1] not in self.conjunto_fechas_maxmin_venta:
                        self.conjunto_fechas_maxmin_venta.add(df_last_three_candles['time'][1])
                        self.min1.append((df_last_three_candles['low'][1], df_last_three_candles['time'][1]))

            # Fase 2: Después de las 07:55 UTC+1, buscamos que se liquide el mínimo o el máximo (abrimos operación de compras o de ventas)
            end_session_time = time(*self.end_session)
            if tick_time.time() > end_session_time:
                if not self.buscarcompras:
                    if new_data['bid'] < self.min_session:
                        self.buscarcompras = True
                        self.horas['hora_ruptura_sesion'] = tick_time.time() # Para depurar

                if not self.buscarventas:
                    if new_data['bid'] > self.max_session:
                        self.buscarventas = True
                        self.horas['hora_ruptura_sesion'] = tick_time.time() # Para depurar

                # Fase 4: buscamos mínimo o máximo (que serán el mínimo Fibonacci o el máximo Fibonacci)
                if self.max1 and not self.rotura_compras and self.buscarcompras:
                    # Buscar el último máximo antes del nuevo mínimo sin pasarse
                    
                    if df_last_three_candles['low'][0] >= df_last_three_candles['low'][1] <= df_last_three_candles['low'][2]:
                        self.max_antes_min = max(
                            [(valor, tiempo) for valor, tiempo in self.max1 if tiempo < df_last_three_candles['time'][1]],
                            key=lambda x: x[1],  # Comparamos los valores de tiempo
                            default=None  # Si no hay un máximo previo, no hacer nada
                        )
                        self.lowfibonacci_compras = df_last_three_candles['low'][1]
                        self.horas['hora_primer_fibonacci_compras'] = df_last_three_candles['time'][1]  # Para depurar
                    
                if self.min1 and not self.rotura_ventas and self.buscarventas:
                    # Buscar el último mínimo antes del nuevo máximo sin pasarse
                    
                    if df_last_three_candles['high'][0] <= df_last_three_candles['high'][1] >= df_last_three_candles['high'][2]:
                        self.min_antes_max = max(
                            [(valor, tiempo) for valor, tiempo in self.min1 if tiempo < df_last_three_candles['time'][1]],
                            key=lambda x: x[1],  # Comparamos los valores de tiempo
                            default=None  # Si no hay un mínimo previo, no hacer nada
                        )
                        self.highfibonacci_ventas = df_last_three_candles['high'][1]
                        self.horas['hora_primer_fibonacci_ventas'] = df_last_three_candles['time'][1]  # Para depurar

                # Fase 5: buscamos que se rompa el máximo o el mínimo de la Fase 3
                if self.lowfibonacci_compras is not None and not self.rotura_compras and not self.pausa_compra:
                    if new_data['bid'] > self.max_antes_min[0]:
                        self.rotura_compras = True

                if self.highfibonacci_ventas is not None and not self.rotura_ventas and not self.pausa_venta:
                    if new_data['bid'] < self.min_antes_max[0]:
                        self.rotura_ventas = True

                # Fase 6: buscamos un máximo o un mínimo después de la rotura, que será nuestro máximo o mínimo de fibonacci
                if self.rotura_compras and self.precio_compra_inicial is None and not self.parar_busqueda_high_fibo and not self.pausa_compra:
                    if df_last_three_candles['high'][0] <= df_last_three_candles['high'][1] >= df_last_three_candles['high'][2] and df_last_three_candles['high'][1] > self.max_antes_min[0] and df_last_three_candles['high'][1] > self.highfibonacci_compras_anterior:
                        self.highfibonacci_compras = df_last_three_candles['high'][1]
                        self.horas['hora_segundo_fibonacci_compras'] = df_last_three_candles['time'][1]
                        self.highfibonacci_compras_anterior = df_last_three_candles['high'][1]
                        # Debemos recalcular fibonacci
                        self.fibonacci_compras = None

                if self.rotura_ventas and self.precio_venta_inicial is None and not self.parar_busqueda_low_fibo and not self.pausa_venta:
                    if df_last_three_candles['low'][0] >= df_last_three_candles['low'][1] <= df_last_three_candles['low'][2] and df_last_three_candles['low'][1]< self.min_antes_max[0] and df_last_three_candles['low'][1] < self.lowfibonacci_ventas_anterior:
                        self.lowfibonacci_ventas = df_last_three_candles['low'][1]
                        self.horas['hora_segundo_fibonacci_ventas'] = df_last_three_candles['time'][1]
                        self.lowfibonacci_ventas_anterior = df_last_three_candles['low'][1]
                        # Debemos recalcular Fibonacci
                        self.fibonacci_ventas = None

                # Fase 7: Marcamos Fibonacci 0.618
                if self.highfibonacci_compras is not None and self.fibonacci_compras is None and not self.pausa_compra:
                    self.fibonacci_compras = self.fibonacci(self.lowfibonacci_compras, self.highfibonacci_compras, 'down', 0.618)
                if self.lowfibonacci_ventas is not None and self.fibonacci_ventas is None and not self.pausa_venta:
                    self.fibonacci_ventas = self.fibonacci(self.highfibonacci_ventas, self.lowfibonacci_ventas, 'up', 0.618)

                # Fase 8: Cuando el precio retroceda al Fibonacci que marcamos, abrimos posición de compra/venta
                if self.fibonacci_compras is not None and self.precio_compra_inicial is None and not self.pausa_compra:
                    if new_data['bid'] <= self.fibonacci_compras:
                        self._reiniciar('venta')
                        self.parar_busqueda_high_fibo = True
                        self.stoploss_compra = self.lowfibonacci_compras - (0.0001 * self.pips)  # SL a self.pips por debajo del nivel Fibonacci
                        risk = new_data['bid'] - self.stoploss_compra  # Distancia entre el precio actual y el SL
                        if risk > self.max_pips * 0.0001:
                            self.stoploss_compra = self.fibonacci(self.lowfibonacci_compras, self.highfibonacci_compras, 'down', 0.7) - 0.0003 # 3 pips por debajo de Fibo 0.7
                            risk = new_data['bid'] - self.stoploss_compra
                            if risk > self.max_pips * 0.0001:
                                self.operacion_finalizada_compra = True
                                self.pausa_venta = False
                        self.precio_compra_inicial = new_data['bid'] # abrimos operación de compra
                        self.hora_inicio_operacion_compra = tick_time.time()
                        self.takeprofit_compra = new_data['bid'] + 2 * risk  # TP a 2 veces la distancia desde el precio actual al SL
                        
                if self.fibonacci_ventas is not None and self.precio_venta_inicial is None and not self.pausa_venta:
                    if new_data['bid'] >= self.fibonacci_ventas:
                        self._reiniciar('compra')
                        self.parar_busqueda_low_fibo = True
                        self.stoploss_venta = self.highfibonacci_ventas + (0.0001 * self.pips)  # SL a self.pips por encima del nivel Fibonacci
                        risk = self.stoploss_venta - new_data['bid']  # Distancia entre el SL y el precio actual
                        if risk > self.max_pips * 0.0001:
                            self.stoploss_venta = self.fibonacci(self.highfibonacci_ventas, self.lowfibonacci_ventas, 'up', 0.7) + 0.0003 # 3 pips por encima de Fibo 0.7
                            risk = self.stoploss_venta - new_data['bid']
                            if risk > self.max_pips * 0.0001:
                                self.operacion_finalizada_venta = True
                                self.pausa_compra = False
                        self.precio_venta_inicial = new_data['bid'] # abrimos operación de venta
                        self.hora_inicio_operacion_venta = tick_time.time()
                        self.takeprofit_venta = new_data['bid'] - 2 * risk  # TP a 2 veces la distancia desde el precio actual al SL

                # Fase 9: El SL estará 2 pips por debajo/encima del mínimo/máximo de Fibonacci con un límite de 10.8 pips. TP = 2*SL
                if self.precio_compra_inicial is not None and not self.operacion_finalizada_compra:
                    if new_data['bid'] >= self.takeprofit_compra:
                        self.precio_compra_final = new_data['bid'] # Ganamos
                        self.operacion_finalizada_compra = True
                        self.pausa_venta = False
                        self.hora_fin_operacion_compra = tick_time.time()

                    if new_data['bid'] <= self.stoploss_compra:
                        self.precio_compra_final = new_data['bid'] # Perdemos
                        self.operacion_finalizada_compra = True
                        self.pausa_venta = False
                        self.hora_fin_operacion_compra = tick_time.time()

                if self.precio_venta_inicial is not None and not self.operacion_finalizada_venta:
                    if new_data['bid'] <= self.takeprofit_venta:
                        self.precio_venta_final = new_data['bid'] # Ganamos
                        self.operacion_finalizada_venta = True
                        self.pausa_compra = False
                        self.hora_fin_operacion_venta =tick_time.time()

                    if new_data['bid'] >= self.stoploss_venta:
                        self.precio_venta_final = new_data['bid'] # Perdemos
                        self.operacion_finalizada_venta = True
                        self.pausa_compra = False
                        self.hora_fin_operacion_venta = tick_time.time()

        #except Exception as e:
            #print(f"Error al obtener o procesar el tick: {e}")

    def __str__(self):
        info = (
            f"Fecha: {self.fecha[0]:02d}/{self.fecha[1]:02d}/{self.fecha[2]}\n"
            f"Sesión: {self.start_session[0]:02d}:{self.start_session[1]:02d} - {self.end_session[0]:02d}:{self.end_session[1]:02d}\n"
            f"Mínimo de sesión: {self.min_session}\n"
            f"Máximo de sesión: {self.max_session}\n"
            f"Máximo 1: {self.max1}\n"
            f"Mínimo 1: {self.min1}\n"
            f"Fibonacci compras: {self.fibonacci_compras} (Low: {self.lowfibonacci_compras}, High: {self.highfibonacci_compras})\n"
            f"Fibonacci ventas: {self.fibonacci_ventas} (Low: {self.lowfibonacci_ventas}, High: {self.highfibonacci_ventas})\n"
            f"Rotura compras: {'Sí' if self.rotura_compras else 'No'}\n"
            f"Rotura ventas: {'Sí' if self.rotura_ventas else 'No'}\n"
            f"Buscar compras: {'Sí' if self.buscarcompras else 'No'}\n"
            f"Buscar ventas: {'Sí' if self.buscarventas else 'No'}\n"
            f"Precio compra: Inicial {self.precio_compra_inicial}, Final {self.precio_compra_final}\n"
            f"Precio venta: Inicial {self.precio_venta_inicial}, Final {self.precio_venta_final}\n"
            f"Stoploss compra: {self.stoploss_compra}\n"
            f"Takeprofit compra: {self.takeprofit_compra}\n"
            f"Stoploss venta: {self.stoploss_venta}\n"
            f"Takeprofit venta: {self.takeprofit_venta}\n"
            f"Operación finalizada compra: {'Sí' if self.operacion_finalizada_compra else 'No'}\n"
            f"Operación finalizada venta: {'Sí' if self.operacion_finalizada_venta else 'No'}\n"
            f"Pips: {self.pips}, Máx. Pips: {self.max_pips}\n"
            f"Hora inicio operación compra: {self.hora_inicio_operacion_compra}\n"
            f"Hora fin operación compra: {self.hora_fin_operacion_compra}\n"
            f"Hora inicio operación venta: {self.hora_inicio_operacion_venta}\n"
            f"Hora fin operación venta: {self.hora_fin_operacion_venta}\n"
            f"Horas clave:\n"
            f"  - Ruptura sesión: {self.horas['hora_ruptura_sesion']}\n"
            f"  - Primer Fibonacci compras: {self.horas['hora_primer_fibonacci_compras']}\n"
            f"  - Primer Fibonacci ventas: {self.horas['hora_primer_fibonacci_ventas']}\n"
            f"  - Segundo Fibonacci compras: {self.horas['hora_primer_fibonacci_compras']}\n"
            f"  - Segundo Fibonacci ventas: {self.horas['hora_segundo_fibonacci_ventas']}\n"
        )
        return info

    def generar_grafico(self):
        # Esta función será para representar gráficamente lo que hizo el algoritmo
        # Conectar a la cuenta demo
        if not mt5.initialize():
            print("Error al iniciar MetaTrader 5")
            mt5.shutdown()
        # Definir el rango de fechas para el día 15 de octubre de 2024
        
        start_date = datetime(self.fecha[2], self.fecha[1], self.fecha[0], 1, 0, tzinfo=timezone.utc)
        end_date = datetime(self.fecha[2], self.fecha[1], self.fecha[0], 21, 0, tzinfo=timezone.utc)

        # Obtener los datos de precios en UTC
        rates = mt5.copy_rates_range("EURUSD", mt5.TIMEFRAME_M5, start_date, end_date)
        # Desconectar de MetaTrader 5
        mt5.shutdown()

        # Convertir los datos a un DataFrame de pandas
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        # Crear un estilo personalizado con los colores deseados
        custom_style = mpf.make_mpf_style(
            marketcolors=mpf.make_marketcolors(
                up='#a8b6d9',  # Color de las velas alcistas
                down='#919398',   # Color de las velas bajistas
                wick='black',  # Color de las mechas
                edge='black',  # Color del borde de las velas
            )
        )

        # Configuración para las gráficas de velas de mplfinance
        kwargs = dict(
            type='candle',
            volume=False,
            style=custom_style,  # Usar el estilo personalizado
            figratio=(12, 6),
            figscale=1.2,
        )

        # Crear la gráfica de velas
        fig, ax = mpf.plot(df, **kwargs, returnfig=True)

        ax[0].yaxis.tick_right()
        fecha_str = f"{self.fecha[0]}/{self.fecha[1]}/{self.fecha[2]}"
        ax[0].set_title(f"Euro/Dólar estadounidense, {fecha_str}", loc='left', fontsize=8, pad=10)

        for spine in ax[0].spines.values():
            spine.set_visible(False)

        ### DIBUJAR TP compra
        if self.operacion_finalizada_compra:
            if self.precio_compra_final is not None:

                price_low = self.precio_compra_inicial
                price_high = self.takeprofit_compra

            if self.hora_inicio_operacion_compra is not None and self.hora_fin_operacion_compra is not None:
                start_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.hora_inicio_operacion_compra.hour, self.hora_inicio_operacion_compra.minute)
                end_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.hora_fin_operacion_compra.hour, self.hora_fin_operacion_compra.minute)

                # Encontrar los índices más cercanos con get_indexer
                start_idx = df.index.get_indexer([start_rect], method='nearest')[0]
                end_idx = df.index.get_indexer([end_rect], method='nearest')[0]

                # Dibujar el rectángulo
                rect = Rectangle((start_idx, price_low), end_idx - start_idx, price_high - price_low,
                                facecolor='cyan', alpha=0.1)
                ax[0].add_patch(rect)

        ### DIBUJAR SL compra
            if self.precio_compra_final is not None:
                price_low = self.stoploss_compra
                price_high = self.precio_compra_inicial

            if self.hora_inicio_operacion_compra is not None and self.hora_fin_operacion_compra is not None:
                start_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.hora_inicio_operacion_compra.hour, self.hora_inicio_operacion_compra.minute)
                end_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.hora_fin_operacion_compra.hour, self.hora_fin_operacion_compra.minute)

                # Encontrar los índices más cercanos con get_indexer
                start_idx = df.index.get_indexer([start_rect], method='nearest')[0]
                end_idx = df.index.get_indexer([end_rect], method='nearest')[0]

                # Dibujar el rectángulo
                rect = Rectangle((start_idx, price_low), end_idx - start_idx, price_high - price_low,
                                facecolor='gray', alpha=0.2)
                ax[0].add_patch(rect)

        ### DIBUJAR TP venta
        if self.operacion_finalizada_venta:
            if self.precio_venta_final is not None:

                price_low = self.takeprofit_venta
                price_high = self.precio_venta_inicial

            if self.hora_inicio_operacion_venta is not None and self.hora_fin_operacion_venta is not None:
                start_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.hora_inicio_operacion_venta.hour, self.hora_inicio_operacion_venta.minute)
                end_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.hora_fin_operacion_venta.hour, self.hora_fin_operacion_venta.minute)

                # Encontrar los índices más cercanos con get_indexer
                start_idx = df.index.get_indexer([start_rect], method='nearest')[0]
                end_idx = df.index.get_indexer([end_rect], method='nearest')[0]

                # Dibujar el rectángulo
                rect = Rectangle((start_idx, price_low), end_idx - start_idx, price_high - price_low,
                                facecolor='cyan', alpha=0.1)
                ax[0].add_patch(rect)

        ### DIBUJAR SL venta
            if self.precio_venta_final is not None:
                price_low = self.precio_venta_inicial
                price_high = self.stoploss_venta

            if self.hora_inicio_operacion_venta is not None and self.hora_fin_operacion_venta is not None:
                start_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.hora_inicio_operacion_venta.hour, self.hora_inicio_operacion_venta.minute)
                end_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.hora_fin_operacion_venta.hour, self.hora_fin_operacion_venta.minute)

                # Encontrar los índices más cercanos con get_indexer
                start_idx = df.index.get_indexer([start_rect], method='nearest')[0]
                end_idx = df.index.get_indexer([end_rect], method='nearest')[0]

                # Dibujar el rectángulo
                rect = Rectangle((start_idx, price_low), end_idx - start_idx, price_high - price_low,
                                facecolor='gray', alpha=0.2)
                ax[0].add_patch(rect)

        ## DIBUJAR SESIÓN TOKIO

        # Convertir las marcas de tiempo a Timestamp
        start_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.start_session[0], self.start_session[1])
        end_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.end_session[0], self.end_session[1])

        # Encontrar los índices más cercanos con get_indexer
        start_idx = df.index.get_indexer([start_rect], method='nearest')[0]
        end_idx = df.index.get_indexer([end_rect], method='nearest')[0]

        price_low = self.min_session
        price_high = self.max_session


        # Dibujar el rectángulo
        rect = Rectangle((start_idx, price_low), end_idx - start_idx, price_high - price_low,
                        facecolor='gray', alpha=0.1)
        ax[0].add_patch(rect)

        ## DIBUJAR FIBONACCI compras

        if self.fibonacci_compras is not None:
            price_low = self.fibonacci_compras
            price_high = self.fibonacci_compras
        # Dibujar el rectángulo
        if self.horas['hora_primer_fibonacci_compras'] is not None and self.horas['hora_segundo_fibonacci_compras'] is not None:
            df.index = df.index.tz_convert('UTC') if df.index.tz else df.index.tz_localize('UTC')
            # Convertir las marcas de tiempo a UTC
            start_rect = self.horas['hora_primer_fibonacci_compras']
            end_rect = self.horas['hora_segundo_fibonacci_compras']

            # Encontrar los índices más cercanos con get_indexer
            start_idx = df.index.get_indexer([start_rect], method='nearest')[0]
            end_idx = df.index.get_indexer([end_rect], method='nearest')[0]
            rect = Rectangle((start_idx, price_low), end_idx - start_idx, 0,
                            linewidth=1, edgecolor='black', alpha=1)
            ax[0].add_patch(rect)

        if self.lowfibonacci_compras is not None:
            price_low = self.lowfibonacci_compras
            price_high = self.lowfibonacci_compras

        if self.lowfibonacci_compras is not None:
            # Dibujar el rectángulo
            rect = Rectangle((start_idx, price_low), end_idx - start_idx, 0,
                            linewidth=1, edgecolor='black', alpha=1)
            ax[0].add_patch(rect)

        if self.highfibonacci_compras is not None:
            # Dibujar el rectángulo
            rect = Rectangle((start_idx, self.highfibonacci_compras), end_idx - start_idx, 0,
                            linewidth=1, edgecolor='black', alpha=1)
            ax[0].add_patch(rect)

        ## DIBUJAR FIBONACCI ventas

        if self.fibonacci_ventas is not None:
            price_low = self.fibonacci_ventas
            price_high = self.fibonacci_ventas
        # Dibujar el rectángulo
        if self.horas['hora_primer_fibonacci_ventas'] is not None and self.horas['hora_segundo_fibonacci_ventas'] is not None:
            df.index = df.index.tz_convert('UTC') if df.index.tz else df.index.tz_localize('UTC')
            # Convertir las marcas de tiempo a UTC
            start_rect = self.horas['hora_primer_fibonacci_ventas']
            end_rect = self.horas['hora_segundo_fibonacci_ventas']

            # Encontrar los índices más cercanos con get_indexer
            start_idx = df.index.get_indexer([start_rect], method='nearest')[0]
            end_idx = df.index.get_indexer([end_rect], method='nearest')[0]
            rect = Rectangle((start_idx, price_low), end_idx - start_idx, 0,
                            linewidth=1, edgecolor='black', alpha=1)
            ax[0].add_patch(rect)

        if self.lowfibonacci_compras is not None:
            price_low = self.lowfibonacci_compras
            price_high = self.lowfibonacci_compras

        if self.lowfibonacci_ventas is not None:
            price_low = self.lowfibonacci_ventas
            price_high = self.lowfibonacci_ventas

        if self.lowfibonacci_compras is not None or self.lowfibonacci_ventas is not None:
            # Dibujar el rectángulo
            rect = Rectangle((start_idx, price_low), end_idx - start_idx, price_high - price_low,
                            linewidth=1, edgecolor='black', alpha=1)
            ax[0].add_patch(rect)

        if self.highfibonacci_ventas is not None:
            # Dibujar el rectángulo
            rect = Rectangle((start_idx, self.highfibonacci_ventas), end_idx - start_idx, 0,
                            linewidth=1, edgecolor='black', alpha=1)
            ax[0].add_patch(rect)

        plt.show()

dia = int(input('Introduce el día: '))
mes = int(input('Introduce el mes: '))
anio = int(input('Introduce el año: '))

# Iniciar MetaTrader 5
if not mt5.initialize():
    print("Error al iniciar MetaTrader 5")
    mt5.shutdown()

# Definir los parámetros
symbol = "EURUSD"
timeframe = mt5.TIMEFRAME_M5
start_time = datetime(anio, mes, dia, 2, 0, 0, tzinfo=timezone.utc)  # 01:00 UTC+1
end_time = datetime(anio, mes, dia, 8, 55, 0, tzinfo=timezone.utc)  # 07:55 UTC+1


# Obtener los datos históricos de MetaTrader 5
rates_session = mt5.copy_rates_range(symbol, timeframe, start_time, end_time)

# Convertir a DataFrame
df_session = pd.DataFrame(rates_session)

# Calcular el mínimo de los mínimos y el máximo de los máximos
min_session = df_session['low'].min()
max_session = df_session['high'].max()


# Una vez tenemos el máximo y el mínimo de la sesión
start_time = datetime(anio, mes, dia, 2, 0
                      , 0, tzinfo=timezone.utc)  # 07:55 UTC+1
end_time = datetime(anio, mes, dia, 21, 0, 0, tzinfo=timezone.utc)  # 20:00 UTC+1



# Obtener los datos históricos de MetaTrader 5
rates = mt5.copy_rates_range(symbol, timeframe, start_time, end_time)
ticks = mt5.copy_ticks_range(symbol, start_time, end_time, mt5.COPY_TICKS_ALL)

# Comprobar si obtuvimos datos
if rates is None or len(rates) == 0:
    print("No se obtuvieron datos de las velas.")
else:
    print(f"Datos de velas obtenidos: {len(rates)}")

if ticks is None or len(ticks) == 0:
    print("No se obtuvieron datos de ticks.")
else:
    print(f"Datos de ticks obtenidos: {len(ticks)}")

# Convertir los datos a un DataFrame de velas (5 minutos)
df_candles = pd.DataFrame(rates)
df_candles['time'] = pd.to_datetime(df_candles['time'], unit='s', utc=True)

# Convertir los datos a un DataFrame de ticks
df_ticks = pd.DataFrame(ticks)
df_ticks['time'] = pd.to_datetime(df_ticks['time'], unit='s', utc=True)
# Instancia del algoritmo
algo = Algorithm(dia=dia, mes=mes, anio= anio, start_session=(2, 0), end_session=(8, 55), max_session=max_session, min_session=min_session, pips=2, max_pips=10.8)

# Recorrer los datos de ticks y procesarlos
# Asegurarse de que estamos trabajando con el índice correcto
# Recorrer los datos de velas y ticks

i = 0
pbar = tqdm(total=len(df_ticks), desc="Procesando ticks", unit="tick")
while i < len(df_ticks):
    tick = df_ticks.iloc[i]
    # Obtener las tres velas previas al tick actual
    last_three_candles = df_candles[df_candles['time'] < tick['time']].iloc[-3:][['time', 'high', 'low']].to_dict('records')
    if len(last_three_candles) == 3:  # Solo procesamos si tenemos 3 velas anteriores
        # Datos del tick para procesar
        new_data = {'time': int(tick['time'].timestamp()),  # Aseguramos que 'time' es un timestamp entero
                    'bid': tick['bid'],  # Usamos el precio 'bid' de los ticks
                    'ask': tick['ask']}
        # Llamar al método _process_data con los datos actualizados
        algo._process_data(new_data, last_three_candles)
        pbar.update(1)
        if algo.operacion_finalizada_compra and algo.operacion_finalizada_venta: break
    i += 1
# Cerrar la conexión con MetaTrader 5
mt5.shutdown()

print(algo)
algo.generar_grafico()