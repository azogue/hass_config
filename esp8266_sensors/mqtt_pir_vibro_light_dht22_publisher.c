/*
# *Detector de movimiento, vibración, luz, temperatura y humedad relativa*

*Detector inalámbrico de movimiento, vibración, luz, temperatura y humedad relativa* sobre plataforma ESP8266,
que comunica los valores detectados a un servidor MQTT (like `mosquitto`). Útil para colocarlo en recintos alejados
pero con acceso a wifi en integraciones de domótica.

De funcionamiento muy sencillo, se conecta a la wifi local, y de ahí al servidor MQTT, donde publica los valores
de temperatura, humedad y porcentaje de iluminación cada X segundos.
(`MQTT_POSTINTERVAL_LIGHT_SEC` & `MQTT_POSTINTERVAL_DHT22_SEC`|`MQTT_POSTINTERVAL_BME280_SEC`).
Los sensores binarios (movimiento, vibración e iluminación) se tratan mediante interrupciones (vs polling)
y publican estados de 'on'/'off' en cuanto se produce un evento de activación.
También escucha para recibir órdenes en JSON.

Componentes:
  - ESP8266 mcu 1.0 dev kit / ESP32 Dev Kit
  - DHT22 / DHT11 sensor
  - PIR sensor
  - Vibration sensor
  - Light sensor (with AO + DO)
  - RGBLED + 3 resistors

Edita, al menos, estos valores con tu configuración particular y flashea el programa con el Arduino IDE:
```
//WiFi Settings
#define WiFiSSID                            [REDACTED_WIFI_SSID]
#define WiFiPSK                             [REDACTED_WIFI_PASSWORD]

//MQTT Server Settings
#define MQTT_SERVER                         [REDACTED_MQTT_SERVER_IP]
#define MQTT_PORT                           [REDACTED_MQTT_SERVER_PORT]
#define MQTT_USER                           [REDACTED_MQTT_USER]
#define MQTT_PASSWORD                       [REDACTED_MQTT_PASSWD]
```

Si quieres editar los MQTT `topic`'s de cada sensor, cambia también estos:
```
#define mqtt_temp_topic                     "sensor/temp_"
#define mqtt_humid_topic                    "sensor/hum_"
#define mqtt_pressure_topic                 "sensor/pres_"
#define mqtt_movement_topic                 "sensor/pir_"
#define mqtt_vibro_topic                    "sensor/extra_"
#define mqtt_light_topic                    "sensor/light_"
#define mqtt_light_analog_topic             "sensor/light_analog_"

#define mqtt_control_topic                  "control/module_"

```

Al nombre del `topic` se le añade la MAC de la Wifi del ESP8266 (ej: `sensor/light_analog_abcdef012345`), de forma
que los identificadores son únicos para cada chip, por lo que, si utilizas varios de estos detectores, no hay
necesidad de cambiar el programa para cada uno.

### Changelog ESP8266 MQTT Publisher

- v1.0: PIR+Vibration+Light(AO+DO)+DHT22 sensors publishing values to a local mosquitto server.
- v1.1: Fixed some errors, Better error handling with DHT22, different publish frecuency for light & DHT22,
        negate digital_light sensor, and some refactoring.
- v1.2: Added ESP32 support with a compilation flag, Compiles OK but it's NOT WORKING:
```
  Guru Meditation Error of type LoadProhibited occurred on core  1. Exception was unhandled.
  Register dump:
  PC      : 0x400d1de8  PS      : 0x00060c30  A0      : 0x800d214a  A1      : 0x3ffc7440
  A2      : 0x3ffc1f98  A3      : 0x000000c8  A4      : 0x3f40156f  A5      : 0x3ffc7560
  A6      : 0x3ffc7540  A7      : 0x00000008  A8      : 0x800d83c5  A9      : 0x3ffc7390
  A10     : 0x00000000  A11     : 0x3ffc7486  A12     : 0x00000000  A13     : 0x3f40156f
  A14     : 0x00000000  A15     : 0x00000000  SAR     : 0x0000001f  EXCCAUSE: 0x0000001c
  EXCVADDR: 0x00000000  LBEG    : 0x400014fd  LEND    : 0x4000150d  LCOUNT  : 0xfffffffc

  Backtrace: 0x400d1de8:0x3ffc7440 0x400d214a:0x3ffc7460 0x400d21dd:0x3ffc7580 0x400d1745:0x3ffc75a0 0x400d11a2:0x3ffc75c0 0x400d1227:0x3ffc75e0 0x400de7d2:0x3ffc7610

  CPU halted.
```
- v1.3: MQTT subscribe at `control/module_MAC`/ `control/out_module_MAC`, JSON payload,
        set RGB color with `{"color": [100, 0, 255]}`; Auto reboot if no wifi or many dht errors;
        mqtt error descriptions; some fixes. PINOUT with esp8266_breadboard & dht11.
- v1.4: BME280 temperature + humidity + pressure sensor (much better than the DHT variants!);
        switch ON/OFF Leds & binary sensors with mqtt (MQTT switches for HA)

### Librerías:

- ESP8266WiFi v1.0 || WiFiEsp v2.1.2
- PubSubClient v2.6
- ArduinoJson v5.8.4
- elapsedMillis v1.0.3
- Adafruit_Unified_Sensor v1.0.2
- DHT_sensor_library v1.3.0
- Adafruit_BME280_Library v1.0.5
*/
//**********************************
//** USER SETTINGS *****************
//**********************************
// MQTT settings
#define MQTT_SERVER                         [REDACTED_MQTT_SERVER_IP]
#define MQTT_PORT                           [REDACTED_MQTT_SERVER_PORT]
#define MQTT_USER                           [REDACTED_MQTT_USER]
#define MQTT_PASSWORD                       [REDACTED_MQTT_PASSWD]
#define MQTT_USERID                         "ESP8266Client"

// MQTT topics
#define mqtt_temp_topic                     "sensor/temp_"
#define mqtt_humid_topic                    "sensor/hum_"
#define mqtt_pressure_topic                 "sensor/pres_"
#define mqtt_movement_topic                 "sensor/pir_"
#define mqtt_vibro_topic                    "sensor/extra_"
#define mqtt_light_topic                    "sensor/light_"
#define mqtt_light_analog_topic             "sensor/light_analog_"

#define MQTT_WILLTOPIC                      "control/online_"
#define MQTT_WILLQOS                        2
#define MQTT_WILLRETAIN                     HIGH
#define MQTT_STATE_OFF                      "off"
#define MQTT_STATE_ON                       "on"

#define mqtt_control_topic                  "control/module_"
#define mqtt_switch_bin_sensors_subtopic    "/switch_bin"
#define mqtt_switch_leds_subtopic           "/switch_leds"
#define mqtt_subtopic_set                   "/set"

// WiFi Settings
#define WiFiSSID                            [REDACTED_WIFI_SSID]
#define WiFiPSK                             [REDACTED_WIFI_PASSWORD]

//**********************************
//** PINOUT ************************
//** comment to deactivate        **
//**********************************
// Master switches:
//#define ESP_TEST1
#define ESP_COCINA
//#define USE_ESP32

#ifdef USE_ESP32
  #define DHTTYPE                             DHT11  // DHT22 (AM2302) / DHT11
  #define DHTPIN                              17     //IO17
  #define LED_RGB_RED                         2      //IO02
  #define LED_RGB_GREEN                       4      //IO04
  #define LED_RGB_BLUE                        16     //IO16

  #define PIN_PIR                             21     //IO21
  #define PIN_VIBRO                           22     //IO22
  #define PIN_LIGHT_SENSOR_DIGITAL            34     //IO34
  #define PIN_LIGHT_SENSOR_ANALOG             35
#endif

#ifdef ESP_TEST1
  #define LED_PIR                             16     //D0
  #define LED_VIBRO                           3      //RX - in dht11 breadboard
  #define LED_RGB_RED                         12     //D6
  #define LED_RGB_GREEN                       13     //D7
  #define LED_RGB_BLUE                        15     //D8
  #define PIN_PIR                             2      //D4
  #define PIN_VIBRO                           0      //D3 - dht11 breadboard
  #define PIN_LIGHT_SENSOR_DIGITAL            14     //D5
  #define PIN_LIGHT_SENSOR_ANALOG             A0     //A0

  #define PIN_I2C_BME280_SDA                  4     //D2
  #define PIN_I2C_BME280_SCL                  5     //D1
#endif

#ifdef ESP_COCINA
  #define DHTTYPE                             DHT22  // DHT22 (AM2302) / DHT11
  #define DHTPIN                              2      //D4 (DHT sensor)
//  #define LED_PIR                             4     //D2 - in dht11 breadboard
  #define LED_RGB_RED                         12     //D6
  #define LED_RGB_GREEN                       13     //D7
  #define LED_RGB_BLUE                        15     //D8
  #define PIN_PIR                             4      //D2 - dht22 box
//  #define PIN_PIR                             5      //D1
//  #define PIN_VIBRO                           4      //D2 - dht22 box
//  #define PIN_VIBRO                           0      //D3 - dht11 breadboard
//  #define PIN_LIGHT_SENSOR_DIGITAL            14     //D5
  #define PIN_LIGHT_SENSOR_ANALOG             A0     //A0
  #define NEGATE_SENSOR_ANALOG
#endif

//**********************************
//** Configuración *****************
//**********************************
#define VERBOSE                             true

#define MQTT_POSTINTERVAL_DHT22_SEC         40
#define MQTT_POSTINTERVAL_BME280_SEC        40
#define MQTT_POSTINTERVAL_LIGHT_SEC         45

#define DELAY_MIN_MS_ENTRE_MOVS             5000
#define DELAY_MIN_MS_ENTRE_VIBRO_SENSOR     4000
#define DELAY_MIN_MS_ENTRE_LIGHT_SENSOR     3000

#define DELTA_MS_TO_TURN_OFF_MOVS           3000
#define DELTA_MS_TO_TURN_OFF_VIBRO          3000
#define PERSISTENT_STATE_MS_UNTIL_STANDBY   2000

//Settings for recording samples
#define RESULTS_SAMPLE_RATE                 8            // # seconds between samples
#define SENSOR_HISTORY_RECORDS              10           // # records to keep
#define NUM_MAX_ERRORS_DHT                  20           // Abort on max

//**********************************
//** Librerías *********************
//**********************************
#ifdef USE_ESP32
  #include "WiFiEsp.h"
#else
  #include <ESP8266WiFi.h>
#endif
#include <PubSubClient.h>
//#include <ArduinoJson.h>
#include <elapsedMillis.h>
#include <list>
#ifdef DHTPIN
  #include <Adafruit_Sensor.h>  // - Adafruit Unified Sensor Library: https://github.com/adafruit/Adafruit_Sensor
  #include <DHT.h>              // - DHT Sensor Library: https://github.com/adafruit/DHT-sensor-library
  #include <DHT_U.h>
#endif
#ifdef PIN_I2C_BME280_SDA
  #include <Wire.h>
  #include <Adafruit_Sensor.h>
  #include <Adafruit_BME280.h>
#endif

//**********************************
//** Variables *********************
//**********************************
#define DELAY_MS_BETWEEN_RETRIES            250
#define DELAY_MS_BETWEEN_MQTT_PUB_STATE     35000

char MAC_char[18];                          //MAC address in ascii
//Wifi client
#ifdef USE_ESP32
  WiFiEspClient wifiClient;
#else
  WiFiClient wifiClient;
#endif
//MQTT client
void callback_mqtt_message_received(char* topic, byte* payload, unsigned int length);
PubSubClient client(MQTT_SERVER, MQTT_PORT, callback_mqtt_message_received, wifiClient);

// Control switches:
bool use_leds = HIGH;
bool in_default_state_use_leds = HIGH;
bool use_binary_sensors = HIGH;
bool in_default_state_binary_sensors = HIGH;

#ifdef DHTPIN                               // DHT22/DHT11 sensor settings.
DHT_Unified dht(DHTPIN, DHTTYPE);
// Variables for recording samples of the DHT22 sensor.
std::list<double> tempSamples;   //Collected results per interval
std::list<double> humidSamples;  //Collected results per interval
std::list<double> tempHistory;   //History over time.
std::list<double> humidHistory;  //History over time.
#endif

#ifdef PIN_I2C_BME280_SDA                   // BME280 sensor (I2C)
Adafruit_BME280 bme;                        // I2C
// Variables for recording samples of the DHT22 sensor.
std::list<double> bme_tempSamples;   //Collected results per interval
std::list<double> bme_humidSamples;  //Collected results per interval
std::list<double> bme_pressureSamples;  //Collected results per interval
std::list<double> bme_tempHistory;   //History over time.
std::list<double> bme_humidHistory;  //History over time.
std::list<double> bme_pressureHistory;  //History over time.
#endif

// Contadores de tiempo
elapsedMillis sinceStart;
int last_sensor_error;
int last_sensor_ok;
int last_dht_sensed;         //The last time a sample was taken from the DHT22 sensor.
int last_bme_sensed;         //The last time a sample was taken from the BME280 sensor.
int error_counter_dht;

// Last OK message for each sensor/topic:
int last_temp_post;
int last_humid_post;
int last_pressure_post;
int last_light_analog_post;

int last_switch_bin_state_post;
int last_switch_leds_state_post;

// Estados (para el output LED RGB)
#define STATE_ERROR            1
#define STATE_WARN             2
#define STATE_BIN_PUBLISH      3
#define STATE_OK_MEASURE       4
#define STATE_OK_PUBLISH       5
#define STATE_INIT             6
#define STATE_STANDBY          7
#define STATE_CRITICAL         8
int current_state;
int last_state_change;

// Binary sensors variables for control them within interrupts
volatile int last_pir_trigered = 0;
volatile int last_vibro_trigered = 0;
volatile int last_light_trigered = 0;

volatile bool pir_state = LOW;
volatile bool vibro_state = LOW;
volatile bool light_state = LOW;
bool last_light_post_state = LOW;

volatile bool flag_publish_pir = LOW;
volatile bool flag_publish_vibro = LOW;
volatile bool flag_publish_light = LOW;

//**********************************
//** SETUP
//**********************************
void setup()
{
  uint8_t MAC_array[6];

  Serial.begin(9600);
  setup_timers();
  setup_leds();
  set_state(STATE_INIT);
  connectWiFi();

  //Get the mac and convert it to a string.
  WiFi.macAddress(MAC_array);
  for (int i = 0; i < sizeof(MAC_array); ++i)
  {
    sprintf(MAC_char, "%s%02x", MAC_char, MAC_array[i]);
  }

#ifdef DHTPIN
  setup_dht_sensor();
#endif
#ifdef PIN_I2C_BME280_SDA
  setup_bme280_sensor();
#endif
  setup_boolean_sensors();

  if (VERBOSE) {
    Serial.print("MAC ADRESS: ");
    Serial.println(MAC_char);
  }
  set_state(STATE_CRITICAL);
}

//**********************************
//** LOOP
//**********************************
void loop()
{
  bool sensor_ok = false;
  bool sensed_data = false;
  bool bin_publish = false;
  int mqtt_retries = 0;

  //Reconnect if disconnected.
  if(WiFi.status() != WL_CONNECTED)
  {
    set_state(STATE_CRITICAL);
    connectWiFi();
  }

  //Check the MQTT connection and process it
  if (!client.connected())
  {
    while (!client.connected())
    {
      if (!client.connect((MQTT_USERID + String(MAC_char)).c_str(), MQTT_USER, MQTT_PASSWORD,
                          (MQTT_WILLTOPIC + String(MAC_char)).c_str(), MQTT_WILLQOS,
                          MQTT_WILLRETAIN, MQTT_STATE_OFF))
      {
        set_state(STATE_ERROR);
        if (VERBOSE)
        {
          Serial.print(i_text_state_pubsubclient(client.state()));
          Serial.print("MQTT retry # ");
          Serial.println(mqtt_retries);
        }
        delay(DELAY_MS_BETWEEN_RETRIES);
      }
      mqtt_retries += 1;
    }
    client.subscribe((mqtt_control_topic + String(MAC_char) + mqtt_switch_bin_sensors_subtopic + mqtt_subtopic_set).c_str());
    client.subscribe((mqtt_control_topic + String(MAC_char) + mqtt_switch_leds_subtopic + mqtt_subtopic_set).c_str());
    client.subscribe((MQTT_WILLTOPIC + String(MAC_char)).c_str());
    publish_switch_states();
  }
  client.loop();

  turn_off_motion_sensors_after_delay();
  bin_publish = publish_binary_sensors_if_flag_or_delta();
#ifdef DHTPIN
  sample_dht22_sensor_data(&sensed_data, &sensor_ok);
#endif
#ifdef PIN_I2C_BME280_SDA
  sample_bme280_sensor_data(&sensed_data, &sensor_ok);
#endif

  if (publish_analog_light_at_delta() || publish_dht22_sensor_data() || publish_bme280_sensor_data())
  {
    set_state(STATE_OK_PUBLISH);
  }
  else if (sensed_data && sensor_ok)
  {
    set_state(STATE_OK_MEASURE);
  }
  else if (sensed_data)
  {
    set_state(STATE_WARN);
  }
  else if (bin_publish)
  {
    set_state(STATE_BIN_PUBLISH);
  }
  else
  {
    auto_standby();
  }
}

//**********************************
//** METHODS
//**********************************
const char *i_text_state_pubsubclient(int state)
{
  //Returns the current state of the client. If a connection attempt fails, this can be used to get more information about the failure.
  switch (state)
  {
    case -4:
      return "MQTT_CONNECTION_TIMEOUT - the server did not respond within the keepalive time";
    case -3:
      return "MQTT_CONNECTION_LOST - the network connection was broken";
    case -2:
      return "MQTT_CONNECT_FAILED - the network connection failed";
    case -1:
      return "MQTT_DISCONNECTED - the client is disconnected cleanly";
    case 0:
      return "MQTT_CONNECTED - the cient is connected";
    case 1:
      return "MQTT_CONNECT_BAD_PROTOCOL - the server does not support the requested version of MQTT";
    case 2:
      return "MQTT_CONNECT_BAD_CLIENT_ID - the server rejected the client identifier";
    case 3:
      return "MQTT_CONNECT_UNAVAILABLE - the server was unable to accept the connection";
    case 4:
      return "MQTT_CONNECT_BAD_CREDENTIALS - the username/password were rejected";
    case 5:
      return "MQTT_CONNECT_UNAUTHORIZED - the client was not authorized to connect";
  }
  return "MQTT_STATE ????";
}

void auto_standby()
{
  if ((sinceStart - last_state_change > PERSISTENT_STATE_MS_UNTIL_STANDBY)
      && current_state != STATE_STANDBY && !i_state_critical())
  {
    set_state(STATE_STANDBY);
  }
}

void turn_off_motion_sensors_after_delay()
{
#ifdef PIN_PIR
  // PIR binary sensor to off after a delay:
  if (pir_state && (sinceStart - last_pir_trigered > DELTA_MS_TO_TURN_OFF_MOVS))
  {
    pir_state = LOW;
    flag_publish_pir = HIGH;
  }
#endif

#ifdef PIN_VIBRO
  // Vibration binary sensor to off after a delay:
  if (vibro_state && (sinceStart - last_vibro_trigered > DELTA_MS_TO_TURN_OFF_VIBRO))
  {
    vibro_state = LOW;
    flag_publish_vibro = HIGH;
  }
#endif
}

void set_color_rgb(uint16_t red, uint16_t green, uint16_t blue)
{
#ifdef LED_RGB_RED
#ifdef USE_ESP32
  // hueToRGB(color, brightness);  // call function to convert hue to RGB
  // write the RGB values to the pins
  ledcWrite(1, (uint32_t)(red / 4)); // write red component to channel 1, etc.
  ledcWrite(2, (uint32_t)(green / 4));
  ledcWrite(3, (uint32_t)(blue / 4));
#else
  analogWrite(LED_RGB_RED, red);
  analogWrite(LED_RGB_GREEN, green);
  analogWrite(LED_RGB_BLUE, blue);
#endif
#endif
}

bool i_state_critical()
{
  switch (current_state)
  {
    case STATE_INIT:
    case STATE_OK_MEASURE:
    case STATE_OK_PUBLISH:
    case STATE_BIN_PUBLISH:
    case STATE_STANDBY:
    {
      return false;
    }
//    case STATE_WEBACCESS:
    case STATE_ERROR:
    case STATE_WARN:
    case STATE_CRITICAL:
    {
      return true;
    }
  }
}

void set_state(int new_state)
{
  bool state_changed = current_state != new_state;
  current_state = new_state;
  last_state_change = sinceStart;

  // Set RGB LED state:
  if (use_leds)
  {
    switch (current_state)
    {
      case STATE_INIT:
      {
        set_color_rgb(1023, 1023, 1023);
        break;
      }
      case STATE_ERROR:
      {
        if (VERBOSE && state_changed)
          Serial.println("ERROR STATE (red)");
        set_color_rgb(1023, 0, 0);
        break;
      }
      case STATE_WARN:
      {
        if (VERBOSE && state_changed)
          Serial.println("WARNING STATE (R+.5G)");
        set_color_rgb(1023, 512, 0);
        break;
      }
      case STATE_CRITICAL:
      {
        if (VERBOSE && state_changed)
          Serial.println("CRITICAL STATE (violet)");
        set_color_rgb(1023, 0, 1023);
        break;
      }
      case STATE_OK_MEASURE:
      {
        set_color_rgb(0, 0, 1023);
        break;
      }
      case STATE_OK_PUBLISH:
      {
      //      Serial.println("OK PUBLISH");
        set_color_rgb(0, 1023, 0);
        break;
      }
      case STATE_BIN_PUBLISH:
      {
      //      Serial.println("OK PUBLISH");
        set_color_rgb(0, 255, 512);
        break;
      }
      case STATE_STANDBY:
      {
        set_color_rgb(0, 0, 0);
        break;
      }
    }
  }
  else
  {
    set_color_rgb(0, 0, 0);
  }
}

void isr_pir_change()
{
  if (use_binary_sensors && !pir_state && (sinceStart - last_pir_trigered > DELAY_MIN_MS_ENTRE_MOVS))
  {
    pir_state = HIGH;
    flag_publish_pir = HIGH;
  }
  last_pir_trigered = sinceStart;
}

void isr_vibro_change()
{
  if (use_binary_sensors && !vibro_state && (sinceStart - last_vibro_trigered > DELAY_MIN_MS_ENTRE_VIBRO_SENSOR))
  {
    vibro_state = HIGH;
    flag_publish_vibro = HIGH;
  }
  last_vibro_trigered = sinceStart;
}

#ifdef PIN_LIGHT_SENSOR_DIGITAL
void isr_light_sensor_change()
{
  if (use_binary_sensors && sinceStart - last_light_trigered > DELAY_MIN_MS_ENTRE_LIGHT_SENSOR)
  {
    bool new_light_state = digitalRead(PIN_LIGHT_SENSOR_DIGITAL);
    if (new_light_state != light_state)
    {
      light_state = !light_state;
      flag_publish_light = HIGH;
    }
  }
  last_light_trigered = sinceStart;
}
#endif

#ifdef PIN_LIGHT_SENSOR_ANALOG
float read_analog_light_percentage()
{
#ifdef NEGATE_SENSOR_ANALOG
  return round(100. * analogRead(PIN_LIGHT_SENSOR_ANALOG) /  10.23) / 100.;
#else
  return round(100. * (1023 - analogRead(PIN_LIGHT_SENSOR_ANALOG)) /  10.23) / 100.;
#endif
}
#endif

void sample_dht22_sensor_data(bool *sampled, bool *sample_ok)
{
  *sampled = false;
  *sample_ok = false;

#ifdef DHTPIN
  // Collect the DHT22 sensor data
  if(sinceStart - last_dht_sensed > RESULTS_SAMPLE_RATE * 1000)
  {
    double temp = -999;
    double humid = -999;
    sensors_event_t event;

    *sampled = true;
    //Collect the temperature from a sensor.
    dht.temperature().getEvent(&event);
    if (!isnan(event.temperature))
    {
      temp = event.temperature;
      if (VERBOSE) {
        Serial.print("Temp: ");
        Serial.print(temp);
        Serial.print(" ^C, ");
      }
    }
    // Get humidity event and print its value.
    dht.humidity().getEvent(&event);
    if (!isnan(event.relative_humidity))
    {
      humid = event.relative_humidity;
      if (VERBOSE) {
        Serial.print("Humidity: ");
        Serial.print(humid);
        Serial.println(" %");
      }
    }

    if ((temp == -999) || (humid == -999))
    {
      sensor_t sensor;
      if (VERBOSE) {
        Serial.print("DHT ERROR # ");
        Serial.print(error_counter_dht);
        Serial.print(": ");
        Serial.print(temp);
        Serial.print(" / ");
        Serial.println(humid);
      }
      dht.begin();
      dht.temperature().getSensor(&sensor);
      last_sensor_error = sinceStart;
      error_counter_dht += 1;
      *sample_ok = false;

      if (error_counter_dht > NUM_MAX_ERRORS_DHT)
        reset_exec();
    }
    else
    {
      last_sensor_ok = sinceStart;
      *sample_ok = true;
      error_counter_dht = 0;

      //Make sure a valid temperature was sampled
      if(temp != -999)
        tempSamples.push_front(temp);

      if(humid != -999)
        humidSamples.push_front(humid);
    }

    last_dht_sensed = sinceStart;
  }
#endif
}

void sample_bme280_sensor_data(bool *sampled, bool *sample_ok)
{
  *sampled = false;
  *sample_ok = false;

#ifdef PIN_I2C_BME280_SDA
  // Collect the sensor data
  if(sinceStart - last_bme_sensed > RESULTS_SAMPLE_RATE * 1000)
  {
    double temp, humid, pressure;

    *sampled = true;
    *sample_ok = true;
    temp = bme.readTemperature();
    humid = bme.readHumidity();
    pressure = bme.readPressure() / 100.0F;
    // #define SEALEVELPRESSURE_HPA (1013.25)      // 1 atm std.
    //bme.readAltitude(SEALEVELPRESSURE_HPA);

    if (VERBOSE) {
      Serial.print("Temp: ");
      Serial.print(temp);
      Serial.print(" ^C, ");
      Serial.print("Humidity: ");
      Serial.print(humid);
      Serial.print(" %, ");
      Serial.print("Pressure: ");
      Serial.print(pressure);
      Serial.println(" mbar");
    }
    if (temp)
      bme_tempSamples.push_front(temp);
    if (humid)
      bme_humidSamples.push_front(humid);
    if (pressure)
      bme_pressureSamples.push_front(pressure);
    if (!temp | !humid | !pressure)
      *sample_ok = false;
    last_bme_sensed = sinceStart;
  }
#endif
}

void calc_sensor_stats(std::list<double> *samples, std::list<double> *history)
{
  int count = 0;
  double samples_sum = 0;
  double samples_average;

  if(samples->size() > 0)
  {
    for(std::list<double>::iterator sensiter = samples->begin(); sensiter != samples->end(); sensiter++)
    {
      count++;
      samples_sum += *sensiter;
    }
    samples_average = samples_sum / count;

    //Add the new data to the history.
    history->push_front(samples_average);
    if(history->size() > SENSOR_HISTORY_RECORDS)
    {
      history->pop_back();
    }
  }
  samples->clear();
}

//**********************************
//** Setup methods
//**********************************
void setup_timers()
{
  sinceStart = 0;
  last_state_change = 0;
  last_sensor_error = 0;
  last_sensor_ok = 0;
  last_dht_sensed = 0;                //The last time a sample was taken from the DHT22 sensor.
  error_counter_dht = 1;

  // Init values to wait some time before the 1st publish.
  last_temp_post = 15000;
  last_humid_post = 15000;
  last_pressure_post = 15000;
  last_light_analog_post = 10000;
  last_switch_bin_state_post = 0;
  last_switch_leds_state_post = 0;
}

void setup_leds()
{
#ifdef LED_PIR
  pinMode(LED_PIR, OUTPUT);
#endif
#ifdef LED_VIBRO
  pinMode(LED_VIBRO, OUTPUT);
#endif

#ifdef LED_RGB_RED
#ifdef USE_ESP32
  ledcAttachPin(LED_RGB_RED, 1); // assign RGB led pins to channels
  ledcAttachPin(LED_RGB_GREEN, 2);
  ledcAttachPin(LED_RGB_BLUE, 3);
  // Initialize channels
  // channels 0-15, resolution 1-16 bits, freq limits depend on resolution
  // ledcSetup(uint8_t channel, uint32_t freq, uint8_t resolution_bits);
  ledcSetup(1, 12000, 8); // 12 kHz PWM, 8-bit resolution
  ledcSetup(2, 12000, 8);
  ledcSetup(3, 12000, 8);
#else
  pinMode(LED_RGB_RED, OUTPUT);
  pinMode(LED_RGB_GREEN, OUTPUT);
  pinMode(LED_RGB_BLUE, OUTPUT);
#endif
#endif
}

#ifdef DHTPIN
void setup_dht_sensor()
{
  dht.begin();
  sensor_t sensor;
  dht.temperature().getSensor(&sensor);
  if (VERBOSE) {
    Serial.println("------------------------------------");
    Serial.println("Temperature");
    Serial.print  ("Sensor:       "); Serial.println(sensor.name);
    Serial.print  ("Driver Ver:   "); Serial.println(sensor.version);
    Serial.print  ("Unique ID:    "); Serial.println(sensor.sensor_id);
    Serial.print  ("Max Value:    "); Serial.print(sensor.max_value); Serial.println(" *C");
    Serial.print  ("Min Value:    "); Serial.print(sensor.min_value); Serial.println(" *C");
    Serial.print  ("Resolution:   "); Serial.print(sensor.resolution); Serial.println(" *C");
    Serial.println("------------------------------------");
  }
  dht.humidity().getSensor(&sensor);
  // Print humidity sensor details.
  dht.humidity().getSensor(&sensor);
  if (VERBOSE) {
    Serial.println("------------------------------------");
    Serial.println("Humidity");
    Serial.print  ("Sensor:       "); Serial.println(sensor.name);
    Serial.print  ("Driver Ver:   "); Serial.println(sensor.version);
    Serial.print  ("Unique ID:    "); Serial.println(sensor.sensor_id);
    Serial.print  ("Max Value:    "); Serial.print(sensor.max_value); Serial.println("%");
    Serial.print  ("Min Value:    "); Serial.print(sensor.min_value); Serial.println("%");
    Serial.print  ("Resolution:   "); Serial.print(sensor.resolution); Serial.println("%");
    Serial.println("------------------------------------");
  }
}
#endif

#ifdef PIN_I2C_BME280_SDA
void setup_bme280_sensor()
{
    bool bme_status;

    // default settings
    bme_status = bme.begin();
    if (!bme_status)
    {
        if (VERBOSE)
          Serial.println("Could not find a valid BME280 sensor, check wiring!");
        set_state(STATE_CRITICAL);
        delay(10000);
        reset_exec();
    }
//    bme.setSampling(sensor_mode mode              = MODE_NORMAL,
//			 sensor_sampling tempSampling  = SAMPLING_X16,
//			 sensor_sampling pressSampling = SAMPLING_X16,
//			 sensor_sampling humSampling   = SAMPLING_X16,
//			 sensor_filter filter          = FILTER_OFF,
//			 standby_duration duration     = STANDBY_MS_0_5
//			 );

    bme.setSampling(Adafruit_BME280::MODE_NORMAL, Adafruit_BME280::SAMPLING_X2, Adafruit_BME280::SAMPLING_X2, Adafruit_BME280::SAMPLING_X2, Adafruit_BME280::FILTER_OFF, Adafruit_BME280::STANDBY_MS_1000);

    delay(100); // let sensor boot up
}
#endif

void setup_boolean_sensors()
{
#ifdef PIN_PIR
  pinMode(PIN_PIR, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_PIR), isr_pir_change, CHANGE);
#endif

#ifdef PIN_VIBRO
  pinMode(PIN_VIBRO, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_VIBRO), isr_vibro_change, CHANGE);
#endif

#ifdef PIN_LIGHT_SENSOR_DIGITAL
  pinMode(PIN_LIGHT_SENSOR_DIGITAL, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_LIGHT_SENSOR_DIGITAL), isr_light_sensor_change, CHANGE);
#endif

#ifdef PIN_LIGHT_SENSOR_ANALOG
  pinMode(PIN_LIGHT_SENSOR_ANALOG, INPUT);
#endif
}

void connectWiFi()
{
  elapsedMillis wifi_try = 0;
#ifdef USE_ESP32
  //char *pass = (char*) malloc(strlen(WiFiPSK));
  //strcpy(pass, WiFiPSK);
  WiFi.begin((char *)WiFiSSID, (const char *)WiFiPSK);
#else
  WiFi.mode(WIFI_STA);
  WiFi.begin(WiFiSSID, WiFiPSK);
#endif

  if (VERBOSE) {
    Serial.print("Attempting to connect to WPA SSID: ");
    Serial.print(WiFiSSID);
  }

  set_state(STATE_CRITICAL);
  while (WiFi.status() != WL_CONNECTED)
  {
    if (VERBOSE)
      Serial.print (".");
    //Delay until connected.
    delay(DELAY_MS_BETWEEN_RETRIES);
    if (wifi_try > 60000)
      reset_exec();
  }
  if (VERBOSE) {
    Serial.println("You are connected to the network");
    printWifiStatus();
  }
  set_state(STATE_STANDBY);
}

void printWifiStatus()
{
  // print the SSID of the network you're attached to
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());

  // print your WiFi shield's IP address
  IPAddress ip = WiFi.localIP();
  Serial.print("IP Address: ");
  Serial.println(ip);

#ifndef USE_ESP32
// print the received signal strength
  long rssi = WiFi.RSSI();
  Serial.print("Signal strength (RSSI):");
  Serial.print(rssi);
  Serial.println(" dBm");
#endif
}

void reset_exec()
{
  if (VERBOSE)
    Serial.println("ABORTING ...");
  set_color_rgb(1023, 200, 200);
  delay(30000);
  ESP.restart();
}

//**********************************
//** MQTT
//**********************************
void publish_switch_states()
{
  if (!in_default_state_binary_sensors && (sinceStart - last_switch_bin_state_post > DELAY_MS_BETWEEN_MQTT_PUB_STATE))
  {
    if (client.publish((mqtt_control_topic + String(MAC_char) + mqtt_switch_bin_sensors_subtopic).c_str(),
                       use_binary_sensors ? MQTT_STATE_ON : MQTT_STATE_OFF, HIGH))
    {
      last_switch_bin_state_post = sinceStart;
    }
  }
  if (!in_default_state_use_leds && (sinceStart - last_switch_leds_state_post > DELAY_MS_BETWEEN_MQTT_PUB_STATE))
  {
    if (client.publish((mqtt_control_topic + String(MAC_char) + mqtt_switch_leds_subtopic).c_str(),
                       use_leds ? MQTT_STATE_ON : MQTT_STATE_OFF, HIGH))
    {
      last_switch_leds_state_post = sinceStart;
    }
  }
}

bool publish_binary_sensors_if_flag_or_delta()
{
  bool any_publish = false;
#ifdef PIN_PIR
  // Update PIR state:
  if (flag_publish_pir)
  {
#ifdef LED_PIR
    if (use_leds)
      digitalWrite(LED_PIR, pir_state);
#endif
    flag_publish_pir = !publish_mqtt_binary_sensor("MOVEMENT", "MOVEMENT OFF", pir_state, mqtt_movement_topic);
    any_publish = !flag_publish_pir;
  }
#endif

#ifdef PIN_VIBRO
  // Update vibro sensor state:
  if (flag_publish_vibro)
  {
#ifdef LED_VIBRO
    if (use_leds)
      digitalWrite(LED_VIBRO, vibro_state);
#endif
    flag_publish_vibro = !publish_mqtt_binary_sensor("VIBRATION", "VIBRATION OFF", vibro_state, mqtt_vibro_topic);
    any_publish = !flag_publish_vibro || any_publish;
  }
#endif

#ifdef PIN_LIGHT_SENSOR_DIGITAL
  // Update LIGHT state:
  if (flag_publish_light || (sinceStart - last_light_analog_post > MQTT_POSTINTERVAL_LIGHT_SEC * 1000))
  {
    if (!flag_publish_light)
    {
      light_state = digitalRead(PIN_LIGHT_SENSOR_DIGITAL);
      if (light_state != last_light_post_state)
      {
        last_light_post_state = light_state;
        flag_publish_light = !publish_mqtt_binary_sensor("LIGHT", "LIGHT OFF", !light_state, mqtt_light_topic);
        any_publish = !flag_publish_light || any_publish;
      }
    }
    else
    {
      last_light_post_state = light_state;
      flag_publish_light = !publish_mqtt_binary_sensor("LIGHT", "LIGHT OFF", !light_state, mqtt_light_topic);
      any_publish = !flag_publish_light || any_publish;
    }
  }
#endif

  return any_publish;
}

bool publish_analog_light_at_delta()
{
#ifdef PIN_LIGHT_SENSOR_ANALOG
  if (sinceStart - last_light_analog_post > MQTT_POSTINTERVAL_LIGHT_SEC * 1000)
  {
    if (publish_mqtt_data("LIGHT AO", mqtt_light_analog_topic, String(read_analog_light_percentage()).c_str(), false))
    {
      last_light_analog_post = sinceStart;
      return true;
    }
  }
#endif
  return false;
}

bool publish_dht22_sensor_data()
{
  bool publishing_t = false, publishing_h = false;

#ifdef DHTPIN
  //post MQTT DHT22 data every X seconds
  if ((error_counter_dht == 0) && (sinceStart - last_temp_post > MQTT_POSTINTERVAL_DHT22_SEC * 1000))
  {
    calc_sensor_stats(&tempSamples, &tempHistory);
    if(tempHistory.size() > 0)
    {
      publishing_t = publish_mqtt_data("TEMP", mqtt_temp_topic,
                                       String(tempHistory.front()).c_str(), false);
      if (publishing_t)
        last_temp_post = sinceStart;
    }
  }

  if ((error_counter_dht == 0) && (sinceStart - last_humid_post > MQTT_POSTINTERVAL_DHT22_SEC * 1000))
  {
    calc_sensor_stats(&humidSamples, &humidHistory);
    if(humidHistory.size() > 0)
    {
      publishing_h = publish_mqtt_data("HUMID", mqtt_humid_topic,
                                       String(humidHistory.front()).c_str(), false);
      if (publishing_h)
        last_humid_post = sinceStart;
    }
  }
#endif

//    return publishing_t && publishing_h;
  return publishing_t || publishing_h;
}

bool publish_bme280_sensor_data()
{
  bool publishing_t = false, publishing_h = false, publishing_p = false;
#ifdef PIN_I2C_BME280_SDA
  //post MQTT BME280 data every X seconds
  if (sinceStart - last_temp_post > MQTT_POSTINTERVAL_BME280_SEC * 1000)
  {
    calc_sensor_stats(&bme_tempSamples, &bme_tempHistory);
    if(bme_tempHistory.size() > 0)
      publishing_t = publish_mqtt_data("TEMP", mqtt_temp_topic,
                                       String(bme_tempHistory.front()).c_str(), false);
    if (publishing_t)
        last_temp_post = sinceStart;
  }

  if (sinceStart - last_humid_post > MQTT_POSTINTERVAL_BME280_SEC * 1000)
  {
    calc_sensor_stats(&bme_humidSamples, &bme_humidHistory);
    if(bme_humidHistory.size() > 0)
      publishing_h = publish_mqtt_data("HUMID", mqtt_humid_topic,
                                       String(bme_humidHistory.front()).c_str(), false);
    if (publishing_h)
      last_humid_post = sinceStart;
  }

  if (sinceStart - last_pressure_post > MQTT_POSTINTERVAL_BME280_SEC * 1000)
  {
    calc_sensor_stats(&bme_pressureSamples, &bme_pressureHistory);
    if(bme_pressureHistory.size() > 0)
      publishing_p = publish_mqtt_data("PRESSURE", mqtt_pressure_topic,
                                       String(bme_pressureHistory.front()).c_str(), false);
    if (publishing_p)
      last_pressure_post = sinceStart;
  }
#endif
  return publishing_t || publishing_h || publishing_p;
}

bool publish_mqtt_data(const char* type_publish, const char* topic_prefix, const char* payload, boolean retained)
{
  bool published;

  published = client.publish((topic_prefix + String(MAC_char)).c_str(), payload, retained);
  if (VERBOSE && published)
  {
    Serial.print("PUBLISH ");
    Serial.print(type_publish);
    Serial.print(": topic=");
    Serial.print((topic_prefix + String(MAC_char)).c_str());
    Serial.print(" -> ");
    Serial.println(payload);
  }
  return published;
}

bool publish_mqtt_binary_sensor(const char* name_on, const char* name_off,
                                bool state, const char* topic)
{
  if (state)
    return publish_mqtt_data(name_on, topic, MQTT_STATE_ON, true);
  else
    return publish_mqtt_data(name_off, topic, MQTT_STATE_OFF, true);
}

void publish_online_state()
{
  bool publish_ok = false;
  do {
    publish_ok = client.publish((MQTT_WILLTOPIC + String(MAC_char)).c_str(), MQTT_STATE_ON, MQTT_WILLRETAIN);
  } while (!publish_ok);

  if (VERBOSE)
    Serial.println("PUBLISHING STATE ON");
}

//bool read_json(byte *payload, unsigned int payload_length)
//{
//  StaticJsonBuffer<500> jsonBuffer;
//  char *json = (char*)payload;
//  JsonObject& root = jsonBuffer.parseObject(json);
//
//  // Test if parsing succeeds.
//  if (!root.success())
//  {
//    Serial.println("parseObject() failed");
//    return false;
//  }
//  else if (root.containsKey("color"))
//  {
//    // Fetch values.
//    uint16_t R, G, B;
//    R = root["color"][0];
//    G = root["color"][1];
//    B = root["color"][2];
//    Serial.print("RGB RECEIVED: (");
//    Serial.print(R);
//    Serial.print(", ");
//    Serial.print(G);
//    Serial.print(", ");
//    Serial.print(B);
//    Serial.println(")");
//    set_color_rgb(4 * R, 4 * G, 4 * B);
//    return client.publish((mqtt_control_topic_out + String(MAC_char)).c_str(), "COLOR SET");
//  }
//  else if (root.containsKey("led"))
//  {
//    bool new_use_leds = root["led"];
//    Serial.print("RECEIVED LED USE=");
//    Serial.print(new_use_leds);
//    if (new_use_leds != use_leds)
//    {
//      use_leds = new_use_leds;
//      set_state(STATE_STANDBY);
//      return client.publish((mqtt_control_topic_out + String(MAC_char)).c_str(), "USE LED CHANGE OK");
//    }
//    return client.publish((mqtt_control_topic_out + String(MAC_char)).c_str(), "USE LED NO CHANGE");
//  }
//  else if (root.containsKey("binary_sensors"))
//  {
//    bool new_use_bin_sensors = root["binary_sensors"];
//    Serial.print("RECEIVED BINARY_SENSORS USE=");
//    Serial.print(new_use_bin_sensors);
//    if (new_use_bin_sensors != use_binary_sensors)
//    {
//      use_binary_sensors = new_use_bin_sensors;
//      return client.publish((mqtt_control_topic_out + String(MAC_char)).c_str(), "USE BINARY_SENSORS CHANGE OK");
//    }
//    return client.publish((mqtt_control_topic_out + String(MAC_char)).c_str(), "USE BINARY_SENSORS NO CHANGE");
//  }
//
//  return client.publish((mqtt_control_topic_out + String(MAC_char)).c_str(), payload, payload_length);
//}

bool i_contains(const char *str1, const char *str2)
{
  char *contains;
  contains = strstr(str1, str2);
  if (contains)
    return true;
  return false;
}

void i_print_mqtt_msg(const char *topic, const char *message)
{
  if (VERBOSE)
  {
    Serial.println("MQTT MSG ARRIVED:");
    Serial.print(" --> topic=");
    Serial.println(topic);
    Serial.print(" --> payload=");
    Serial.println(message);
  }
}

bool mqtt_switch_check(const char *topic, const char *message,
                       const char *topic_switch,
                       const char *str_debug_set_switch,
                       bool switch_value_old, bool *switch_value)
{
  if (i_contains(topic, topic_switch) && i_contains(topic, MAC_char) && i_contains(topic, mqtt_subtopic_set))
  {
    bool new_switch_value;

    new_switch_value = i_contains(message, MQTT_STATE_ON);
    *switch_value = new_switch_value;
    if (new_switch_value != switch_value_old)
    {
      if (VERBOSE)
      {
        i_print_mqtt_msg(topic, message);
        Serial.print(str_debug_set_switch);
        Serial.println(new_switch_value ? MQTT_STATE_ON : MQTT_STATE_OFF);
      }
      client.publish((mqtt_control_topic + String(MAC_char) + topic_switch).c_str(),
                     new_switch_value ? MQTT_STATE_ON : MQTT_STATE_OFF, HIGH);
    }
    return true;
  }
  return false;
}

void callback_mqtt_message_received(char* topic, byte* payload, unsigned int payload_length)
{
  char *message;
  bool switch_value;
  byte *p = (byte*)malloc(payload_length);
  memcpy(p, payload, payload_length);
  message = (char*)p;

//  Serial.print("- MQTT RECEIVED: ");
//  Serial.println(topic);
  if (i_contains(topic, MQTT_WILLTOPIC) && i_contains(topic, MAC_char))
  {
    if (!i_contains(message, MQTT_STATE_ON))
    {
      i_print_mqtt_msg(topic, message);
      publish_online_state();
      Serial.println("published_online_state");
    }
  }
  else if (mqtt_switch_check(topic, message, mqtt_switch_bin_sensors_subtopic,
                        "SET use_binary_sensors = ", use_binary_sensors, &switch_value))
  {
    //Serial.println("USE BIN SENSORS CHANGED");
    use_binary_sensors = switch_value;
    in_default_state_binary_sensors = false;
  }
  else if (mqtt_switch_check(topic, message, mqtt_switch_leds_subtopic,
                        "SET use_leds = ", use_leds, &switch_value))
  {
    //Serial.println("USE LEDS CHANGED");
    use_leds = switch_value;
    in_default_state_use_leds = false;
  }
  else
  {
    Serial.println("WTF MQTT MESSAGE:");
    i_print_mqtt_msg(topic, message);
//    read_json(p, payload_length);
  }
  free(p);
}
