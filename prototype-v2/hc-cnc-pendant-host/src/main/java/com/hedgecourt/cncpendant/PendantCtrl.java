package com.hedgecourt.cncpendant;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.UnknownHostException;
import java.util.Properties;

public class PendantCtrl {

    private Properties properties = new Properties();

    private boolean shuttingDown = false;

    public PendantCtrl() {
        super();
    }

    public void init() throws CncPendantException {
        String propertyFileName = System.getProperty("hcPendant.properties.filename", "hcPendant.properties");
        try {
            this.properties.load(ClassLoader.getSystemResourceAsStream(propertyFileName));
        } catch (IOException E) {
            System.err.println("Failed loading properties from [" + propertyFileName + "]");
            throw new CncPendantException(E);
        }

        // validate we have a proper gcode sender selected
        String gsKey = "gcode.sender";
        String gsVal = null;
        if (System.getProperty(gsKey) != null && !System.getProperty(gsKey).isEmpty()) {
            // user specified via system property
            gsVal = System.getProperty("gcode.sender");

        } else if (this.getProperty(gsKey) != null && !this.getProperty(gsKey).isEmpty()) {
            // user specified via properties file
            gsVal = this.getProperty(gsKey);

        } else {
            // just use default "ugs", you never forget your first
            gsVal = "ugs";
        }

        CncPendant.log("using gcode.sender [" + gsVal + "]");
        // CncPendant.log("gcode separator [" + this.getProperty(gsVal + ".gcode.separator") + "]");

        this.getProperties().setProperty(gsKey, gsVal);
    }

    public void sendStopSignal() {
        try {
            Socket sock = new Socket(getProperty("controller.socket.host"), Integer.parseInt(getProperty("controller.socket.port")));
            PrintWriter out = new PrintWriter(sock.getOutputStream(), true);
            out.println(getProperty("controller.protocol.msg.stop"));
            sock.close();
        } catch (UnknownHostException E) {
            System.err.println("Socket Client - Unknown host: " + E.getMessage());
        } catch (IOException E) {
            System.err.println("Socket Client - Error writing to socket (is server running?): " + E.getMessage());
        }
    }

    public void runServer() {
        new Thread() {
            @Override
            public void run() {
                try {
                    ServerSocket serverSocket = new ServerSocket(Integer.parseInt(getProperty("controller.socket.port")));
                    Socket clientSocket = serverSocket.accept();
                    BufferedReader socketIn = new BufferedReader(new InputStreamReader(clientSocket.getInputStream()));

                    String inputLine = null;
                    String prevLine = null;

                    while ((inputLine = socketIn.readLine()) != null) {
                        System.out.println("Socket Server - read [" + inputLine + "]");
                        prevLine = inputLine;
                    }

                    if (prevLine != null && prevLine.equalsIgnoreCase(getProperty("controller.protocol.msg.stop"))) {
                        System.out.println("Socket Server - received stop command, exiting (tbh, any data recv means stop but whatevs)");
                    }

                    serverSocket.close();

                    setShuttingDown(true);

                } catch (IOException E) {
                    System.err.println("Socket Server - Error listening to port " + Integer.parseInt(getProperty("controller.socket.port")) + " or listening to connection: " + E.getMessage());
                    E.printStackTrace();
                }

            }
        }.start();

        while (!this.isShuttingDown()) {
            if (Boolean.parseBoolean(this.getProperty("verbose.heartbeat"))) {
                // when wait() is called with no millis, we hang forever and only run this "heartbeat" once
                System.out.println("Socket Server - thread heartbeat");
            }

            synchronized (this.getSemaphore()) {
                try {
                    int waitMillis = Integer.parseInt(this.getProperty("controller.thread.wait.millis"));
                    if (waitMillis == 0) {
                        this.getSemaphore().wait();
                    } else {
                        this.getSemaphore().wait(waitMillis);
                    }

                } catch (InterruptedException E) {

                }
            }
        }

        System.out.println("Socket Server - exiting");
    }

    public String getGcodeSenderProperty(String key) {
        return this.getProperty(this.getProperty("gcode.sender") + "." + key);
    }

    public String getProperty(String key) {
        return this.getProperties().getProperty(key);
    }

    public Properties getProperties() {
        return properties;
    }

    public Object getSemaphore() {
        return this;
    }

    public boolean isShuttingDown() {
        return shuttingDown;
    }

    public void setShuttingDown(boolean shuttingDown) {
        this.shuttingDown = shuttingDown;
        synchronized (this.getSemaphore()) {
            this.getSemaphore().notifyAll();
        }
    }

}
