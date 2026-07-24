"""
Contador de Producao Nao-Intrusivo
-----------------------------------
Firmware MicroPython para ESP32 que monitora a passagem de pecas em uma
esteira usando um sensor optico (LDR), calcula o tempo de ciclo, detecta
micro-paradas e permite o reset manual do turno via botao fisico.

Arquitetura: maquina de estados simples rodando em um loop principal
NAO-BLOQUEANTE, baseada em time.ticks_ms() para todas as temporizacoes.
"""

from machine import Pin, ADC
import time

# ---------------------------------------------------------------------------
# Configuracao de hardware
# ---------------------------------------------------------------------------

LDR_PIN = 34            # Pino analogico (AO) do sensor fotorresistor (ldr1)
BUTTON_PIN = 4           # Pino digital do botao de reset (btn1)

adc = ADC(Pin(LDR_PIN))
adc.atten(ADC.ATTN_11DB)    # Permite leitura de 0 a ~3.3V
try:
    adc.width(ADC.WIDTH_12BIT)  # 0-4095 (alguns ports ja vem fixos em 12 bits)
except AttributeError:
    pass

# Botao com pull-up interno: solto = 1 (HIGH), pressionado = 0 (LOW)
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

# ---------------------------------------------------------------------------
# Constantes do sistema
# ---------------------------------------------------------------------------

# Caracteristicas eletricas do modulo fotorresistor (compativeis com o
# wokwi-photoresistor-sensor: rl10=50 (kOhm), gamma=0.7, resistor fixo 10k)
VCC = 3.3
ADC_MAX = 4095
R_FIXED = 10000.0   # ohms
RL10 = 50.0         # kOhm
GAMMA = 0.7

LUX_LINHA_LIVRE = 500     # Acima disso: linha livre (sem peca no sensor)
LUX_LINHA_BLOQUEADA = 100  # Abaixo disso: peca bloqueando o feixe de luz

MICROPARADA_LIMIAR_MS = 5000  # Tempo continuo bloqueado para considerar parada
DEBOUNCE_MS = 50               # Tempo de estabilizacao do botao

LOOP_DELAY_MS = 10  # Pequena pausa para nao saturar a CPU (nao-bloqueante)

# ---------------------------------------------------------------------------
# Estado global do sistema
# ---------------------------------------------------------------------------

total_pecas = 0
estado_linha = "LIVRE"          # "LIVRE" ou "BLOQUEADA"
instante_bloqueio = None        # ticks_ms() de quando a linha bloqueou
microparada_alertada = False    # Evita repetir o alerta durante a mesma parada

botao_leitura_anterior = button.value()
botao_estado_estavel = botao_leitura_anterior
botao_ultima_mudanca = time.ticks_ms()


# ---------------------------------------------------------------------------
# Funcoes auxiliares
# ---------------------------------------------------------------------------

def ler_lux():
    """Le o pino analogico do LDR e converte a leitura em um valor de lux,
    usando a mesma formula fisica do modulo fotorresistor do Wokwi."""
    valor_bruto = adc.read()
    tensao = (valor_bruto / ADC_MAX) * VCC

    # Protege contra divisao por zero nos extremos da faixa
    if tensao <= 0.001:
        return 100000.0
    if tensao >= (VCC - 0.001):
        return 0.0

    resistencia = R_FIXED * tensao / (VCC - tensao)
    lux = (RL10 * 1000.0 * (10 ** GAMMA) / resistencia) ** (1.0 / GAMMA)
    return lux


def processar_sensor():
    """Maquina de estados da esteira: deteccao de peca e de micro-parada."""
    global estado_linha, total_pecas, instante_bloqueio, microparada_alertada

    lux = ler_lux()
    agora = time.ticks_ms()

    if lux >= LUX_LINHA_LIVRE:
        leitura_atual = "LIVRE"
    elif lux <= LUX_LINHA_BLOQUEADA:
        leitura_atual = "BLOQUEADA"
    else:
        # Zona intermediaria (histerese): mantem o estado anterior para
        # evitar contagens falsas por ruido/transicao de luminosidade.
        leitura_atual = estado_linha

    # Borda de descida: linha livre -> peca comecando a bloquear o sensor
    if estado_linha == "LIVRE" and leitura_atual == "BLOQUEADA":
        instante_bloqueio = agora
        microparada_alertada = False

    # Borda de subida: peca terminou de passar -> incrementa contagem
    elif estado_linha == "BLOQUEADA" and leitura_atual == "LIVRE":
        total_pecas += 1
        print("Peca detectada! Total: {}".format(total_pecas))
        instante_bloqueio = None
        microparada_alertada = False

    estado_linha = leitura_atual

    # Verifica micro-parada de forma nao-bloqueante
    if estado_linha == "BLOQUEADA" and instante_bloqueio is not None:
        decorrido = time.ticks_diff(agora, instante_bloqueio)
        if decorrido > MICROPARADA_LIMIAR_MS and not microparada_alertada:
            print("Alerta: Micro-parada detectada!")
            microparada_alertada = True


def processar_botao():
    """Le o botao de reset com debounce e zera os contadores do turno."""
    global botao_leitura_anterior, botao_estado_estavel, botao_ultima_mudanca
    global total_pecas, estado_linha, instante_bloqueio, microparada_alertada

    agora = time.ticks_ms()
    leitura = button.value()

    if leitura != botao_leitura_anterior:
        botao_ultima_mudanca = agora
        botao_leitura_anterior = leitura

    if time.ticks_diff(agora, botao_ultima_mudanca) > DEBOUNCE_MS:
        if leitura != botao_estado_estavel:
            botao_estado_estavel = leitura

            # Pull-up: 0 (LOW) = botao pressionado
            if botao_estado_estavel == 0:
                total_pecas = 0
                estado_linha = "LIVRE"
                instante_bloqueio = None
                microparada_alertada = False
                print("Turno resetado com sucesso. Contadores zerados.")


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main():
    print("Contador de Producao Inicializado")

    while True:
        processar_sensor()
        processar_botao()
        time.sleep_ms(LOOP_DELAY_MS)


if __name__ == "__main__":
    main()
