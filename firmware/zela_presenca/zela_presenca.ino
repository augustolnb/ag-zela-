// Firmware do ESP32 para o Zela+: le 4 sensores PIR (infravermelho
// passivo) cobrindo 2 comodos (2 sensores por comodo, por redundancia)
// e notifica o backend (POST /ingest/esp32) sempre que a presenca
// combinada muda de estado (presente <-> ausente).
//
// Sensores (3 pinos cada: VCC-OUT-GND, saida digital ja em 3,3V,
// nao precisa de divisor de tensao):
//   Comodo A: 1x SR602 (OUT -> GPIO 13) + 1x HC-SR505 (OUT -> GPIO 14)
//   Comodo B: 1x SR602 (OUT -> GPIO 26) + 1x HC-SR505 (OUT -> GPIO 27)
// SR602 alimentado em 3,3V (ESP32), HC-SR505 alimentado em 5V/VIN
// (datasheet pede minimo 4,5V) — OUT de ambos permanece seguro pro
// GPIO independente da alimentacao. Diagrama completo em
// docs/hardware/automacao_esp32.pdf.
//
// Presenca = OR entre os 4 sensores (qualquer um acionado conta como
// presenca) — o payload enviado ao backend continua sendo um unico
// booleano, sem distincao de comodo (ver zela/models/monitoramento.py).

#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>

// Credenciais e endereco do backend: ver config.h.example. Copie para
// "config.h" (nao versionado) e preencha antes de compilar/gravar.
#include "config.h"

const int PINO_SR602_COMODO_A = 13;
const int PINO_SR505_COMODO_A = 14;
const int PINO_SR602_COMODO_B = 26;
const int PINO_SR505_COMODO_B = 27;
const int PINOS_SENSORES[] = {PINO_SR602_COMODO_A, PINO_SR505_COMODO_A, PINO_SR602_COMODO_B, PINO_SR505_COMODO_B};
const int QUANTIDADE_SENSORES = 4;

const unsigned long INTERVALO_LEITURA_MS = 2000;
// PIR precisa de um tempo de estabilizacao apos ligar (o SR602 e o
// HC-SR505 podem oscilar/disparar falso positivo nesse periodo) — leituras
// sao ignoradas ate esse tempo passar desde o boot.
const unsigned long TEMPO_AQUECIMENTO_MS = 60000;

bool presencaAnterior = false;
unsigned long inicioMs = 0;
unsigned long ultimaTentativaReconexaoMs = 0;
const unsigned long INTERVALO_RECONEXAO_MS = 15000UL;  // no minimo 15s entre tentativas

bool lerPresenca() {
  for (int i = 0; i < QUANTIDADE_SENSORES; i++) {
    if (digitalRead(PINOS_SENSORES[i]) == HIGH) {
      return true;
    }
  }
  return false;
}

String obterTimestampIso() {
  time_t agora = time(nullptr);
  struct tm infoTempo;
  localtime_r(&agora, &infoTempo);
  char buffer[25];
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%S", &infoTempo);
  return String(buffer);
}

bool enviarLeitura(bool presenca) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi desconectado, pulando envio.");
    return false;
  }
  HTTPClient http;
  http.begin(URL_INGESTAO);
  http.addHeader("Content-Type", "application/json");
  if (strlen(TOKEN_INGESTAO) > 0) {
    http.addHeader("X-Api-Key", TOKEN_INGESTAO);
  }

  String corpo = String("{\"valor\": ") + (presenca ? "1" : "0") +
                 ", \"timestamp\": \"" + obterTimestampIso() + "\"}";

  int codigoResposta = http.POST(corpo);
  Serial.printf("POST /ingest/esp32 -> %d\n", codigoResposta);
  http.end();
  return codigoResposta > 0 && codigoResposta < 300;
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < QUANTIDADE_SENSORES; i++) {
    pinMode(PINOS_SENSORES[i], INPUT);
  }
  inicioMs = millis();

  WiFi.begin(WIFI_SSID, WIFI_SENHA);
  Serial.print("Conectando ao WiFi");
  unsigned long limiteEsperaWifiMs = millis() + 30000UL;
  while (WiFi.status() != WL_CONNECTED && millis() < limiteEsperaWifiMs) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nConectado.");
  } else {
    Serial.println("\nWiFi nao conectou no boot; tentando em segundo plano.");
  }

  // O ESP32 nao tem RTC com bateria propria — sincroniza a hora via NTP
  // antes de comecar a enviar leituras, para os timestamps serem reais.
  configTime(-3 * 3600, 0, "pool.ntp.org", "time.nist.gov");  // UTC-3, sem horario de verao desde 2019
  Serial.print("Sincronizando hora via NTP");
  unsigned long limiteEsperaMs = millis() + 30000UL;  // no maximo 30s de espera
  time_t agora = time(nullptr);
  while (agora < 100000 && millis() < limiteEsperaMs) {
    delay(500);
    Serial.print(".");
    agora = time(nullptr);
  }
  if (agora < 100000) {
    Serial.println("\nNTP falhou ao sincronizar; prosseguindo mesmo assim.");
  } else {
    Serial.println("\nHora sincronizada.");
  }

  Serial.println("Aquecendo sensores PIR (60s) antes da primeira leitura valida...");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED && millis() - ultimaTentativaReconexaoMs >= INTERVALO_RECONEXAO_MS) {
    Serial.println("WiFi desconectado, tentando reconectar...");
    WiFi.reconnect();
    ultimaTentativaReconexaoMs = millis();
  }

  if (millis() - inicioMs < TEMPO_AQUECIMENTO_MS) {
    delay(INTERVALO_LEITURA_MS);
    return;
  }

  bool presencaAtual = lerPresenca();

  if (presencaAtual != presencaAnterior) {
    if (enviarLeitura(presencaAtual)) {
      presencaAnterior = presencaAtual;
    }
  }

  delay(INTERVALO_LEITURA_MS);
}
