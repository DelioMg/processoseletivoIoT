# Contador de Produção Não-Intrusivo

## Identificação do Candidato

- **Nome completo:Délio de Macedo Gonçalves**
- **GitHub:https://github.com/DelioMg**

---

## Visão Geral da Solução

O projeto simula um contador de produção não-intrusivo para linhas de montagem manuais/semiautomáticas sem CLP. Um sensor óptico (LDR) monitora a passagem de peças sobre uma esteira: cada vez que uma peça bloqueia e depois libera o feixe de luz, o firmware soma uma unidade ao contador. O sistema também identifica automaticamente micro-paradas (linha travada por tempo excessivo) e permite que o operador zere os contadores do turno pressionando um botão físico.

O usuário interage com o sistema apenas observando o log via porta serial (UART) e acionando o botão de reset quando desejar encerrar/limpar o turno.

---

## Arquitetura do Sistema Embarcado

O firmware (`src/main.py`) é organizado como uma máquina de estados executada em um laço principal **não-bloqueante**, baseada em `time.ticks_ms()`/`time.ticks_diff()` para todas as temporizações.

Fluxo principal (`main()`):

```
Inicialização -> imprime mensagem de boot
loop infinito:
    processar_sensor()   -> lê o LDR, atualiza estado da linha e contagem
    processar_botao()    -> lê o botão com debounce e trata o reset
    sleep_ms(10)          -> pequena pausa, sem bloquear o loop
```

### Estados da linha (sensor)

- `LIVRE`: luminosidade ≥ 500 lux (nenhuma peça sobre o sensor)
- `BLOQUEADA`: luminosidade ≤ 100 lux (peça obstruindo o feixe)
- Entre 100 e 500 lux: zona de histerese — o firmware mantém o último estado estável, evitando contagens falsas por ruído/transição.

Transições relevantes:

- `LIVRE -> BLOQUEADA`: início de uma possível peça; registra o instante do bloqueio (para o cálculo de micro-parada).
- `BLOQUEADA -> LIVRE`: a peça terminou de passar; o contador é incrementado e a mensagem de detecção é impressa.
- Enquanto o estado permanecer `BLOQUEADA` por mais de 5 segundos contínuos, um alerta de micro-parada é emitido (uma única vez por ocorrência).

### Botão de reset

A leitura do botão passa por um debounce baseado em tempo (50 ms): só é considerada uma mudança de estado válida quando o novo valor permanece estável por esse intervalo. Ao detectar o acionamento estável (nível baixo, já que o pino usa pull-up interno), os contadores e cronômetros são zerados imediatamente.

---

## Componentes Utilizados na Simulação

- **Placa:** ESP32 DevKit C v4 (`board-esp32-devkit-c-v4`), executando MicroPython (`env: micropython-20231005-v1.21.0`).
- **Sensor óptico (LDR):** `ldr1` — fotorresistor conectado ao pino analógico **GPIO34** (`esp:34`), usado para detectar a passagem de peças e micro-paradas. Alimentado por `esp:3V3` / `esp:GND.1`.
- **Botão de reset:** `btn1` — botão digital conectado ao **GPIO4** (`esp:4`, pull-up interno), com o outro terminal em `esp:GND.3`, usado para zerar o turno.
- **UART/Serial:** interface UART0 nativa da placa (`esp:TX0`/`esp:RX0`), conectada ao monitor serial do Wokwi (`$serialMonitor`, `display: always`). Utilizada para logs de inicialização, contagem de peças, alertas de micro-parada e confirmação de reset.

---

## Decisões Técnicas Relevantes

- **Arquitetura não-bloqueante:** nenhuma função de espera longa (`sleep` bloqueante) é usada no laço principal; todas as temporizações (micro-parada e debounce) usam marcações de tempo (`ticks_ms`), garantindo que o firmware nunca perca a janela em que o simulador altera a luminosidade.
- **Conversão ADC → lux:** a leitura analógica é convertida para um valor de lux usando a mesma relação física do módulo fotorresistor do Wokwi (resistor fixo em série com o LDR, parâmetros `rl10` e `gamma`), o que torna a lógica de decisão fiel aos valores de lux descritos na especificação (500 lux / 100 lux), independentemente de pequenas variações no valor bruto do ADC.
- **Histerese entre os limiares:** evita alternância de estado (e falsas contagens) quando a luminosidade fica temporariamente entre 100 e 500 lux.
- **Uma única emissão de alerta por parada:** o alerta de micro-parada é disparado uma única vez por ocorrência (controlado por uma flag), evitando poluir o log enquanto a peça permanece parada.
- **Constantes nomeadas:** todos os limiares (lux, tempo de micro-parada, debounce) são constantes no topo do arquivo, facilitando ajuste fino sem alterar a lógica.

---

## Resultados Obtidos

- Mensagem de inicialização exibida corretamente ao ligar o sistema.
- Contagem de peças incrementada corretamente na transição bloqueado → livre, com a mensagem `Peca detectada! Total: X`.
- Alerta de micro-parada disparado corretamente após 5 segundos contínuos de bloqueio do sensor.
- Reset de turno funcional, com debounce do botão e mensagem de confirmação.
- Cenários de teste automatizados (`test_1.yaml`, `test_2.yaml`, `test_3.yaml`) validados via Wokwi CI.

---

## Comentários Adicionais

- **Dificuldades:** a principal atenção foi garantir o casamento exato das strings de log exigido pelo avaliador e assegurar que nenhuma chamada bloqueante pudesse atrasar a leitura do sensor durante a janela de simulação.
- **Melhorias futuras:** com mais tempo, seria interessante calcular e reportar também o tempo de ciclo médio entre peças e persistir os contadores (ex.: em arquivo) para sobreviver a reinicializações do turno.
- **Aprendizados:** aprofundamento em máquinas de estado não-bloqueantes em MicroPython e na modelagem elétrica de sensores simulados no Wokwi (conversão ADC → grandeza física).

