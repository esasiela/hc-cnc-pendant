#include <HC_BouncyButton.h>
/*
 * Tactical Button Planning:    note, not tactile :-)
 * Z Probe
 * Z- (hardcoded at 0.100 inches)
 * Z Top
 * G28
 * G30
 * Go To Work XY
 * 
 * Strategic Button Planning:
 * eStop / Pause (basically a soft stop)
 * X+
 * Y+
 * Z+
 * X-
 * Y-
 * Z-
 * Set Increment 1.00
 * Set Increment 0.10
 * Set Increment 0.01
 * Set Units Inch
 * Set Units MM
 * Z Probe (M5; G17; G20; G91 G38.2 z-.5 F2; G0 z.03; G38.2 z-.1 F1; G10 L20 P0 z.062; G0 z.1; G90)
 * Z Top (G53 G0 Z0)
 * G28
 * G30
 * Go To Work XY (G90 G0 X0 Y0)
 * Go To Ready Pos (G21 G90 G0 X0 Y0 Z15)
 * Set Work XY (G10 L20 P0 X0 Y0)
 * Move Z Zero Down 0.1mm (or 0.001 inch)
 * 
 * LED Planning:
 * Increment 1.00
 * Increment 0.10
 * Increment 0.01
 * Key Press Indicator
 * Inch Indicator
 * MM Indicator
 * Host Connection Alive?
 * GRBL State Indicator?
 * 
 * 
 * Some buttons are internal to pendant client only:
 *  Increment selectors (qty 3)
 *  Unit selectors (qty 2)
 * Others are external and must be sent to pendant server.
 * 14 externals in prelim design.
 * 
 * So need to xmit:
 * Button Number (5 bits / 32 choices / 14 used)
 * MM/Inch choice (1 bit / 2 choices / 2 used) 
 * Increment choice (2 bits / 4 choices / 3 used)
 * 
 * Bit Packing (s=size, u=unit, b=buttonNum)
 * 76543210
 * ssubbbbb
 */


/* Pack->Val
 * 0->1
 * 1->2
 * 2->4
 * 3->8
 * 4->16
 * 5->32
 * 6->64
 * 7->128
 */

#define PACK_BUTTON_NUM 0
#define PACK_JOG_UNIT 5
#define PACK_JOG_SIZE 6

#define JOG_UNIT_INCH 0
#define JOG_UNIT_MM 1

#define JOG_SIZE_1000 0
#define JOG_SIZE_0100 1
#define JOG_SIZE_0010 2
#define JOG_SIZE_0001 3

/*
 * Tactical pendant only has 6 buttons, but the code can support 12 on pins (3-13 plus A0)
 * INTERNAL count will be used once I implement jog unit and jog size buttons.
 */
#define BUTTON_COUNT 12
#define INTERNAL_BUTTON_COUNT 0
#define EXTERNAL_BUTTON_COUNT 12

#define PIN_LED A1

/*
 * Tactical defaults, use 0.100 INCHES for the only jog button Z-
 */
byte jogSizeSelector = JOG_SIZE_0100;
byte jogUnitSelector = JOG_UNIT_INCH;

/*
 * tooSoon is used for turnign the LED off for an interval after a button press
 * also, new button presses are ignored during this interval, preventing me from
 * hammering on a button and causing UGS/GRBL to become unhappy
 */
boolean tooSoon=false;
unsigned long tooSoonMillis=0;
unsigned int tooSoonInterval=500;

/*
 * debounce the buttons.
 * the mapping of pin number (on the left) to a button index (on the right),
 * which is really just the index of the buttons[] array.
 * when packing the byte to send to the java host, the index of the array is
 * used as the button number, and the java host prog only sees this number, it
 * does not ever care or know about button assignments.
 */
BouncyButton buttons[BUTTON_COUNT] = {
  BouncyButton(3),  // idx0 = X-
  BouncyButton(4),  // idx1 = X+
  BouncyButton(5),  // idx2 = Y-
  BouncyButton(6),  // idx3 = Y-
  BouncyButton(7),  // idx4 = Z-
  BouncyButton(8),  // idx5 = Z+
  BouncyButton(9),  // idx6 = G28
  BouncyButton(10), // idx7 = G30
  BouncyButton(11), // idx8 = G90 G0 X0 Y0
  BouncyButton(12), // idx9 = (ZTOP) G53 G0 Z0
  BouncyButton(13), // idx10 = (ZPROBE)
  BouncyButton(A0)  // idx11 = G28; G30 (Test semicolon separator)
};

void setup() {
  Serial.begin(9600);

  /*
   * turn on the pullup resistors and initialize the button debouncers
   */
  for (byte idx=0; idx<BUTTON_COUNT; idx++) {
    pinMode(buttons[idx].getPin(), INPUT_PULLUP);
    buttons[idx].init();
  }

  /*
   * Only one output LED in the tactical pendant.  the default is on, like a power indicator,
   * and it toggles off when button pressed
   */
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, HIGH);
}

void loop() {

  for (byte idx=0; idx<BUTTON_COUNT; idx++) {
    if (buttons[idx].update() && !buttons[idx].getState() && !tooSoon) {
      /*
       * if a button's debounced state has changed, and it is pressed down, and we're not in a lockout interval from an earlier press...
       */

      if (idx<EXTERNAL_BUTTON_COUNT) {
        byte data = 0;
        data |= jogSizeSelector<<PACK_JOG_SIZE;
        data |= jogUnitSelector<<PACK_JOG_UNIT;
        data |= idx<<PACK_BUTTON_NUM;
        Serial.write(data);
      } else {
        /*
         * tactical pendant has no internal buttons, so do nothing here. someday though.
         */
      }

      /*
       * turn off the LED and lockout button presses for a little while
       */
      digitalWrite(PIN_LED, LOW);
      tooSoonMillis=millis();
      tooSoon=true;
    }
  }

  if (tooSoon && millis()-tooSoonMillis > tooSoonInterval) {
    /*
     * if we're locked out and enough time has passed, unlock and turn the LED back on.
     */
    tooSoon=false;
    digitalWrite(PIN_LED, HIGH);
  }
}
