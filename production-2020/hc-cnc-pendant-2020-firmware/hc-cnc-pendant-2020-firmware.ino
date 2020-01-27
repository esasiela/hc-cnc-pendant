/*
   hc-cnc-pendant-firmware

   This is the Arduino Nano firmware for the Hedge Court CNC Pendant (v3, 2020)

   Pin Usage:

   3,5,6,9 - LED indicators (PWM output pins, only used as digital but future proofing)
   10,11,12 - Serial In register for 16 pushbuttons

*/

#include <EEPROM.h>
#include <HC_BouncyButton.h>

const int SERIAL_DEBUG = 0;


/***
   PIN definitions
*/

const int PIN_BTN_DATA = 10;
const int PIN_BTN_CLOCK = 12;
const int PIN_BTN_LATCH = 11;

const int PIN_LED_NOTIFY = 3;
const int PIN_LED_100 = 9;
const int PIN_LED_010 = 6;
const int PIN_LED_001 = 5;

// host will map JOG_SIZE_n to proper measurement size
const int JOG_SIZE_100 = 0;
const int JOG_SIZE_010 = 1;
const int JOG_SIZE_001 = 2;

// G-Code spec, 20=imperial, 21=metric
const int JOG_UNIT_INCH = 20;
const int JOG_UNIT_MM = 21;

// hc-pendant-2020 spec for data msg start (debugging strings DONT begin with 0x03)
const uint8_t MSG_START_BYTE = 0x03;

const uint8_t NOTIFY_IDLE = 0x01;
const uint8_t NOTIFY_ARMED = 0x02;
const uint8_t NOTIFY_FIRED = 0x03;

// the host app will send me the true notify state once I connect serial
uint8_t notifyState = NOTIFY_IDLE;

unsigned long lastNotifyBlinkMillis;
const int NOTIFY_BLINK_DELAY_MILLIS = 250;

// true on any change (press or release)
boolean isBtnRegisterChange = false;
// only true for press, not for release
boolean isBtnButtonPress = false;

uint16_t bouncingCurrentBtnRegister;
uint16_t bouncingPreviousBtnRegister;
uint16_t btnRegister;
uint16_t previousBtnRegister;

unsigned long lastDebounceTime;
const int DEBOUNCE_DELAY_MILLIS = 13;

// set the defaults to 10mm jog size
// hc-pendant-2020 does not offer any user interface to change from MM to inches, but we code it flexible anyways
byte jogSizeSelector = JOG_SIZE_100;
byte jogUnitSelector = JOG_UNIT_MM;


void updateUnitSelectorLED() {
  digitalWrite(PIN_LED_100, LOW);
  digitalWrite(PIN_LED_010, LOW);
  digitalWrite(PIN_LED_001, LOW);

  if (jogSizeSelector == JOG_SIZE_100) {
    digitalWrite(PIN_LED_100, HIGH);
  } else if (jogSizeSelector == JOG_SIZE_010) {
    digitalWrite(PIN_LED_010, HIGH);
  } else if (jogSizeSelector == JOG_SIZE_001) {
    digitalWrite(PIN_LED_001, HIGH);
  } else {
    Serial.println(F("invalid jog size selector is in the house, resetting to 10"));
    jogSizeSelector = JOG_SIZE_100;
    updateUnitSelectorLED();
  }
}

void setup() {

  Serial.begin(9600);
  delay(100);
  Serial.flush();
  Serial.println(F("HC CNC PENDANT 2020"));

  // button multiplexer
  pinMode(PIN_BTN_DATA, INPUT);
  pinMode(PIN_BTN_CLOCK, OUTPUT);
  pinMode(PIN_BTN_LATCH, OUTPUT);

  digitalWrite(PIN_BTN_LATCH, LOW);
  digitalWrite(PIN_BTN_CLOCK, HIGH);

  pinMode(PIN_LED_NOTIFY, OUTPUT);
  pinMode(PIN_LED_100, OUTPUT);
  pinMode(PIN_LED_010, OUTPUT);
  pinMode(PIN_LED_001, OUTPUT);

  digitalWrite(PIN_LED_NOTIFY, LOW);

  updateUnitSelectorLED();

}

void loop() {

  if (notifyState==NOTIFY_FIRED && (millis() - lastNotifyBlinkMillis) >= NOTIFY_BLINK_DELAY_MILLIS) {
    lastNotifyBlinkMillis = millis();
    digitalWrite(PIN_LED_NOTIFY, !digitalRead(PIN_LED_NOTIFY));
  }

  /***
     Check for client messages incoming on serial port.
     Pendant app will send Jog Size and Job Notify data.
     Client messages are 3 bytes:
     byte 0 - msg start, 0x03
     byte 1 - msg type - 0x01=jog_size, 0x02=notify
     byte 2 - data:
        jog_size - 13=10.0, 14=1.00, 15=0.10
        notify - IDLE=0x01, ARMED=0x02, FIRED=0x03
  */
  if (Serial.available() >= 3) {
    uint8_t start_byte = Serial.read();
    uint8_t msg_type  = Serial.read();
    uint8_t msg_data = Serial.read();

    if (start_byte == 0x03) {
      if (SERIAL_DEBUG) {
        Serial.println(F("client msg with valid start byte"));
      }

      if (msg_type == 0x01) {
        if (SERIAL_DEBUG) {
          Serial.println(F("client msg - jog size"));
        }

        if (msg_data == 13) {
          jogSizeSelector = JOG_SIZE_100;
        } else if (msg_data == 14) {
          jogSizeSelector = JOG_SIZE_010;
        } else if (msg_data == 15) {
          jogSizeSelector = JOG_SIZE_001;
        }
        updateUnitSelectorLED();

      } else if (msg_type == 0x02) {
        if (SERIAL_DEBUG) {
          Serial.println(F("client msg - notify"));
        }

        notifyState = msg_data;

        if (notifyState == NOTIFY_IDLE) {
          digitalWrite(PIN_LED_NOTIFY, LOW);
        } else if (notifyState == NOTIFY_ARMED) {
          digitalWrite(PIN_LED_NOTIFY, HIGH);
        } else if (notifyState == NOTIFY_FIRED) {
          // start blinking
          lastNotifyBlinkMillis = millis();
          // presumably we were in ARMED (unless I use my fake Fire! button for testing),
          // so LED was already on, so blinking is best to start by going low
          digitalWrite(PIN_LED_NOTIFY, LOW);
        }
      }
    }
  }

  /***
     read the multiplexed buttons
  */

  // latch HIGH and delay, allowing us to provide the LOW transition to begin reading
  digitalWrite(PIN_BTN_LATCH, HIGH);
  digitalWrite(PIN_BTN_CLOCK, HIGH);
  delayMicroseconds(20);
  // latch LOW tells the multiplexer to latch the button states so we can begin reading
  digitalWrite(PIN_BTN_LATCH, LOW);

  isBtnRegisterChange = false;
  bouncingCurrentBtnRegister = shiftIn(PIN_BTN_DATA, PIN_BTN_CLOCK, LSBFIRST) << 8;
  bouncingCurrentBtnRegister = bouncingCurrentBtnRegister | shiftIn(PIN_BTN_DATA, PIN_BTN_CLOCK, LSBFIRST);

  if (bouncingCurrentBtnRegister != bouncingPreviousBtnRegister) {
    // something is bouncing
    lastDebounceTime = millis();
  }

  isBtnRegisterChange = bouncingCurrentBtnRegister != btnRegister;

  if ((millis() - lastDebounceTime) > DEBOUNCE_DELAY_MILLIS && isBtnRegisterChange) {
    // bouncing is done and there is a state change, make it live
    previousBtnRegister = btnRegister;
    btnRegister = bouncingCurrentBtnRegister;

    // determine if it is a PRESS, we dont care about release
    for (byte bitIdx = 0; bitIdx < 16; bitIdx++) {
      boolean prevBit = previousBtnRegister & (1 << bitIdx);
      boolean curBit = btnRegister & (1 << bitIdx);

      // not equals means either press or relase....
      if (prevBit != curBit) {

        // we want only press eveents....curBit is LOW on a press event
        if (!curBit) {
          if (SERIAL_DEBUG) {
            Serial.print(F("Press Event - "));
            printBinary16(btnRegister);
            Serial.println("");
            Serial.flush();
            delay(10);
          }

          /* 
           * buttons 13-15 are the unit selectors. 
           * handle the press same as the others.
           *   * send button event to host
           *   * host determines new unit size
           *   * host sends unit size information back to me in a client msg
           *   * i update my led in response to the client msg
           * this allows sync between pendant hardware and emulator, since host manages state
           */

          // byte 0 : MSG_START_BYTE
          // byte 1 : button number (bitIdx)
          // byte 2 : mm/inch (Pendant 2020 always sends 21, royale with cheese)
          // OBSOLETE - jog size is maintained in Pendant application in HC Pendant 2020 version
          // byte 3 : jog size (0=10.0, 1=01.0, 2=0.10)

          Serial.flush();
          Serial.write(MSG_START_BYTE);
          Serial.write(bitIdx);
          Serial.write(jogUnitSelector);
          //Serial.write(jogSizeSelector);
          Serial.println("");
        }
      }
    }
  }

  // update the "previous" value for the next iteration
  bouncingPreviousBtnRegister = bouncingCurrentBtnRegister;
}

void printBinary16(uint16_t x) {
  int idx;
  for (idx = 16; idx > 0; idx--) {
    if (idx == 8) {
      Serial.print(" ");
    }
    if ((x >> (idx - 1)) & 1) {
      Serial.print("1");
    } else {
      Serial.print("0");
    }
  }
}

void printBinaryByte(byte b) {
  int x;
  for (x = 8; x > 0; x--) {
    if ((b >> (x - 1)) & 1) {
      Serial.print("1");
    } else {
      Serial.print("0");
    }
  }
}
