// Firmware do ESP32 para o Zela+: le um sensor ultrassonico HC-SR04 e
// notifica o backend (POST /ingest/esp32) sempre que a presenca no
// comodo muda de estado (presente <-> ausente).
//
// Ligacoes do HC-SR04:
//   VCC   -> 5V (ou 3.3V, conforme o modulo)
//   GND   -> GND
//   TRIG  -> GPIO 5
//   ECHO  -> GPIO 18 (usar um divisor de tensao 5V->3.3V se o modulo for 5V)

#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>

const char *WIFI_SSID = "SUA_REDE_WIFI";
const char *WIFI_SENHA = "SUA_SENHA_WIFI";
const char *URL_INGESTAO = "http://SEU_SERVIDOR:8000/ingest/esp32";

const int PINO_TRIGGER = 5;
const int PINO_ECHO = 18;
const float DISTANCIA_LIMIAR_CM = 150.0;
const unsigned long INTERVALO_LEITURA_MS = 2000;

bool presencaAnterior = false;
unsigned long ultimaTentativaReconexaoMs = 0;
const unsigned long INTERVALO_RECONEXAO_MS = 15000UL;  // no minimo 15s entre tentativas

float lerDistanciaCm() {
  digitalWrite(PINO_TRIGGER, LOW);
  delayMicroseconds(2);
  digitalWrite(PINO_TRIGGER, HIGH);
  delayMicroseconds(10);
  digitalWrite(PINO_TRIGGER, LOW);

  long duracaoMicros = pulseIn(PINO_ECHO, HIGH, 30000);
  if (duracaoMicros == 0) {
    return -1.0;  // sem eco dentro do timeout (nada refletindo o sinal)
  }
  return duracaoMicros * 0.0343 / 2.0;
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

  String corpo = String("{\"valor\": ") + (presenca ? "1" : "0") +
                 ", \"timestamp\": \"" + obterTimestampIso() + "\"}";

  int codigoResposta = http.POST(corpo);
  Serial.printf("POST /ingest/esp32 -> %d\n", codigoResposta);
  http.end();
  return codigoResposta > 0 && codigoResposta < 300;
}

void setup() {
  Serial.begin(115200);
  pinMode(PINO_TRIGGER, OUTPUT);
  pinMode(PINO_ECHO, INPUT);

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
}

void loop() {
  if (WiFi.status() != WL_CONNECTED && millis() - ultimaTentativaReconexaoMs >= INTERVALO_RECONEXAO_MS) {
    Serial.println("WiFi desconectado, tentando reconectar...");
    WiFi.reconnect();
    ultimaTentativaReconexaoMs = millis();
  }

  float distanciaCm = lerDistanciaCm();
  bool presencaAtual = (distanciaCm > 0 && distanciaCm <= DISTANCIA_LIMIAR_CM);

  if (presencaAtual != presencaAnterior) {
    if (enviarLeitura(presencaAtual)) {
      presencaAnterior = presencaAtual;
    }
  }

  delay(INTERVALO_LEITURA_MS);
}
