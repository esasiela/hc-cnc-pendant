# hc-cnc-pendant

This repository is for the software required to run an Arduino-based CNC Pendant and the host software bridge that connects the pendant to Universal Gcode Sender (UGS).

* The client is the physical pendant device powered by an Arduino, connected to the host computer via USB.

* The host is a Java application that runs on the host computer, listens to the client over USB, and sends G-Code to UGS via the UGS Pendant web UI.

## hc-cnc-pendant-client

This directory contains the Arduino sketch that runs on the pendant device.

## hc-cnc-pendant-host

This directory contains the Java source and resources plus Maven .pom project descriptor.
