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
        self.fibonacci_puntos = {'low_compras': None, 'high_ventas': None, 'high_compras': None, 'low_ventas': None}
        self.roturas = {'compras': False, 'ventas': False}
        self.buscar = {'compras': False, 'ventas': False}
        self.fibonacci618 = {'compras': None, 'ventas': None}
        self.precios = {'compra_inicial': None, 'venta_inicial': None, 'compra_final': None, 'venta_final': None}
        self.tpysl = {'stoploss_compra': None, 'takeprofit_compra': None, 'stoploss_venta': None, 'takeprofit_venta': None}
        self.operacion_finalizada = {'compra': False, 'venta': False}
        self.pips = pips # Número de pips por debajo/encima del mínimo/máximo de Fibonacci
        self.max_pips = max_pips # Máximo número de pips para el SL (si lo supera no se hace la operación)
        self.horas_operacion = {'inicio_compra': None, 'fin_compra': None, 'inicio_venta': None, 'fin_venta': None}
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
        self.pausa = {'compra': False, 'venta': False}

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
        if tipo == 'compra' and not self.operacion_finalizada['compra']:
            self.pausa['compra'] = True
            self.roturas['compras'] = False
            self.fibonacci_puntos['high_compras'] = None
            self.highfibonacci_compras_anterior = float('-inf')
            self.horas['hora_segundo_fibonacci_compras'] = None
            self.fibonacci618['compras'] = None

        if tipo == 'venta' and not self.operacion_finalizada['venta']:
            self.pausa['venta'] = True
            self.roturas['ventas'] = False
            self.fibonacci_puntos['low_ventas'] = None
            self.lowfibonacci_ventas_anterior = float('inf')
            self.horas['hora_segundo_fibonacci_ventas'] = None
            self.fibonacci618['ventas'] = None

    def _process_data(self, new_data, last_three_candles):
        if not (self.operacion_finalizada['compra'] and self.operacion_finalizada['venta']):
            # el dato viene en formato tick, ¿qué nos interesa? Nos interesa el precio bid y la hora. Aunque realmente solo nos interesa la hora de 01:00 a 07:55
            # también se necesitan las 3 últimas velas de temporalidad 5 minutos para poder hallar máximos y mínimos
            df_last_three_candles = pd.DataFrame(last_three_candles)
            #try:
            # Convertir el timestamp a una hora legible
            tick_time = datetime.fromtimestamp(new_data['time'], tz=timezone.utc)  # Asegura que la hora esté en UTC
            # Haremos una serie de condiciones para saber qué es lo que debemos hacer con el nuevo dato
            # Fase 1: 01:00-07:55, simplemente debemos identificar máximo y mínimo
            # Fase 3: buscamos máximo o mínimo
            if not self.roturas['compras']:
                if df_last_three_candles['high'][0] <= df_last_three_candles['high'][1] >= df_last_three_candles['high'][2]:
                    if df_last_three_candles['time'][1] not in self.conjunto_fechas_maxmin_compra:
                        self.conjunto_fechas_maxmin_compra.add(df_last_three_candles['time'][1])
                        self.max1.append((df_last_three_candles['high'][1], df_last_three_candles['time'][1]))

            if not self.roturas['ventas']:
                if df_last_three_candles['low'][0] >= df_last_three_candles['low'][1] <= df_last_three_candles['low'][2]:
                    if df_last_three_candles['time'][1] not in self.conjunto_fechas_maxmin_venta:
                        self.conjunto_fechas_maxmin_venta.add(df_last_three_candles['time'][1])
                        self.min1.append((df_last_three_candles['low'][1], df_last_three_candles['time'][1]))

            # Fase 2: Después de las 07:55 UTC+1, buscamos que se liquide el mínimo o el máximo (abrimos operación de compras o de ventas)
            end_session_time = time(*self.end_session)
            if tick_time.time() > end_session_time:
                if not self.buscar['compras']:
                    if new_data['bid'] < self.min_session:
                        self.buscar['compras'] = True
                        self.horas['hora_ruptura_sesion'] = tick_time.time() # Para depurar

                if not self.buscar['ventas']:
                    if new_data['bid'] > self.max_session:
                        self.buscar['ventas'] = True
                        self.horas['hora_ruptura_sesion'] = tick_time.time() # Para depurar

                # Fase 4: buscamos mínimo o máximo (que serán el mínimo Fibonacci o el máximo Fibonacci)
                if self.max1 and not self.roturas['compras'] and self.buscar['compras']:
                    # Buscar el último máximo antes del nuevo mínimo sin pasarse
                    
                    if df_last_three_candles['low'][0] >= df_last_three_candles['low'][1] <= df_last_three_candles['low'][2]:
                        self.max_antes_min = max(
                            [(valor, tiempo) for valor, tiempo in self.max1 if tiempo < df_last_three_candles['time'][1]],
                            key=lambda x: x[1],  # Comparamos los valores de tiempo
                            default=None  # Si no hay un máximo previo, no hacer nada
                        )
                        self.fibonacci_puntos['low_compras'] = df_last_three_candles['low'][1]
                        self.horas['hora_primer_fibonacci_compras'] = df_last_three_candles['time'][1]  # Para depurar
                    
                if self.min1 and not self.roturas['ventas'] and self.buscar['ventas']:
                    # Buscar el último mínimo antes del nuevo máximo sin pasarse
                    
                    if df_last_three_candles['high'][0] <= df_last_three_candles['high'][1] >= df_last_three_candles['high'][2]:
                        self.min_antes_max = max(
                            [(valor, tiempo) for valor, tiempo in self.min1 if tiempo < df_last_three_candles['time'][1]],
                            key=lambda x: x[1],  # Comparamos los valores de tiempo
                            default=None  # Si no hay un mínimo previo, no hacer nada
                        )
                        self.fibonacci_puntos['high_ventas'] = df_last_three_candles['high'][1]
                        self.horas['hora_primer_fibonacci_ventas'] = df_last_three_candles['time'][1]  # Para depurar

                # Fase 5: buscamos que se rompa el máximo o el mínimo de la Fase 3
                if self.fibonacci_puntos['low_compras'] is not None and not self.roturas['compras'] and not self.pausa['compra']:
                    if new_data['bid'] > self.max_antes_min[0]:
                        self.roturas['compras'] = True

                if self.fibonacci_puntos['high_ventas'] is not None and not self.roturas['ventas'] and not self.pausa['venta']:
                    if new_data['bid'] < self.min_antes_max[0]:
                        self.roturas['ventas'] = True

                # Fase 6: buscamos un máximo o un mínimo después de la rotura, que será nuestro máximo o mínimo de fibonacci
                if self.roturas['compras'] and self.precios['compra_inicial'] is None and not self.parar_busqueda_high_fibo and not self.pausa['compra']:
                    if df_last_three_candles['high'][0] <= df_last_three_candles['high'][1] >= df_last_three_candles['high'][2] and df_last_three_candles['high'][1] > self.max_antes_min[0] and df_last_three_candles['high'][1] > self.highfibonacci_compras_anterior:
                        self.fibonacci_puntos['high_compras'] = df_last_three_candles['high'][1]
                        self.horas['hora_segundo_fibonacci_compras'] = df_last_three_candles['time'][1]
                        self.highfibonacci_compras_anterior = df_last_three_candles['high'][1]
                        # Debemos recalcular Fibonacci
                        self.fibonacci618['compras'] = None

                if self.roturas['ventas'] and self.precios['venta_inicial'] is None and not self.parar_busqueda_low_fibo and not self.pausa['venta']:
                    if df_last_three_candles['low'][0] >= df_last_three_candles['low'][1] <= df_last_three_candles['low'][2] and df_last_three_candles['low'][1]< self.min_antes_max[0] and df_last_three_candles['low'][1] < self.lowfibonacci_ventas_anterior:
                        self.fibonacci_puntos['low_ventas'] = df_last_three_candles['low'][1]
                        self.horas['hora_segundo_fibonacci_ventas'] = df_last_three_candles['time'][1]
                        self.lowfibonacci_ventas_anterior = df_last_three_candles['low'][1]
                        # Debemos recalcular Fibonacci
                        self.fibonacci618['ventas'] = None

                # Fase 7: Marcamos Fibonacci 0.618
                if self.fibonacci_puntos['high_compras'] is not None and self.fibonacci618['compras'] is None and not self.pausa['compra']:
                    self.fibonacci618['compras'] = self.fibonacci(self.fibonacci_puntos['low_compras'], self.fibonacci_puntos['high_compras'], 'down', 0.618)
                if self.fibonacci_puntos['low_ventas'] is not None and self.fibonacci618['ventas'] is None and not self.pausa['venta']:
                    self.fibonacci618['ventas'] = self.fibonacci(self.fibonacci_puntos['high_ventas'], self.fibonacci_puntos['low_ventas'], 'up', 0.618)

                # Fase 8: Cuando el precio retroceda al Fibonacci que marcamos, abrimos posición de compra/venta
                if self.fibonacci618['compras'] is not None and self.precios['compra_inicial'] is None and not self.pausa['compra']:
                    if new_data['bid'] <= self.fibonacci618['compras']:
                        self._reiniciar('venta')
                        self.parar_busqueda_high_fibo = True
                        self.tpysl['stoploss_compra'] = self.fibonacci_puntos['low_compras'] - (0.0001 * self.pips)  # SL a self.pips por debajo del nivel Fibonacci
                        risk = new_data['bid'] - self.tpysl['stoploss_compra']  # Distancia entre el precio actual y el SL
                        if risk > self.max_pips * 0.0001:
                            self.tpysl['stoploss_compra'] = self.fibonacci(self.fibonacci_puntos['low_compras'], self.fibonacci_puntos['high_compras'], 'down', 0.7) - 0.0003 # 3 pips por debajo de Fibo 0.7
                            risk = new_data['bid'] - self.tpysl['stoploss_compra']
                            if risk > self.max_pips * 0.0001:
                                self.operacion_finalizada['compra'] = True
                                self.pausa['ventas'] = False
                        self.precios['compra_inicial'] = new_data['bid'] # abrimos operación de compra
                        self.horas_operacion['inicio_compra'] = tick_time.time()
                        self.tpysl['takeprofit_compra'] = new_data['bid'] + 2 * risk  # TP a 2 veces la distancia desde el precio actual al SL
                        
                if self.fibonacci618['ventas'] is not None and self.precios['venta_inicial'] is None and not self.pausa['venta']:
                    if new_data['bid'] >= self.fibonacci618['ventas']:
                        self._reiniciar('compra')
                        self.parar_busqueda_low_fibo = True
                        self.tpysl['stoploss_venta'] = self.fibonacci_puntos['high_ventas'] + (0.0001 * self.pips)  # SL a self.pips por encima del nivel Fibonacci
                        risk = self.tpysl['stoploss_venta'] - new_data['bid']  # Distancia entre el SL y el precio actual
                        if risk > self.max_pips * 0.0001:
                            self.tpysl['stoploss_venta'] = self.fibonacci(self.fibonacci_puntos['high_ventas'], self.fibonacci_puntos['low_ventas'], 'up', 0.7) + 0.0003 # 3 pips por encima de Fibo 0.7
                            risk = self.tpysl['stoploss_venta'] - new_data['bid']
                            if risk > self.max_pips * 0.0001:
                                self.operacion_finalizada['venta'] = True
                                self.pausa['compras'] = False
                        self.precios['venta_inicial'] = new_data['bid'] # abrimos operación de venta
                        self.horas_operacion['inicio_venta'] = tick_time.time()
                        self.tpysl['takeprofit_venta'] = new_data['bid'] - 2 * risk  # TP a 2 veces la distancia desde el precio actual al SL

                # Fase 9: El SL estará 2 pips por debajo/encima del mínimo/máximo de Fibonacci con un límite de 10.8 pips. TP = 2*SL
                if self.precios['compra_inicial'] is not None and not self.operacion_finalizada['compra']:
                    if new_data['bid'] >= self.tpysl['takeprofit_compra']:
                        self.precios['compra_final'] = new_data['bid'] # Ganamos
                        self.operacion_finalizada['compra'] = True
                        self.pausa['venta'] = False
                        self.horas_operacion['fin_compra'] = tick_time.time()

                    if new_data['bid'] <= self.tpysl['stoploss_compra']:
                        self.precios['compra_final'] = new_data['bid'] # Perdemos
                        self.operacion_finalizada['compra'] = True
                        self.pausa['venta'] = False
                        self.horas_operacion['fin_compra'] = tick_time.time()

                if self.precios['venta_inicial'] is not None and not self.operacion_finalizada['venta']:
                    if new_data['bid'] <= self.tpysl['takeprofit_venta']:
                        self.precios['venta_final'] = new_data['bid'] # Ganamos
                        self.operacion_finalizada['venta'] = True
                        self.pausa['compra'] = False
                        self.horas_operacion['fin_venta'] =tick_time.time()

                    if new_data['bid'] >= self.tpysl['stoploss_venta']:
                        self.precios['venta_final'] = new_data['bid'] # Perdemos
                        self.operacion_finalizada['venta'] = True
                        self.pausa['compra'] = False
                        self.horas_operacion['fin_venta'] = tick_time.time()

        #except Exception as e:
            #print(f"Error al obtener o procesar el tick: {e}")

    def __str__(self):
        info = (
            f"Fecha: {self.fecha[0]:02d}/{self.fecha[1]:02d}/{self.fecha[2]}\n"
            f"Sesión: {self.start_session[0]:02d}:{self.start_session[1]:02d} - {self.end_session[0]:02d}:{self.end_session[1]:02d}\n"
            f"Mínimo de sesión: {self.min_session}\n"
            f"Máximo de sesión: {self.max_session}\n"
            f"Máximos 1: {self.max1}\n"
            f"Mínimos 1: {self.min1}\n"
            f"Puntos de Fibonacci: Low Compras: {self.fibonacci_puntos['low_compras']}, High Ventas: {self.fibonacci_puntos['high_ventas']}, "
            f"High Compras: {self.fibonacci_puntos['high_compras']}, Low Ventas: {self.fibonacci_puntos['low_ventas']}\n"
            f"Fibonacci 61.8%: Compras: {self.fibonacci618['compras']}, Ventas: {self.fibonacci618['ventas']}\n"
            f"Roturas: Compras: {'Sí' if self.roturas['compras'] else 'No'}, Ventas: {'Sí' if self.roturas['ventas'] else 'No'}\n"
            f"Buscar operaciones: Compras: {'Sí' if self.buscar['compras'] else 'No'}, Ventas: {'Sí' if self.buscar['ventas'] else 'No'}\n"
            f"Precios: Compra Inicial: {self.precios['compra_inicial']}, Compra Final: {self.precios['compra_final']}, "
            f"Venta Inicial: {self.precios['venta_inicial']}, Venta Final: {self.precios['venta_final']}\n"
            f"Stoploss y Takeprofit: SL Compra: {self.tpysl['stoploss_compra']}, TP Compra: {self.tpysl['takeprofit_compra']}, "
            f"SL Venta: {self.tpysl['stoploss_venta']}, TP Venta: {self.tpysl['takeprofit_venta']}\n"
            f"Operación finalizada: Compra: {'Sí' if self.operacion_finalizada['compra'] else 'No'}, Venta: {'Sí' if self.operacion_finalizada['venta'] else 'No'}\n"
            f"Pips: {self.pips}, Máx. Pips: {self.max_pips}\n"
            f"Horas operación: Inicio Compra: {self.horas_operacion['inicio_compra']}, Fin Compra: {self.horas_operacion['fin_compra']}, "
            f"Inicio Venta: {self.horas_operacion['inicio_venta']}, Fin Venta: {self.horas_operacion['fin_venta']}\n"
            f"Horas clave:\n"
            f"  - Ruptura sesión: {self.horas['hora_ruptura_sesion']}\n"
            f"  - Primer Fibonacci compras: {self.horas['hora_primer_fibonacci_compras']}\n"
            f"  - Segundo Fibonacci compras: {self.horas['hora_segundo_fibonacci_compras']}\n"
            f"  - Primer Fibonacci ventas: {self.horas['hora_primer_fibonacci_ventas']}\n"
            f"  - Segundo Fibonacci ventas: {self.horas['hora_segundo_fibonacci_ventas']}\n"
            f"Max antes del Min: {'Sí' if self.max_antes_min else 'No'}\n"
            f"Min antes del Max: {'Sí' if self.min_antes_max else 'No'}\n"
            f"High Fibonacci Compras Anterior: {self.highfibonacci_compras_anterior}\n"
            f"Low Fibonacci Ventas Anterior: {self.lowfibonacci_ventas_anterior}\n"
            f"Parar búsqueda: High Fibo: {'Sí' if self.parar_busqueda_high_fibo else 'No'}, Low Fibo: {'Sí' if self.parar_busqueda_low_fibo else 'No'}\n"
            f"Pausa operaciones: Compra: {'Sí' if self.pausa['compra'] else 'No'}, Venta: {'Sí' if self.pausa['venta'] else 'No'}\n"
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
        if self.operacion_finalizada['compra']:
            if self.precios['compra_final'] is not None:

                price_low = self.precios['compra_inicial']
                price_high = self.tpysl['takeprofit_compra']

            if self.horas_operacion['inicio_compra'] is not None and self.horas_operacion['fin_compra'] is not None:
                start_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.horas_operacion['inicio_compra'].hour, self.horas_operacion['inicio_compra'].minute)
                end_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.horas_operacion['fin_compra'].hour, self.horas_operacion['fin_compra'].minute)

                # Encontrar los índices más cercanos con get_indexer
                start_idx = df.index.get_indexer([start_rect], method='nearest')[0]
                end_idx = df.index.get_indexer([end_rect], method='nearest')[0]

                # Dibujar el rectángulo
                rect = Rectangle((start_idx, price_low), end_idx - start_idx, price_high - price_low,
                                facecolor='cyan', alpha=0.1)
                ax[0].add_patch(rect)

        ### DIBUJAR SL compra
            if self.precios['compra_final'] is not None:
                price_low = self.tpysl['stoploss_compra']
                price_high = self.precios['compra_inicial']

            if self.horas_operacion['inicio_compra'] is not None and self.horas_operacion['fin_compra'] is not None:

                start_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.horas_operacion['inicio_compra'].hour, self.horas_operacion['inicio_compra'].minute)
                end_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.horas_operacion['fin_compra'].hour, self.horas_operacion['fin_compra'].minute)

                # Encontrar los índices más cercanos con get_indexer
                start_idx = df.index.get_indexer([start_rect], method='nearest')[0]
                end_idx = df.index.get_indexer([end_rect], method='nearest')[0]

                # Dibujar el rectángulo
                rect = Rectangle((start_idx, price_low), end_idx - start_idx, price_high - price_low,
                                facecolor='gray', alpha=0.2)
                ax[0].add_patch(rect)

        ### DIBUJAR TP venta
        if self.operacion_finalizada['venta']:
            if self.precios['venta_final'] is not None:

                price_low = self.tpysl['takeprofit_venta']
                price_high = self.precios['venta_inicial']

            if self.horas_operacion['inicio_venta'] is not None and self.horas_operacion['fin_venta'] is not None:
                start_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.horas_operacion['inicio_venta'].hour, self.horas_operacion['inicio_venta'].minute)
                end_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.horas_operacion['fin_venta'].hour, self.horas_operacion['fin_venta'].minute)

                # Encontrar los índices más cercanos con get_indexer
                start_idx = df.index.get_indexer([start_rect], method='nearest')[0]
                end_idx = df.index.get_indexer([end_rect], method='nearest')[0]

                # Dibujar el rectángulo
                rect = Rectangle((start_idx, price_low), end_idx - start_idx, price_high - price_low,
                                facecolor='cyan', alpha=0.1)
                ax[0].add_patch(rect)

        ### DIBUJAR SL venta
            if self.precios['venta_inicial'] is not None:
                price_low = self.precios['venta_inicial']
                price_high = self.tpysl['stoploss_venta']

            if self.horas_operacion['inicio_venta'] is not None and self.horas_operacion['fin_venta'] is not None:
                start_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.horas_operacion['inicio_venta'].hour, self.horas_operacion['inicio_venta'].minute)
                end_rect = pd.Timestamp(self.fecha[2], self.fecha[1], self.fecha[0], self.horas_operacion['fin_venta'].hour, self.horas_operacion['fin_venta'].minute)

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

        if self.fibonacci618['compras'] is not None:
            price_low = self.fibonacci618['compras']
            price_high = self.fibonacci618['compras']

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

        if self.fibonacci_puntos['low_compras'] is not None:
            price_low = self.fibonacci_puntos['low_compras']
            price_high = self.fibonacci_puntos['low_compras']

        if self.fibonacci_puntos['low_compras'] is not None:
            # Dibujar el rectángulo
            rect = Rectangle((start_idx, price_low), end_idx - start_idx, 0,
                            linewidth=1, edgecolor='black', alpha=1)
            ax[0].add_patch(rect)

        if self.fibonacci_puntos['high_compras'] is not None:
            # Dibujar el rectángulo
            rect = Rectangle((start_idx, self.fibonacci_puntos['high_compras']), end_idx - start_idx, 0,
                            linewidth=1, edgecolor='black', alpha=1)
            ax[0].add_patch(rect)

        ## DIBUJAR FIBONACCI ventas

        if self.fibonacci618['ventas'] is not None:
            price_low = self.fibonacci618['ventas']
            price_high = self.fibonacci618['ventas']

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

        if self.fibonacci_puntos['low_compras'] is not None:
            # Dibujar el rectángulo
            rect = Rectangle((start_idx, self.fibonacci_puntos['low_compras']), end_idx - start_idx, 0,
                            linewidth=1, edgecolor='black', alpha=1)
            ax[0].add_patch(rect)

        if self.fibonacci_puntos['low_ventas'] is not None:
            rect = Rectangle((start_idx, self.fibonacci_puntos['low_ventas']), end_idx - start_idx, 0,
                            linewidth=1, edgecolor='black', alpha=1)
            ax[0].add_patch(rect)

        if self.fibonacci_puntos['high_ventas'] is not None:
            # Dibujar el rectángulo
            rect = Rectangle((start_idx, self.fibonacci_puntos['high_ventas']), end_idx - start_idx, 0,
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
        if algo.operacion_finalizada['compra'] and algo.operacion_finalizada['venta']: break
    i += 1
# Cerrar la conexión con MetaTrader 5
mt5.shutdown()

print(algo)
algo.generar_grafico()