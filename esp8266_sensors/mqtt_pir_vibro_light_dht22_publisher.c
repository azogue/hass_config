/*
# *Detector de movimiento, vibración, luz, temperatura y humedad relativa*

*Detector inalámbrico de movimiento, vibración, luz, temperatura y humedad relativa* sobre plataforma ESP8266,
que comunica los valores detectados a un servidor MQTT (like `mosquitto`). Útil para colocarlo en recintos alejados
pero con acceso a wifi en integraciones de domótica.

De funcionamiento muy sencillo, se conecta a la wifi local, y de ahí al servidor MQTT, donde publica los valores
de temperatura, humedad y porcentaje de iluminación cada X segundos
(`MQTT_POSTINTERVAL_LIGHT_SEC` & `MQTT_POSTINTERVAL_DHT22_SEC`).
Los sensores binarios (movimiento, vibración e iluminación) se tratan mediante interrupciones (vs polling)
y publican estados de 'on'/'off' en cuanto se produce un evento de activación.

Componentes:
  - ESP8266 mcu 1.0 dev kit
  - DHT22 sensor
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
#define mqtt_movement_topic                 "sensor/pir_"
#define mqtt_vibro_topic                    "sensor/extra_"
#define mqtt_light_topic                    "sensor/light_"
#define mqtt_light_analog_topic             "sensor/light_analog_"
```

Al nombre del `topic` se le añade la MAC de la Wifi del ESP8266 (ej: `sensor/light_analog_abcdef012345`), de forma
que los identificadores son únicos para cada chip, por lo que, si utilizas varios de estos detectores, no hay
necesidad de cambiar el programa para cada uno.

### Changelog ESP8266 MQTT Publisher

- v1.0: PIR+Vibration+Light(AO+DO)+DHT22 sensors publishing values to a local mosquitto server.
- v1.1: Fixed some errors, Better error handling with DHT22, different publish frecuency for light & DHT22,
        negate digital_light sensor, and some refactoring.

### Librerías:

- ESP8266WiFi v1.0 || WiFiEsp v2.1.2
- PubSubClient v2.6
- elapsedMillis v1.0.3
- Adafruit_Unified_Sensor v1.0.2
- DHT_sensor_library v1.3.0

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

#define mqtt_temp_topic                     "sensor/temp_"
#define mqtt_humid_topic                    "sensor/hum_"
#define mqtt_movement_topic                 "sensor/pir_"
#define mqtt_vibro_topic                    "sensor/extra_"
#define mqtt_light_topic                    "sensor/light_"
#define mqtt_light_analog_topic             "sensor/light_analog_"

// WiFi Settings
#define WiFiSSID                            [REDACTED_WIFI_SSID]
#define WiFiPSK                             [REDACTED_WIFI_PASSWORD]

//**********************************
//** PLATFORM & PINOUT *************
//** comment to deactivate        **
//**********************************
#define USE_ESP32

//#define DHTPIN                              2      //D4 (DHT sensor)

//#define LED_BLUE_PIR                        14     //D5
//#define LED_YELLOW_VIBRO                    0      //D3

//#define LED_RGB_RED                         12     //D6
//#define LED_RGB_GREEN                       13     //D7
//#define LED_RGB_BLUE                        15     //D8
#define LED_RGB_RED                         2     //IO02
#define LED_RGB_GREEN                       4     //IO04
#define LED_RGB_BLUE                        16    //IO16

//#define PIN_PIR                             5      //D1
//#define PIN_VIBRO                           4      //D2
//#define PIN_LIGHT_SENSOR_DIGITAL            14     //D5
//#define PIN_LIGHT_SENSOR_ANALOG             A0     //A0
#define PIN_PIR                             21      //IO21
#define PIN_VIBRO                           22      //IO22
//#define PIN_LIGHT_SENSOR_DIGITAL            14     //D5
//#define PIN_LIGHT_SENSOR_ANALOG             A0     //A0

//**********************************
//** Configuración *****************
//**********************************
#define VERBOSE

#define MQTT_POSTINTERVAL_DHT22_SEC         40
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

//**********************************
//** Librerías *********************
//**********************************
#ifdef USE_ESP32
  #include "WiFiEsp.h"
#else
  #include <ESP8266WiFi.h>
#endif
#include <PubSubClient.h>
#include <elapsedMillis.h>
#ifdef DHTPIN
  #include <list>
  #include <Adafruit_Sensor.h>  // - Adafruit Unified Sensor Library: https://github.com/adafruit/Adafruit_Sensor
  #include <DHT.h>              // - DHT Sensor Library: https://github.com/adafruit/DHT-sensor-library
  #include <DHT_U.h>
#endif

//**********************************
//** Variables *********************
//**********************************
#ifdef USE_ESP32
  WiFiEspClient espClient;                       //For the MQTT client
#else
  WiFiClient espClient;                       //For the MQTT client
#endif
PubSubClient client(espClient);             //MQTT client
char MAC_char[18];                          //MAC address in ascii
#define DELAY_MS_BETWEEN_RETRIES            250

#ifdef DHTPIN
// DHT22 sensor settings.
#define DHTTYPE DHT22                       // DHT22 (AM2302)
DHT_Unified dht(DHTPIN, DHTTYPE);

// Variables for recording samples of the DHT22 sensor.
std::list<double> tempSamples;   //Collected results per interval
std::list<double> humidSamples;  //Collected results per interval
std::list<double> tempHistory;   //History over time.
std::list<double> humidHistory;  //History over time.
#endif

// Contadores de tiempo
elapsedMillis sinceStart;
int last_sensor_error;
int last_sensor_ok;
int last_dht_sensed;         //The last time a sample was taken from the DHT22 sensor.
int error_counter_dht;

int last_dht22_post;            // Init value to wait some time before the 1st publish.
int last_light_post;            // Init value to wait some time before the 1st publish.

int last_state_change;

// Estados (para el output LED RGB)
#define STATE_ERROR            1
#define STATE_WARN             2
#define STATE_OK_MEASURE       3
#define STATE_OK_PUBLISH       4
#define STATE_INIT             5
#define STATE_STANDBY          7
#define STATE_CRITICAL         8
int current_sensor_state;

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
#ifdef DHTPIN
  setup_temp_sensor();
#endif
  setup_boolean_sensors();

  //Get the mac and convert it to a string.
  WiFi.macAddress(MAC_array);
  for (int i = 0; i < sizeof(MAC_array); ++i)
  {
    sprintf(MAC_char, "%s%02x", MAC_char, MAC_array[i]);
  }

#ifdef VERBOSE
  Serial.print("MAC ADRESS: ");
  Serial.println(MAC_char);
#endif
  set_state(STATE_CRITICAL);
}

//**********************************
//** LOOP
//**********************************

void loop()
{
  bool sensor_ok = false;
  bool sensed_data = false;

  //Reconnect if disconnected.
  if(WiFi.status() != WL_CONNECTED)
  {
    set_state(STATE_CRITICAL);
    connectWiFi();
  }

  //Check the MQTT connection and process it
  while (!client.connected())
  {
    set_state(STATE_ERROR);
    client.connect(MQTT_USERID, MQTT_USER, MQTT_PASSWORD);
    delay(DELAY_MS_BETWEEN_RETRIES * 2);
  }
  client.loop();

  turn_off_motion_sensors_after_delay();
  publish_motion_and_light_sensors_if_flag_or_delta();
#ifdef DHTPIN
  sample_dht22_sensor_data(&sensed_data, &sensor_ok);
#endif
  if (publish_dht22_sensor_data())
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
  else
  {
    auto_standby();
  }
}

//**********************************
//** METHODS
//**********************************

void auto_standby()
{
  if ((sinceStart - last_state_change > PERSISTENT_STATE_MS_UNTIL_STANDBY)
      && current_sensor_state != STATE_STANDBY && !i_state_critical())
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

void publish_motion_and_light_sensors_if_flag_or_delta()
{
#ifdef PIN_PIR
  // Update PIR state:
  if (flag_publish_pir)
  {
#ifdef LED_BLUE_PIR
    digitalWrite(LED_BLUE_PIR, pir_state);
#endif
    flag_publish_pir = !publish_mqtt_binary_sensor("MOVEMENT", "MOVEMENT OFF", pir_state,
                                                   (mqtt_movement_topic+String(MAC_char)).c_str());
  }
#endif

#ifdef PIN_VIBRO
  // Update vibro sensor state:
  if (flag_publish_vibro)
  {
#ifdef LED_YELLOW_VIBRO
    digitalWrite(LED_YELLOW_VIBRO, vibro_state);
#endif
    flag_publish_vibro = !publish_mqtt_binary_sensor("VIBRATION", "VIBRATION OFF", vibro_state,
                                                     (mqtt_vibro_topic+String(MAC_char)).c_str());
  }
#endif

#ifdef PIN_LIGHT_SENSOR_DIGITAL
  // Update LIGHT state:
  if (flag_publish_light || (sinceStart - last_light_post > MQTT_POSTINTERVAL_LIGHT_SEC * 1000))
  {
    float light_percentage;

    if (!flag_publish_light)
    {
      light_state = digitalRead(PIN_LIGHT_SENSOR_DIGITAL);
      if (light_state != last_light_post_state)
      {
        last_light_post_state = light_state;
        flag_publish_light = !publish_mqtt_binary_sensor("LIGHT", "LIGHT OFF", !light_state,
                                                         (mqtt_light_topic+String(MAC_char)).c_str());
      }
    }
    else
    {
      last_light_post_state = light_state;
      flag_publish_light = !publish_mqtt_binary_sensor("LIGHT", "LIGHT OFF", !light_state,
                                                       (mqtt_light_topic+String(MAC_char)).c_str());
    }

#ifdef PIN_LIGHT_SENSOR_ANALOG
    light_percentage = read_analog_light_percentage();
    flag_publish_light = !publish_mqtt_data("LIGHT", (mqtt_light_analog_topic+String(MAC_char)).c_str(),
                                            String(light_percentage).c_str(), false);
#endif

    if (!flag_publish_light)
      last_light_post = sinceStart;
  }
#endif
}

bool publish_dht22_sensor_data()
{
#ifdef DHTPIN
  //post MQTT DHT22 data every X seconds
  if ((error_counter_dht == 0) && (sinceStart - last_dht22_post > MQTT_POSTINTERVAL_DHT22_SEC * 1000))
  {
    bool publishing = false;

    calc_sensor_stats(&tempSamples, &tempHistory);
    if(tempHistory.size() > 0)
    {
      publishing = publish_mqtt_data("TEMP", (mqtt_temp_topic+String(MAC_char)).c_str(),
                                     String(tempHistory.front()).c_str(), false);
    }

    calc_sensor_stats(&humidSamples, &humidHistory);
    if(humidHistory.size() > 0)
    {
      publishing = publish_mqtt_data("HUMID", (mqtt_humid_topic+String(MAC_char)).c_str(),
                                     String(humidHistory.front()).c_str(), false);
    }

    if (publishing)
      last_dht22_post = sinceStart;

    return publishing;
  }
#endif

  return false;
}

bool publish_mqtt_data(const char* type_publish, const char* topic, const char* payload, boolean retained)
{
#ifdef VERBOSE
  Serial.print("PUBLISH ");
  Serial.print(type_publish);
  Serial.print(": topic=");
  Serial.print(topic);
  Serial.print(" -> ");
  Serial.println(payload);
#endif
  return client.publish(topic, payload, retained);
}

bool publish_mqtt_binary_sensor(const char* name_on, const char* name_off,
                                bool state, const char* topic)
{
  if (state)
    return publish_mqtt_data(name_on, topic, "on", false);
  else
    return publish_mqtt_data(name_off, topic, "off", false);
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
  switch (current_sensor_state)
  {
    case STATE_INIT:
    case STATE_OK_MEASURE:
    case STATE_OK_PUBLISH:
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
  current_sensor_state = new_state;
  last_state_change = sinceStart;

  // Set RGB LED state:
  switch (current_sensor_state)
  {
    case STATE_INIT:
    {
      set_color_rgb(1023, 1023, 1023);
      break;
    }
    case STATE_ERROR:
    {
#ifdef VERBOSE
      Serial.println("ERROR STATE (red)");
#endif
      set_color_rgb(1023, 0, 0);
      break;
    }
    case STATE_WARN:
    {
#ifdef VERBOSE
      Serial.println("WARNING STATE (R+.5G)");
#endif
      set_color_rgb(1023, 512, 0);
      break;
    }
    case STATE_CRITICAL:
    {
#ifdef VERBOSE
      Serial.println("CRITICAL STATE (violet)");
#endif
      set_color_rgb(0, 1023, 1023);
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
    case STATE_STANDBY:
    {
      set_color_rgb(0, 0, 0);
      break;
    }
  }
}

void isr_pir_change()
{
  if (!pir_state && (sinceStart - last_pir_trigered > DELAY_MIN_MS_ENTRE_MOVS))
  {
    pir_state = HIGH;
    flag_publish_pir = HIGH;
  }
  last_pir_trigered = sinceStart;
}

void isr_vibro_change()
{
  if (!vibro_state && (sinceStart - last_vibro_trigered > DELAY_MIN_MS_ENTRE_VIBRO_SENSOR))
  {
    vibro_state = HIGH;
    flag_publish_vibro = HIGH;
  }
  last_vibro_trigered = sinceStart;
}

#ifdef PIN_LIGHT_SENSOR_DIGITAL
void isr_light_sensor_change()
{
  if (sinceStart - last_light_trigered > DELAY_MIN_MS_ENTRE_LIGHT_SENSOR)
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
  float light_percentage;

  light_percentage = round(100. * (1023 - analogRead(PIN_LIGHT_SENSOR_ANALOG)) /  10.23) / 100.;
//#ifdef VERBOSE
//  Serial.print("LIGHT: ");
//  Serial.print(light_percentage);
//  Serial.println(" %");
//#endif
  return light_percentage;
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
#ifdef VERBOSE
      Serial.print("Temp: " + String(temp) + " ^C, ");
#endif
    }
    // Get humidity event and print its value.
    dht.humidity().getEvent(&event);
    if (!isnan(event.relative_humidity))
    {
      humid = event.relative_humidity;
#ifdef VERBOSE
      Serial.println("Humidity: " + String(humid) + " %");
#endif
    }

    if ((temp == -999) || (humid == -999))
    {
      sensor_t sensor;
#ifdef VERBOSE
      Serial.println("ERROR! " + String(temp) + " / " + String(humid));
#endif
      dht.begin();
      dht.temperature().getSensor(&sensor);
      last_sensor_error = sinceStart;
      error_counter_dht += 1;
      *sample_ok = false;
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

#ifdef DHTPIN
void calc_sensor_stats(std::list<double> *samples, std::list<double> *history)
{
  int count = 0;
  double tempsum = 0;
  double tempaverage;

  if(samples->size() > 0)
  {
    for(std::list<double>::iterator sensiter = samples->begin(); sensiter != samples->end(); sensiter++)
    {
      count++;
      tempsum += *sensiter;
    }
    tempaverage = tempsum / count;

    //Add the new data to the history.
    history->push_front(tempaverage);
    if(history->size() > SENSOR_HISTORY_RECORDS)
    {
      history->pop_back();
    }
  }
  samples->clear();
}
#endif

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
  last_dht22_post = 15000;            // Init value to wait some time before the 1st publish.
  last_light_post = 15000;            // Init value to wait some time before the 1st publish.
  flag_publish_light = HIGH;
}

void setup_leds()
{
#ifdef LED_BLUE_PIR
  pinMode(LED_BLUE_PIR, OUTPUT);
#endif
#ifdef LED_YELLOW_VIBRO
  pinMode(LED_YELLOW_VIBRO, OUTPUT);
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
void setup_temp_sensor()
{
  dht.begin();
  sensor_t sensor;
  dht.temperature().getSensor(&sensor);
#ifdef VERBOSE
  Serial.println("------------------------------------");
  Serial.println("Temperature");
  Serial.print  ("Sensor:       "); Serial.println(sensor.name);
  Serial.print  ("Driver Ver:   "); Serial.println(sensor.version);
  Serial.print  ("Unique ID:    "); Serial.println(sensor.sensor_id);
  Serial.print  ("Max Value:    "); Serial.print(sensor.max_value); Serial.println(" *C");
  Serial.print  ("Min Value:    "); Serial.print(sensor.min_value); Serial.println(" *C");
  Serial.print  ("Resolution:   "); Serial.print(sensor.resolution); Serial.println(" *C");
  Serial.println("------------------------------------");
#endif
  dht.humidity().getSensor(&sensor);
  // Print humidity sensor details.
  dht.humidity().getSensor(&sensor);
#ifdef VERBOSE
  Serial.println("------------------------------------");
  Serial.println("Humidity");
  Serial.print  ("Sensor:       "); Serial.println(sensor.name);
  Serial.print  ("Driver Ver:   "); Serial.println(sensor.version);
  Serial.print  ("Unique ID:    "); Serial.println(sensor.sensor_id);
  Serial.print  ("Max Value:    "); Serial.print(sensor.max_value); Serial.println("%");
  Serial.print  ("Min Value:    "); Serial.print(sensor.min_value); Serial.println("%");
  Serial.print  ("Resolution:   "); Serial.print(sensor.resolution); Serial.println("%");
  Serial.println("------------------------------------");
#endif
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
  //char *pass = (char*) malloc(strlen(WiFiPSK));
  //strcpy(pass, WiFiPSK);

  //WiFi.mode(WIFI_STA);
  //WiFi.begin(WiFiSSID, pass);
  WiFi.begin((char *)WiFiSSID, (const char *)WiFiPSK);


#ifdef VERBOSE
  Serial.print("Attempting to connect to WPA SSID: ");
  Serial.print(WiFiSSID);
#endif

  while (WiFi.status() != WL_CONNECTED)
  {
    set_color_rgb(1023, 0, 1023);
    //Delay until connected.
    delay(DELAY_MS_BETWEEN_RETRIES);
#ifdef VERBOSE
    Serial.print (".");
#endif
  }
  set_color_rgb(0, 1023, 0);
#ifdef VERBOSE
  Serial.println("You're connected to the network");
  printWifiStatus();
#endif

  //Connect to the mqtt server
  client.setServer(MQTT_SERVER, MQTT_PORT);
  set_state(STATE_STANDBY);
}

#ifdef VERBOSE
void printWifiStatus()
{
  // print the SSID of the network you're attached to
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());

  // print your WiFi shield's IP address
  IPAddress ip = WiFi.localIP();
  Serial.print("IP Address: ");
  Serial.println(ip);

  // print the received signal strength
  long rssi = WiFi.RSSI();
  Serial.print("Signal strength (RSSI):");
  Serial.print(rssi);
  Serial.println(" dBm");
}
#endif
