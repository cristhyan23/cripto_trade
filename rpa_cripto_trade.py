import os
import time
import datetime
import pandas as pd
from binance.client import Client
from binance.enums import *
from dotenv import load_dotenv


# Specify the path to your .env file
load_dotenv()

class Rpa_Cripto_Trade:
    """ Classe responsavel por conectar com a API acessar dados da conta criar ordem de compra e venda"""
    def __init__(self):    
        self.API_KEY = os.getenv('BINANCE_API_KEY')
        self.SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
        # connect to the binance client
        self.binance_client = Client(self.API_KEY,self.SECRET_KEY)
        self.binance_client.SYNC_TIME = True
        # Sincronizar o tempo com o servidor da Binance
        server_time = self.binance_client.get_server_time()
        local_time = int(time.time() * 1000)
        time_offset = server_time['serverTime'] - local_time
        self.binance_client.TIME_OFFSET = time_offset
        #account binance
        self.my_account = self.binance_client.get_account()

# get all balances greater than 0
    @property
    def get_ativos(self):
        """retona dados dos ativos que temos em carteira"""
        ativos = []
        for ativo in self.my_account["balances"]:
            if float(ativo["free"])>0:
                ativos.append(ativo)
        return ativos
    
# creating a buying order
    def create_order(self,trade_coin,quant,side):
        """ criar a ordem de compra ou venda de acordo com o ativo e quantidade solicidada"""
        #creating a buying order
        buy_order = self.binance_client.create_order(
            symbol = trade_coin,
            side =side, 
            type = ORDER_TYPE_MARKET, 
            quantity = quant
        )
        return buy_order

    def log_message(self,message):
        """ Salva o log da operação """
        with open("log.txt", "a") as log_file:
            log_file.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

    def get_conversion_rates(self):
        """Retorna as taxas de conversão para BRL dos ativos, tratando USD como USDT."""
            # Lista dos símbolos para os ativos, incluindo "USDT" para "USD"
        symbols = ["USDTBRL", "BTCBRL", "ETHBRL", "SOLBRL"]
        rates = {}
            
            # Loop para coletar as taxas de conversão
        for symbol in symbols:
                # Se o ativo for "USD", vamos tratá-lo como "USDT"
                asset = symbol[:3]
                if asset == "USD":
                    asset = "USDT"
                
                # Obtém a taxa de conversão e armazena no dicionário
                rate = float(self.binance_client.get_symbol_ticker(symbol=symbol)["price"])
                rates[asset] = rate
                
        return rates
    
    def calcular_saldo_por_ativo(self, carteira, taxas):
            """
            Calcula os saldos de cada ativo em BRL e o saldo total.
            
            Args:
            - carteira: Lista de ativos com suas quantidades livres e bloqueadas.
            - taxas: Dicionário com as taxas de conversão (ex: {"USD": 5.0, "BTC": 120000.0}).

            Returns:
            - saldo_por_ativo: Dicionário com saldos por ativo.
            - saldo_total: Saldo total em BRL.
            """
            saldo_por_ativo = {ativo: 0 for ativo in taxas.keys()}
            saldo_total = 0

            for ativo in carteira:
                asset = ativo["asset"]
                free = float(ativo["free"])
                locked = float(ativo["locked"])
                total = free + locked

                if total > 0:
                    if asset in taxas:
                        saldo_em_brl = total * taxas[asset]
                        saldo_por_ativo[asset] = saldo_em_brl
                        saldo_total += saldo_em_brl
                    elif asset == "BRL":
                        saldo_por_ativo["BRL"] = total
                        saldo_total += total
                    else:
                        print(f"Ativo não suportado: {asset}")

            return saldo_por_ativo, saldo_total

    def calcular_saldo_total_em_brl(self):
        """Calcula o saldo total em BRL da carteira."""
        taxas = self.get_conversion_rates()
        carteira = self.get_ativos  # Certifique-se de que isso retorna a lista de ativos corretamente
        _, saldo_total = self.calcular_saldo_por_ativo(carteira, taxas)
        return saldo_total
    
    def save_account_historical_value(self):
        """Salva o valor histórico da conta em um arquivo Excel."""
        # Data e hora atual
        data_hora_atual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Obtém as taxas de conversão e os dados da carteira
        taxas = self.get_conversion_rates()
        carteira = self.get_ativos  # Certifique-se de que isso retorna a lista de ativos corretamente

        # Calcula os saldos por ativo e o total
        saldo_por_ativo, saldo_total = self.calcular_saldo_por_ativo(carteira, taxas)

        # Cria os dados da nova linha
        nova_linha = {
            "Data e Hora": data_hora_atual,
            "USDT/BRL": round(saldo_por_ativo.get("USDT", 0), 2),
            "BTC/BRL": round(saldo_por_ativo.get("BTC", 0), 2),
            "ETH/BRL": round(saldo_por_ativo.get("ETH", 0), 2),
            "SOL/BRL": round(saldo_por_ativo.get("SOL", 0), 2),
            "TOTAL": round(saldo_total, 2),
        }

        arquivo_excel = "./saldo_historico.xlsx"

        # Verifica se o arquivo já existe
        if os.path.exists(arquivo_excel):
            df_existente = pd.read_excel(arquivo_excel)
            df_atualizado = pd.concat([df_existente, pd.DataFrame([nova_linha])], ignore_index=True)
        else:
            df_atualizado = pd.DataFrame([nova_linha])

        # Salva o DataFrame atualizado no Excel
        df_atualizado.to_excel(arquivo_excel, index=False)

if __name__ == '__main__':
    rpa = Rpa_Cripto_Trade()
    