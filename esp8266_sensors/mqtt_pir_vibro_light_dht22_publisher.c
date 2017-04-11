/*
# *Detector de movimiento, vibración, luz, temperatura y humedad relativa*

*Detector inalámbrico de movimiento, vibración, luz, temperatura y humedad relativa* sobre plataforma ESP8266,
que comunica los valores detectados a un servidor MQTT (like `mosquitto`). Útil para colocarlo en recintos alejados
pero con acceso a wifi en integraciones de domótica.

De funcionamiento muy sencillo, se conecta a la wifi local, y de ahí al servidor MQTT, donde publica los valores
de temperatura, humedad y % de iluminación cada `MQTT_POSTINTERVAL_SEC` segundos (default=40s).
Los sensores binarios (movimiento y vibración) se tratan mediante interrupciones (vs polling)
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
#define mqtt_extra_topic                    "sensor/extra_"
#define mqtt_light_topic                    "sensor/light_"
#define mqtt_light_analog_topic             "sensor/light_analog_"
```

Al nombre del `topic` se le añade la MAC de la Wifi del ESP8266 (ej: `sensor/light_analog_abcdef012345`), de forma
que los identificadores son únicos para cada chip, por lo que, si utilizas varios de estos detectores, no hay
necesidad de cambiar el programa para cada uno.

### Changelog ESP8266 MQTT Publisher

- v1.0: PIR+Vibration+Light(AO+DO)+DHT22 sensors publishing values to a local mosquitto server.

*/

//**********************************
//** Librerías *********************
//**********************************
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <elapsedMillis.h>
#include <list>
#include <Adafruit_Sensor.h>  // - Adafruit Unified Sensor Library: https://github.com/adafruit/Adafruit_Sensor
#include <DHT.h>              // - DHT Sensor Library: https://github.com/adafruit/DHT-sensor-library
#include <DHT_U.h>

//**********************************
//** USER SETTINGS *****************
//**********************************

//MQTT settings
#define MQTT_SERVER                         [REDACTED_MQTT_SERVER_IP]
#define MQTT_PORT                           [REDACTED_MQTT_SERVER_PORT]
#define MQTT_USER                           [REDACTED_MQTT_USER]
#define MQTT_PASSWORD                       [REDACTED_MQTT_PASSWD]

#define MQTT_POSTINTERVAL_SEC               40 //Seconds
#define mqtt_temp_topic                     "sensor/temp_"
#define mqtt_humid_topic                    "sensor/hum_"
#define mqtt_movement_topic                 "sensor/pir_"
#define mqtt_extra_topic                    "sensor/extra_"
#define mqtt_light_topic                    "sensor/light_"
#define mqtt_light_analog_topic             "sensor/light_analog_"

//WiFi Settings
#define WiFiSSID                            [REDACTED_WIFI_SSID]
#define WiFiPSK                             [REDACTED_WIFI_PASSWORD]

//**********************************
//** PINOUT ************************
//**********************************

#define DHTPIN                              2      //D4 (DHT sensor)

//#define LED_BLUE_PIR                        14     //D5
//#define LED_YELLOW_VIBRO                    0      //D3
#define LED_RGB_RED                         12     //D6
#define LED_RGB_GREEN                       13     //D7
#define LED_RGB_BLUE                        15     //D8

#define PIN_PIR                             5      //D1
#define PIN_EXTRA_SENSOR                    4      //D2

#define PIN_LIGHT_SENSOR_DIGITAL            14     //D5
#define PIN_LIGHT_SENSOR_ANALOG             A0     //A0

//**********************************
//** Configuración *****************
//**********************************
#define VERBOSE

#define DELAY_MIN_MS_ENTRE_MOVS             2500
#define DELAY_MIN_MS_ENTRE_EXTRA_SENSOR     3000
#define DELTA_MS_TO_TURN_OFF_BOOLEAN        3000
#define PERSISTENT_STATE_MS_UNTIL_STANDBY   2000

//**********************************
//** Variables *********************
//**********************************

WiFiClient espClient;           //For the MQTT client
PubSubClient client(espClient); //MQTT client
char MAC_char[18];    //MAC address in ascii

// DHT22 sensor settings.
#define DHTTYPE DHT22     // DHT 22 (AM2302)
DHT_Unified dht(DHTPIN, DHTTYPE);

//Settings for recording samples
#define RESULTS_SAMPLE_RATE  10        //The number of seconds between samples
#define SENSOR_HISTORY_RECORDS 15     //The number of records to keep
std::list<double> tempSamples;   //Collected results per interval
std::list<double> humidSamples;  //Collected results per interval
std::list<double> tempHistory;   //History over time.
std::list<double> humidHistory;  //History over time.

int current_sensor_state;
int last_sensor_error = 0;
int last_sensor_ok = 0;
int last_result_time = 0;  //The last time a sample was taken.
int lastposttime = 0;      //The last time a MQTT topic was posted.

// Estados (para el output LED RGB)
#define STATE_ERROR            1
#define STATE_WARN             2
#define STATE_OK_MEASURE       3
#define STATE_OK_PUBLISH       4
#define STATE_INIT             5
#define STATE_STANDBY          7
#define STATE_CRITICAL         8

// Contadores de tiempo
elapsedMillis sinceStart;
int last_state_change = 0;

// PIR & extra sensors data for interrupts
volatile int last_pir_trigered = 0;
volatile int last_extra_trigered = 0;
volatile int last_light_trigered = 0;
volatile bool pir_state = LOW;
volatile bool extra_sensor_state = LOW;
volatile bool light_state = LOW;
volatile bool flag_publish_pir = LOW;
volatile bool flag_publish_extra = LOW;
volatile bool flag_publish_light = LOW;

//**********************************
//** SETUP
//**********************************
void setup() {
  uint8_t MAC_array[6];

  current_sensor_state = STATE_INIT;
  Serial.begin(9600);
  sinceStart = 0;
  setup_leds();
  set_led_state();

  connectWiFi();

  setup_temp_sensor();
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
  current_sensor_state = STATE_CRITICAL;
  set_led_state();
}

//**********************************
//** LOOP
//**********************************

void loop()
{
  bool sensor_ok = false;
  bool sensed_data = false;

  //Reconnect if disconnected.
  if(WiFi.status() != WL_CONNECTED) {
    current_sensor_state = STATE_ERROR;
    set_led_state();
    connectWiFi();
  }

  //Check the MQTT connection and process it
  while (!client.connected()) {
    current_sensor_state = STATE_ERROR;
    set_led_state();
    client.connect("ESP8266Client", MQTT_USER, MQTT_PASSWORD);
    delay(250);
  }
  client.loop();

  // Extra binary sensor to off after a delay:
  if (extra_sensor_state && (sinceStart - last_extra_trigered > DELTA_MS_TO_TURN_OFF_BOOLEAN))
  {
    extra_sensor_state = LOW;
    flag_publish_extra = HIGH;
  }

  // Update PIR state:
  if (flag_publish_pir)
  {
#ifdef LED_BLUE_PIR
    digitalWrite(LED_BLUE_PIR, pir_state);
#endif
    publish_mqtt_binary_sensor("MOVEMENT", "MOVEMENT OFF",
                               pir_state, (mqtt_movement_topic+String(MAC_char)).c_str());
    flag_publish_pir = LOW;
  }

  // Update Extra sensor state:
  if (flag_publish_extra)
  {
#ifdef LED_YELLOW_VIBRO
    digitalWrite(LED_YELLOW_VIBRO, extra_sensor_state);
#endif
    publish_mqtt_binary_sensor("VIBRATION", "VIBRATION OFF",
                               extra_sensor_state, (mqtt_extra_topic+String(MAC_char)).c_str());
    flag_publish_extra = LOW;
  }

  // Update LIGHT state:
  if (flag_publish_light)
  {
    publish_mqtt_binary_sensor("LIGHT", "LIGHT OFF",
                               light_state, (mqtt_light_topic+String(MAC_char)).c_str());
    flag_publish_light = LOW;
  }

  //Collect the sensor data
  if(millis() - last_result_time > RESULTS_SAMPLE_RATE * 1000)
  {
    sensed_data = true;
    sensor_ok = get_dht22_sensor_data();
    last_result_time = millis();
  }

  //post MQTT data every MQTT_POSTINTERVAL_SEC seconds and on bootup
  if (millis() - lastposttime > MQTT_POSTINTERVAL_SEC * 1000 || lastposttime == 0)
  {
    bool publishing = false;
    float light_percentage;

    calcSensorStats();
    light_percentage = read_analog_light_percentage();
    publish_mqtt_data("LIGHT", (mqtt_light_analog_topic+String(MAC_char)).c_str(), String(light_percentage).c_str(), false);
    publish_mqtt_binary_sensor("LIGHT ON", "LIGHT OFF", !digitalRead(PIN_LIGHT_SENSOR_DIGITAL), (mqtt_light_topic+String(MAC_char)).c_str());

    if(tempHistory.size() > 0)
    {
      publishing = true;
      publish_mqtt_data("TEMP", (mqtt_temp_topic+String(MAC_char)).c_str(), String(tempHistory.front()).c_str(), false);
    }

    if(humidHistory.size() > 0)
    {
      publishing = true;
      publish_mqtt_data("HUMID", (mqtt_humid_topic+String(MAC_char)).c_str(), String(humidHistory.front()).c_str(), false);
    }

    if (publishing)
    {
      lastposttime = millis();
      current_sensor_state = STATE_OK_PUBLISH;
      set_led_state();
    }
  }
  else if (sensed_data && sensor_ok)
  {
    current_sensor_state = STATE_OK_MEASURE;
    set_led_state();
  }
  else if (sensed_data)
  {
    current_sensor_state = STATE_WARN;
    set_led_state();
  }

  if ((sinceStart - last_state_change > PERSISTENT_STATE_MS_UNTIL_STANDBY)
      && current_sensor_state != STATE_STANDBY && !i_state_critical())
  {
    current_sensor_state = STATE_STANDBY;
    set_led_state();
  }
}


//**********************************
//** METHODS
//**********************************

void publish_mqtt_data(const char* type_publish, const char* topic, const char* payload, boolean retained)
{
#ifdef VERBOSE
  Serial.print("PUBLISH ");
  Serial.print(type_publish);
  Serial.print(": topic=");
  Serial.print(topic);
  Serial.print(" -> ");
  Serial.println(payload);
#endif
  client.publish(topic, payload, retained);
}

void publish_mqtt_binary_sensor(const char* name_on, const char* name_off,
                                bool state, const char* topic)
{
  if (state)
    publish_mqtt_data(name_on, topic, "on", false);
  else
    publish_mqtt_data(name_off, topic, "off", false);
}

#ifdef VERBOSE
void test_led_rgb()
{
  uint16_t i;
  int16_t j;

  Serial.println("Red 1/2");
  set_color_rgb(512, 0, 0);
  delay(500);
  Serial.println("Red");
  set_color_rgb(1023, 0, 0);
  delay(500);

  Serial.println("Green 1/2");
  set_color_rgb(0, 512, 0);
  delay(500);
  Serial.println("Green");
  set_color_rgb(0, 1023, 0);
  delay(500);

  Serial.println("Blue 1/2");
  set_color_rgb(0, 0, 512);
  delay(500);
  Serial.println("Blue");
  set_color_rgb(0, 0, 1023);
  delay(500);

  for (i = 0; i < 1024; i++)
  {
    for (j = 1023; j >= 0; j--)
    {
      Serial.print("RGB = ");
      Serial.print(i);
      Serial.print(", ");
      Serial.print(j);
      Serial.println(", 0");
      set_color_rgb(i, (uint16_t)j, 0);
      delay(200);
      j -= 127;
    }
    i += 127;
  }

  for (i = 0; i < 1024; i++)
  {
    for (j = 1023; j >= 0; j--)
    {
      Serial.print("RGB = ");
      Serial.print(i);
      Serial.print(", 0, ");
      Serial.println(j);
      set_color_rgb(i, 0, (uint16_t)j);
      delay(200);
      j -= 127;
    }
    i += 127;
  }

  for (i = 0; i < 1024; i++)
  {
    for (j = 1023; j >= 0; j--)
    {
      Serial.print("RGB = 0, ");
      Serial.print(i);
      Serial.print(", ");
      Serial.println(j);
      set_color_rgb(0, i, (uint16_t)j);
      delay(200);
      j -= 127;
    }
    i += 127;
  }

  Serial.println("FIN . GREEN 5s");
  set_color_rgb(0, 1023, 0);
  delay(5000);

//  set_color_rgb(0, 512, 0);
//  delay(500);
//  set_color_rgb(0, 1023, 0);
//  delay(500);
}
#endif

void setup_leds()
{
#ifdef LED_BLUE_PIR
  pinMode(LED_BLUE_PIR, OUTPUT);
#endif
#ifdef LED_YELLOW_VIBRO
  pinMode(LED_YELLOW_VIBRO, OUTPUT);
#endif

  pinMode(LED_RGB_BLUE, OUTPUT);
  pinMode(LED_RGB_GREEN, OUTPUT);
  pinMode(LED_RGB_RED, OUTPUT);

//#ifdef VERBOSE
  //test_led_rgb();
//#endif
}

void set_color_rgb(uint16_t red, uint16_t green, uint16_t blue)
{
  analogWrite(LED_RGB_RED, red);
  analogWrite(LED_RGB_GREEN, green);
  analogWrite(LED_RGB_BLUE, blue);
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

void set_led_state()
{
  last_state_change = sinceStart;
  switch (current_sensor_state)
  {
    case STATE_INIT:
    {
      set_color_rgb(1023, 1023, 1023);
      break;
    }
    case STATE_ERROR:
    {
      Serial.println("ERROR R");
      set_color_rgb(1023, 0, 0);
      break;
    }
    case STATE_WARN:
    {
      Serial.println("WARN R+.5G");
      set_color_rgb(1023, 512, 0);
      break;
    }
    case STATE_CRITICAL:
    {
      Serial.println("CRITICAL G+B");
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
//    case STATE_WEBACCESS:
//    {
//      Serial.println("WEB .5R,.5G");
//      set_color_rgb(512, 512, 0);
//      break;
//    }
    case STATE_STANDBY:
    {
      set_color_rgb(0, 0, 0);
      break;
    }
  }
}

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

void setup_boolean_sensors()
{
  pinMode(PIN_PIR, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_PIR), isr_pir_change, CHANGE);

  pinMode(PIN_EXTRA_SENSOR, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_EXTRA_SENSOR), isr_extra_sensor_change, CHANGE);

  pinMode(PIN_LIGHT_SENSOR_DIGITAL, INPUT);
  //attachInterrupt(digitalPinToInterrupt(PIN_LIGHT_SENSOR_DIGITAL), isr_light_sensor_change, CHANGE);

  pinMode(PIN_LIGHT_SENSOR_ANALOG, INPUT);
}

void isr_pir_change()
{
  int new_pir_state = digitalRead(PIN_PIR);

  if (new_pir_state && (sinceStart - last_pir_trigered > DELAY_MIN_MS_ENTRE_MOVS))
  {
    if (new_pir_state != pir_state)
    {
      pir_state = new_pir_state;
      flag_publish_pir = HIGH;
#ifdef VERBOSE
      Serial.println("* Movimiento detectado, last=" + String(sinceStart - last_pir_trigered));
#endif
      last_pir_trigered = sinceStart;
    }
  }
  else if (!new_pir_state)
  {
    if (new_pir_state != pir_state)
    {
      pir_state = new_pir_state;
      flag_publish_pir = HIGH;
#ifdef VERBOSE
      Serial.println("* Movimiento detectado OFF, last=" + String(sinceStart - last_pir_trigered));
#endif
//      last_pir_trigered = sinceStart;
    }
  }
  else
  {
#ifdef VERBOSE
    Serial.println("Movimiento detectado ignorado");
#endif
    last_pir_trigered = sinceStart;
  }
}

void isr_extra_sensor_change()
{
  if (sinceStart - last_extra_trigered > DELAY_MIN_MS_ENTRE_EXTRA_SENSOR)
  {
    //int new_extra_sensor_state = digitalRead(PIN_EXTRA_SENSOR);
    if (!extra_sensor_state)
    {
      extra_sensor_state = HIGH;
      flag_publish_extra = HIGH;
//      Serial.println("* Vibracion detectada, last=" + String(sinceStart - last_extra_trigered));
    }
  }
  last_extra_trigered = sinceStart;
}

float read_analog_light_percentage()
{
  float light_percentage;

  light_percentage = round(100. * (1023 - analogRead(PIN_LIGHT_SENSOR_ANALOG)) /  10.23) / 100.;

#ifdef VERBOSE
  Serial.print("LIGHT: ");
  Serial.print(light_percentage);
  Serial.println(" %");
#endif
  return light_percentage;
}

bool get_dht22_sensor_data()
{
  double temp = -999;
  double humid = -999;
  sensors_event_t event;
  boolean error = true;

  //Collect the temperature from a sensor.
  dht.temperature().getEvent(&event);
  if (!isnan(event.temperature))
  {
    temp = event.temperature;
#ifdef VERBOSE
    Serial.print("Temp: " + String(temp) + " ^C, ");
#endif
    error = false;
  }
  // Get humidity event and print its value.
  dht.humidity().getEvent(&event);
  if (!isnan(event.relative_humidity))
  {
    humid = event.relative_humidity;
#ifdef VERBOSE
    Serial.println("Humidity: " + String(humid) + " %");
#endif
    error = false;
  }

  if (error)
  {
    sensor_t sensor;
#ifdef VERBOSE
    Serial.println("ERROR! " + String(temp) + " / " + String(humid));
#endif
    dht.begin();
//    dht.temperature().getSensor(&sensor);
    last_sensor_error = sinceStart;
    return false;
  }
  else
  {
    //Make sure a valid temperature was sampled
    if(temp != -999)
    {
      tempSamples.push_front(temp);
      last_sensor_ok = sinceStart;
    }
    if(humid != -999)
    {
      humidSamples.push_front(humid);
      last_sensor_ok = sinceStart;
    }
  }

  return true;
}

void calcSensorStats()
{
  int count = 0;
  double tempsum = 0;
  double humidsum = 0;
  double tempaverage, humidaverage;

  if(tempSamples.size() > 0) {
    for(std::list<double>::iterator sensiter = tempSamples.begin(); sensiter != tempSamples.end(); sensiter++) {
      count++;
      tempsum += *sensiter;
    }
    tempaverage = tempsum / count;

    //Add the new data to the history.
    tempHistory.push_front(tempaverage);
    if(tempHistory.size() > SENSOR_HISTORY_RECORDS) {
      tempHistory.pop_back();
    }
  }

  if(humidSamples.size() > 0) {
    count = 0;
    //Get totals and averages
    for(std::list<double>::iterator sensiter = humidSamples.begin(); sensiter != humidSamples.end(); sensiter++) {
      count++;
      humidsum += *sensiter;
    }
    humidaverage = humidsum / count;

    //Add the new data to the history.
    humidHistory.push_front(humidaverage);
    if(humidHistory.size() > SENSOR_HISTORY_RECORDS) {
      humidHistory.pop_back();
    }
  }

  tempSamples.clear();
  humidSamples.clear();
}

void connectWiFi()
{
  WiFi.mode(WIFI_STA);
  WiFi.begin(WiFiSSID, WiFiPSK);

#ifdef VERBOSE
  Serial.print("Attempting to connect to WPA SSID: ");
  Serial.print(WiFiSSID);
#endif

  while (WiFi.status() != WL_CONNECTED)
  {
    set_color_rgb(1023, 0, 1023);
    //Delay until connected.
    delay(250);
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

  //Begin listening to clients connecting to the "webserver".
  //  server.begin(); //Listen for clients connecting to port 80

  current_sensor_state = STATE_STANDBY;
  set_led_state();
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
