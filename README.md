# hc-cnc-pendant

This repository is for the software required to run an Arduino-based CNC Pendant and the host software bridge that connects the pendant to a Gcode sender with a web user interface.

* The sender is the control software that is connected to the CNC machine.  Senders are outside the scope of this repository.  The client/host that are part of this repostiory interface with the sender of your choice.  Currently tested with Universal Gcode Sender (UGS) and bCNC. Via modifications to the properties file, can support any web ui that takes a simple line of Gcode via a request parameter.

* The client is the physical pendant device powered by an Arduino, connected to the host computer via USB.

* The host is a Java application that runs on the host computer.  It listens to the client over USB, and feeds G-Code to the sender (UGS, bCNC) via the sender's pendant web UI.

* It is common that the host will run on the same computer as the sender, however this is not required.  URL references to localhost can be changed to the remote address of the sender.

## hc-cnc-pendant-client

This directory contains the Arduino sketch that runs on the pendant device.

## hc-cnc-pendant-host

This directory contains the host application Java source and resources plus Maven .pom project descriptor.
