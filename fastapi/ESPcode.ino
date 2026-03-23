#include <WiFi.h>
#include <HTTPClient.h>

#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>
#include "MAX30105.h"
#include "heartRate.h"
#include <DHT.h>
#include <esp_task_wdt.h>

MAX30105 particleSensor;

#define DHTTYPE DHT11
#define dhtsensepin 16
DHT dht(dhtsensepin,DHTTYPE);

float humidity;
float ambTEMPc;

// Pin definitions
int buttonPin = 35;
int buttonVal;
#define ECG_PIN 34                        // Analog pin connected to ECG output
#define DS18B20_PIN 23                    // Digital pin connected to DS18B20 data pin


OneWire oneWire(DS18B20_PIN);             // Setup OneWire and DallasTemperature instances for DS18B20
DallasTemperature sensors(&oneWire);

double avered    = 0; 
double aveir     = 0;
double sumirrms  = 0;
double sumredrms = 0;
int    i         = 0;
int    Num       = 100;  
int    Temperature;
int    temp;
float  ESpO2;            
double FSpO2     = 0.7;  
double frate     = 0.95; 
#define TIMETOBOOT 3000  
#define SCALE      88.0 
#define SAMPLING   100 
#define FINGER_ON  30000 
#define USEFIFO



const byte RATE_SIZE = 4; 
byte rates[RATE_SIZE]; 
byte rateSpot = 0;
long lastBeat = 0; 

float beatsPerMinute;
int beatAvg;

// Wi-Fi Credentials
const char* ssid = "test";
const char* password = "test@123";

// Backend API URL (actual API endpoint)
const char* serverUrl = "http://192.168.0.101:8000/update_patient_info";
const char* serverUrlECG = "http://192.168.0.101:8000/update_ECG";
//const char* serverUrl = "http://192.168.6.231:8000/update_patient_info";

//const char* serverUrl = "http://192.168.29.99:3000/send_data";

void setup() {

  Serial.begin(115200);
  pinMode(buttonPin,INPUT);
  esp_task_wdt_init(30,true);
  esp_task_wdt_add(NULL);
  
  WiFi.begin(ssid, password);
    
    Serial.print("Connecting to Wi-Fi...");
    while (WiFi.status() != WL_CONNECTED) {
        delay(1000);
        Serial.print(".");
    }
    Serial.println("\nConnected to Wi-Fi!");
  Serial.setDebugOutput(true);
  Serial.println();

  Serial.println("Running...");
  delay(3000);

  dht.begin();         // Start temperature sensor
  sensors.begin();

  while (!particleSensor.begin(Wire, I2C_SPEED_FAST)) //Use default I2C port, 400kHz speed
  {
    Serial.println("MAX30102 was not found. Please check wiring/power/solder jumper at MH-ET LIVE MAX30102 board. ");
    //while (1);
  }

  byte ledBrightness = 0x7F;
  byte sampleAverage = 4; 
  byte ledMode       = 2;
  int sampleRate     = 200; 
  int pulseWidth     = 411;
  int adcRange       = 16384; 
  
  // Set up the wanted parameters
  particleSensor.setup(ledBrightness, sampleAverage, ledMode, sampleRate, pulseWidth, adcRange); 
  particleSensor.enableDIETEMPRDY();
  Serial.println("Starting ECG and Temperature Monitoring...");
}

void sendECGDataToBackend(String ecgData) {
    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        http.begin(serverUrlECG);
        http.addHeader("Content-Type", "application/json");

        String jsonPayload = "{";
        jsonPayload += "\"ecg\": \"" + ecgData + "\"";
        jsonPayload += "}";

        Serial.println("Sending ECG data...");
        Serial.println(jsonPayload);
        int httpResponseCode = http.POST(jsonPayload);

        if (httpResponseCode > 0) {
            Serial.println("ECG Data sent successfully!");
        } else {
            Serial.print("Error sending ECG data: ");
            Serial.println(httpResponseCode);
        }

        http.end();
    } else {
        Serial.println("Wi-Fi Disconnected. Reconnecting...");
        WiFi.begin(ssid, password);
    }
}

void sendDataToBackend(float bodyTemp, float humidity, float roomTemp, float spo2, float bpm, float avgBpm) {
    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        http.begin(serverUrl);
        http.addHeader("Content-Type", "application/json");

        // Create JSON payload
        String jsonPayload = "{";
        jsonPayload += "\"bodyTemp\": " + String(bodyTemp) + ",";
        jsonPayload += "\"humidity\": " + String(humidity) + ",";
        jsonPayload += "\"roomTemp\": " + String(roomTemp) + ",";
        jsonPayload += "\"spo2\": " + String(spo2) + ",";
        jsonPayload += "\"bpm\": " + String(bpm) + ",";
        jsonPayload += "\"avgBpm\": " + String(avgBpm);
        jsonPayload += "}";

        Serial.println("Sending data: " + jsonPayload);

        // Send HTTP POST request
        int httpResponseCode = http.POST(jsonPayload);
        
        if (httpResponseCode > 0) {
            Serial.println("Data sent successfully!");
        } else {
            Serial.print("Error sending data: ");
            Serial.println(httpResponseCode);
        }

        http.end();  // Free resources
    } else {
        Serial.println("Wi-Fi Disconnected. Reconnecting...");
        WiFi.begin(ssid, password);
    }
}

void loop() {

  buttonVal = digitalRead(buttonPin);
  
  // If button is pressed, collect and send ECG data only
    if (buttonVal == 1) {
        Serial.println("Button Pressed - Collecting ECG Data...");
        String ecgData = "";

        for (int i = 0; i < 500; i++) {
            int ecgValue = analogRead(ECG_PIN);
            ecgData += String(ecgValue) + ",";
            delay(20);

            esp_task_wdt_reset();
        }
        Serial.println("ECG Data Sent. Resuming Normal Operation...");
        // Serial.println(typeof(ecgData));
        Serial.println(ecgData);

        sendECGDataToBackend(ecgData);
        Serial.println("ECG Data Sent. Resuming Normal Operation...");
        delay(2000);
        return;  // Skip sending other sensor data
    }
  

  // --- Read Temperature Data ---
  sensors.requestTemperatures();             // Request temperature from DS18B20
  float temperatureC = sensors.getTempCByIndex(0); // Read temperature in Celsius

  humidity = dht.readHumidity();
  ambTEMPc = dht.readTemperature();
  
  Serial.print("Body Temperature (°C): ");
  Serial.print(temperatureC);

  Serial.print(" , Humidity : ");
  Serial.print(humidity);

  Serial.print(" , Room Temperature (°C): ");
  Serial.println(ambTEMPc);


  

  uint32_t ir, red, green;
  double fred, fir;
  double SpO2 = 0; 
  
#ifdef USEFIFO
  particleSensor.check();

  while (particleSensor.available()) {
#ifdef MAX30105
   red = particleSensor.getFIFORed(); 
   ir  = particleSensor.getFIFOIR();  
#else
   red = particleSensor.getFIFOIR(); 
   ir  = particleSensor.getFIFORed(); 
#endif
   
    i++;
    fred = (double)red;
    fir  = (double)ir;
    avered = avered * frate + (double)red * (1.0 - frate); 
    aveir = aveir * frate + (double)ir * (1.0 - frate); 
    sumredrms += (fred - avered) * (fred - avered); 
    sumirrms += (fir - aveir) * (fir - aveir);

  long irValue = particleSensor.getIR();

  if (checkForBeat(irValue) == true)
  {
    long delta = millis() - lastBeat;
    lastBeat = millis();

    beatsPerMinute = 60 / (delta / 1000.0);

    if (beatsPerMinute < 255 && beatsPerMinute > 20)
    {
      rates[rateSpot++] = (byte)beatsPerMinute; 
      rateSpot %= RATE_SIZE; 

      
      beatAvg = 0;
      for (byte x = 0 ; x < RATE_SIZE ; x++)
        beatAvg += rates[x];
      beatAvg /= RATE_SIZE;
    }
  }
    if ((i % SAMPLING) == 0) {
      if ( millis() > TIMETOBOOT) {
        float ir_forGraph = (2.0 * fir - aveir) / aveir * SCALE;
        float red_forGraph = (2.0 * fred - avered) / avered * SCALE;
        if ( ir_forGraph > 100.0) ir_forGraph = 100.0;
        if ( ir_forGraph < 80.0) ir_forGraph = 80.0;
        if ( red_forGraph > 100.0 ) red_forGraph = 100.0;
        if ( red_forGraph < 80.0 ) red_forGraph = 80.0;
        float temperature = particleSensor.readTemperatureF();
        
        if (ir < FINGER_ON){ // no finger on the sensor
           Serial.println("No finger detected");
           break;
        }
        if(ir > FINGER_ON){
           Serial.print("Oxygen % = ");
           Serial.print(ESpO2);
           Serial.print("%");
           Serial.print(", BPM=");
           Serial.print(beatsPerMinute);
           Serial.print(", Avg BPM=");
          Serial.println(beatAvg);
        }
      }
    }
    if ((i % Num) == 0) {
      double R = (sqrt(sumredrms) / avered) / (sqrt(sumirrms) / aveir);
      SpO2 = -23.3 * (R - 0.4) + 100; 
      ESpO2 = FSpO2 * ESpO2 + (1.0 - FSpO2) * SpO2;
      sumredrms = 0.0; sumirrms = 0.0; i = 0;
      break;
    }
    particleSensor.nextSample(); 
  }
#endif

  //sendDataToBackend(temperatureC, humidity, ambTEMPc, SpO2, beatsPerMinute, beatAvg);
  sendDataToBackend(temperatureC, 27, 27, SpO2, beatsPerMinute, beatAvg);
  esp_task_wdt_reset();
  delay(5000);
}
