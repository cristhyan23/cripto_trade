import numpy as np
import pandas as pd
import time
from rpa_cripto_trade import *
from datetime import datetime, timedelta

class Operador(Rpa_Cripto_Trade):
    """ Classe para operações gera analise historica e define estrategia para atuar com a compra ou a venda """
    def __init__(self,codigo_operado,ativo,quant,period):
        super().__init__()
        self.codigo_operado = codigo_operado
        self.ativo_operado = ativo
        self.period_candle = self.binance_client.KLINE_INTERVAL_15MINUTE if period =="15min" else self.binance_client.KLINE_INTERVAL_1HOUR
        self.trade_buy_quantity = quant
        # Obtendo a quantidade mínima e as casas decimais do ativo
        self.asset_info = self.binance_client.get_symbol_info(self.codigo_operado)
        self.min_qty = float(self.asset_info['filters'][1]['minQty'])  # Mínima quantidade permitida
        self.precision = int(self.asset_info['filters'][1]['stepSize'].find('1') - 1)  # Casas decimais permitidas

    def get_dados_trade(self):
        """ Retorna os dados de fechamento dos ultimos 1000 candles do ativo """
        candles = self.binance_client.get_klines(symbol = self.codigo_operado,interval = self.period_candle, limit = 1000)
        prices = pd.DataFrame(candles)
        prices.columns = ['timestamp', 'open', 'high', 'low', 'close','volume','close_time','coin_traded',
                          'trade_numbers','active_buy_volume_based','quoting_active_volume','-']
        prices = prices[['close','close_time']]
        prices['close'] = prices['close'].astype(float)
        # configura para data com base no horário local
        prices['close_time'] = pd.to_datetime(prices['close_time'],unit='ms').dt.tz_localize("UTC")
        prices['close_time'] = prices['close_time'].dt.tz_convert("America/Sao_Paulo")
       
        return prices
    @property
    def get_quantity_ative(self):
        """ Retorna a quantidade que tenho em posição na minha carteira """
        ativos = self.get_ativos
        for ativo in ativos:
            if ativo['asset'] == self.ativo_operado:
                return float(ativo['free']) #valor em carteira

    def get_symbol_info(self, symbol="SOLBRL"):
        """ Retorna as informações do par de moedas (symbol_info) """
    # Obtendo as informações do par de moedas
        symbol_info = self.binance_client.get_symbol_info(symbol)
        return symbol_info

    def adjust_quantity(self, quantity):
        """ funções para ajustar a quantidade disponivel para venda de acordo com a quantidade de casas decimais e minimo aceitavel pela binance"""
        if quantity == 0:
            return quantity
        else:
                # Obter informações sobre o símbolo
            symbol_info = self.binance_client.get_symbol_info(self.codigo_operado)
        # Filtra para encontrar o filtro LOT_SIZE
            lot_size_filter = next(filter(lambda x: x['filterType'] == 'LOT_SIZE', symbol_info['filters']))
        # Passo do lote (stepSize) - o incremento permitido
            step_size = float(lot_size_filter['stepSize'])
            self.log_message(f"Step size: {step_size}") 
        # Ajustar a quantidade para o múltiplo mais próximo do stepSize
            try:
                adjusted_quantity = quantity - (quantity % step_size)
            except TypeError:
                adjusted_quantity = 0
        # Limitar o número de casas decimais baseado no stepSize
            step_decimals = len(str(step_size).split('.')[-1])
            adjusted_quantity = round(adjusted_quantity, step_decimals)
            return adjusted_quantity

    def otimizar_medias(self, historical_data):
        """ função que analisa a melhor opção para janelas para media rapida e lenta"""
        melhores_parametros = None
        melhor_performance = -np.inf

        # Testar diferentes combinações de janelas
        for janela_rapida in range(5, 50, 5):  # Ex: 5, 10, 15, ..., 45
            for janela_lenta in range(50, 200, 25):  # Ex: 50, 75, ..., 175
                if janela_rapida >= janela_lenta:
                    continue  # A média rápida deve ter um período menor que a lenta
                
                # Calcular médias móveis
                historical_data['fast_mean'] = historical_data['close'].rolling(window=janela_rapida).mean()
                historical_data['slow_mean'] = historical_data['close'].rolling(window=janela_lenta).mean()

                # Sinal de Compra/Venda (exemplo: cruzamento de médias)
                historical_data['signal'] = np.where(
                    historical_data['fast_mean'] > historical_data['slow_mean'], 1, -1
                )
                
                # Simular estratégia com sinais
                historical_data['strategy_return'] = (
                    historical_data['signal'].shift(1) * historical_data['close'].pct_change()
                )
                retorno_cumulativo = historical_data['strategy_return'].cumsum().iloc[-1]
                
                # Comparar performance
                if retorno_cumulativo > melhor_performance:
                    melhor_performance = retorno_cumulativo
                    melhores_parametros = (janela_rapida, janela_lenta)
        
        return melhores_parametros, melhor_performance
    def trade_estrategies(self):
        """função responsavel por copilar as quantidades e analisar medias rapidas e lentas para definir se deve comprar ou vender e com isso acionar função de compra ou venda"""
        actual_quantity = self.get_quantity_ative
        adjust_quantity = self.adjust_quantity(actual_quantity)
        self.log_message(f"Ativo: {rpa.ativo_operado} | Quantidade Atual: {adjust_quantity} ")

        if adjust_quantity < self.min_qty:
            posicao = False
            self.log_message(f"Quantidade abaixo do mínimo {self.min_qty}.")
        else:
            posicao = True

        historical_data = self.get_dados_trade()
        # Substitua os valores estáticos pelas melhores janelas encontradas
        fast_window, slow_window = self.otimizar_medias(historical_data)[0]
        self.log_message(f"Janela Rápida: {fast_window} | Janela Lenta: {slow_window} ")
        # implementar estratégias de trade aqui
        historical_data['fast_mean'] = historical_data['close'].rolling(window=fast_window).mean()
        historical_data['slow_mean'] = historical_data['close'].rolling(window=slow_window).mean()

        ultima_media_rapida = historical_data['fast_mean'].iloc[-1]
        ultima_media_lenta = historical_data['slow_mean'].iloc[-1]
        
        self.log_message(f"Última Média Rápida: {ultima_media_rapida} | Última Média Lenta: {ultima_media_lenta}")

        #ANALISE PARA COMPRA
        if ultima_media_rapida > ultima_media_lenta:
            self.log_message("CONSELHA COMPRA")
            if posicao == False:
               try:
                self.create_order(self.codigo_operado,self.trade_buy_quantity,SIDE_BUY)
                self.log_message("ATIVO COMPRADO")
                posicao = True
               except Exception as e:
                    self.log_message(f"Erro ao comprar: {str(e)}")

        #ANALISE PARA VENDA

        elif ultima_media_rapida < ultima_media_lenta:
            self.log_message("CONSELHA VENDA")
            if posicao == True:
                try:
                    if adjust_quantity >= self.min_qty:
                        self.create_order(self.codigo_operado,adjust_quantity,SIDE_SELL)
                        self.log_message(f"ATIVO VENDIDO")
                        posicao = False
                    else:
                        self.log_message(f"Quantidade muito baixa para venda: {adjust_quantity}")
                except Exception as e:
                    self.log_message(f"Erro ao vender: {str(e)}")
                 
        return posicao


if __name__ == '__main__':
    
    moedas = [["SOLBRL","SOL",0.015,"15min"],["ETHBRL","ETH",0.0015,"1h"],["USDTBRL","USDT",5.5,"1h"],["BTCBRL","BTC",0.00015,"15min"]]
    
    while True:
        proxima_execucao = datetime.now()
        for moeda in moedas:
            rpa = Operador(moeda[0],moeda[1],moeda[2],moeda[3])
            posicao = rpa.trade_estrategies()
        proxima_execucao = datetime.now() + timedelta(minutes=15)
        rpa.log_message(f"Saldo Atual em BRL da Carteira: R$ {rpa.calcular_saldo_total_em_brl():.2f}")
        rpa.save_account_historical_value()
        rpa.log_message(f"Proxima análise de mercado: {proxima_execucao}")
        time.sleep(900) # intervalo de 15 min entre cada atualização da estratégia
        