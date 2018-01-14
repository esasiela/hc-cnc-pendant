package com.hedgecourt.ugspendant;

import java.io.IOException;
import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;

import org.apache.http.HttpEntity;
import org.apache.http.HttpResponse;
import org.apache.http.NameValuePair;
import org.apache.http.client.ClientProtocolException;
import org.apache.http.client.ResponseHandler;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.client.utils.URIBuilder;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.message.BasicNameValuePair;
import org.apache.http.util.EntityUtils;

import com.fazecast.jSerialComm.SerialPort;
import com.fazecast.jSerialComm.SerialPortDataListener;
import com.fazecast.jSerialComm.SerialPortEvent;

public class UgsPendant implements SerialPortDataListener {

    private PendantCtrl pendantCtrl = null;

    private SerialPort serialPort = null;
    private String portName = null;

    private long lastIndexVisitMillis = 0;

    public static void main(String[] args) {

        if (args.length < 1) {
            UgsPendant.printUsage();
            System.exit(1);
        }

        if (args[0].equalsIgnoreCase("list")) {
            listCommPorts();
            System.exit(0);
        }

        PendantCtrl pendantCtrl = new PendantCtrl();
        try {
            pendantCtrl.init();
        } catch (UgsPendantException E) {
            System.err.println("Failed initializing controller: " + E.getMessage());
            E.printStackTrace();
            System.exit(1);
        }

        if (args[0].equalsIgnoreCase("stop")) {
            System.out.println("sending stop signal to server");
            pendantCtrl.sendStopSignal();
            System.out.println("server stopped");
            System.exit(0);
        }

        if (args[0].equalsIgnoreCase("start")) {
            System.out.println("UgsPendant - starting comm server");

            if (args.length < 2) {
                UgsPendant.printUsage();
                System.err.println("start requires COMM_PORT");
                System.exit(1);
            }

            UgsPendant ugsPendant = new UgsPendant(pendantCtrl, args[1]);
            ugsPendant.doIt();

            System.exit(0);
        }

    }

    public static void printUsage() {
        System.out.println("usage: UgsPendant [list | stop | start COMM_PORT]\n");
    }

    public UgsPendant(PendantCtrl pendantCtrl, String commPort) {
        super();
        this.setPendantCtrl(pendantCtrl);
        this.setPortName(commPort);
    }

    public void doIt() {
        Runtime.getRuntime().addShutdownHook(new UgsPendantShutdownThread());

        new Thread() {
            @Override
            public void run() {
                getPendantCtrl().runServer();
            }
        }.start();

        UgsPendant.listCommPorts();

        System.out.println("\nUgsPendant - looking for serial port [" + this.getPortName() + "]");

        this.setSerialPort(SerialPort.getCommPort(this.getPortName()));
        if (this.getSerialPort() == null) {
            System.out.println("UgsPendant - serial port is null, exiting.");
            System.exit(1);
        }

        if (!this.getSerialPort().openPort()) {
            // failed opening
            System.out.println("UgsPendant - failed opening serial port, exiting.");
            System.exit(1);
        }

        this.getSerialPort().addDataListener(this);

        System.out.println("UgsPendant - successfully opened serial port.\n");

        while (!this.getPendantCtrl().isShuttingDown()) {

            if (this.getSerialPort() == null || !this.getSerialPort().isOpen()) {
                System.out.println("UgsPendant - serial port is not open, exiting.");
                this.getPendantCtrl().setShuttingDown(true);
            } else {

                if (Boolean.parseBoolean(this.getProperty("verbose.heartbeat"))) {
                    System.out.println("UgsPendant - thread heartbeat");
                }

                try {
                    synchronized (this.getPendantCtrl().getSemaphore()) {

                        int waitMillis = Integer.parseInt(this.getProperty("serial.thread.wait.millis"));
                        if (waitMillis == 0) {
                            this.getPendantCtrl().getSemaphore().wait();
                        } else {
                            this.getPendantCtrl().getSemaphore().wait(waitMillis);
                        }
                    }

                } catch (InterruptedException e) {

                }
            }
        }

        System.out.println("UgsPendant - shutdown received OR port closed (disconnect), exiting.");

    }

    @Override
    public int getListeningEvents() {
        return SerialPort.LISTENING_EVENT_DATA_AVAILABLE;
    }

    @Override
    public void serialEvent(SerialPortEvent e) {
        if (e.getEventType() != SerialPort.LISTENING_EVENT_DATA_AVAILABLE) {
            return;
        }
        byte[] newData = new byte[this.serialPort.bytesAvailable()];
        int numRead = this.serialPort.readBytes(newData, newData.length);
        System.out.println("UgsPendant - incoming serial data: numBytes=" + numRead);

        if (numRead == 1) {

            // gotta "& 0xFF" because java hates unsigned bytes
            if ((newData[0] & 0xFF) == Integer.decode(this.getProperty("serial.protocol.byte.stop"))) {
                System.out.println("\treceived shutdown command via serial");
                this.getPendantCtrl().setShuttingDown(true);
            } else {
                PendantDataPacket p = new PendantDataPacket(this.getPendantCtrl(), newData);

                String gCode = this.getGcodeForButton(p);

                if (p.getButtonNumber() < 6) {
                    System.out.println("\treceived axis jog button [" + p.toString() + "] [" + gCode + "]");
                } else {
                    System.out.println("\treceived direct gcode button [" + p.toString() + "] [" + gCode + "]");
                }

                // now send the gcode to the Ugs Pendant webserver
                if (!Boolean.valueOf(System.getProperty("hcPendant.suppress.http", "false"))) {

                    /*
                     * after a certain amount of idle time (and first time through), we need to visit
                     * the index page of the UGS Pendant UI webserver
                     */
                    if ((System.currentTimeMillis() - this.getLastIndexVisitMillis()) > (Long.parseLong(this.getProperty("ugs.index.visit.seconds")) * 1000)) {
                        System.out.println("\tvisiting UGS index page");
                        this.visitUgsUrl(this.getProperty("ugs.url.index"), Boolean.parseBoolean(this.getProperty("ugs.index.outputResponse")));
                        this.setLastIndexVisitMillis(System.currentTimeMillis());
                    }

                    // build the query parameter with the gCode
                    List<NameValuePair> queryParms = new ArrayList<>();
                    queryParms.add(new BasicNameValuePair("gCode", gCode));

                    System.out.println("\tvisiting UGS gcode page");
                    this.visitUgsUrl(this.getProperty("ugs.url.gcode"), Boolean.parseBoolean(this.getProperty("ugs.gcode.outputResponse")), queryParms);

                    // blank line to make the console a bit easier on the eyes
                    System.out.println("");

                }
            }
        } else {
            System.out.println("\treceived more than 1 byte, skipping packet.");
        }
    }

    public void visitUgsUrl(String requestUrl, boolean outputResponse) {
        this.visitUgsUrl(requestUrl, outputResponse, null);
    }

    public void visitUgsUrl(String requestUrl, boolean outputResponse, List<NameValuePair> queryParms) {
        CloseableHttpClient browser = HttpClients.createDefault();
        try {
            HttpGet getRequest = new HttpGet(requestUrl);

            if (queryParms != null) {
                URI uri = new URIBuilder(getRequest.getURI()).addParameters(queryParms).build();
                getRequest.setURI(uri);
            }

            System.out.println("\turi [" + getRequest.getURI().toString() + "]");

            ResponseHandler<String> respHandler = new ResponseHandler<String>() {
                @Override
                public String handleResponse(final HttpResponse response) throws ClientProtocolException, IOException {
                    int status = response.getStatusLine().getStatusCode();
                    if (status >= 200 && status < 300) {
                        HttpEntity entity = response.getEntity();
                        return entity != null ? EntityUtils.toString(entity) : null;
                    } else {
                        throw new ClientProtocolException("Unexpected response status [" + status + "]");
                    }
                }
            };

            String responseBody = browser.execute(getRequest, respHandler);

            if (outputResponse) {
                System.out.println("HTTP RESPONSE TEXT:");
                System.out.println("------------------------");
                System.out.println(responseBody);
                System.out.println("------------------------");
            }

        } catch (Exception E) {
            System.err.println("failed sending request to ugs pendant webserver: " + E.getMessage());
            E.printStackTrace();
        } finally {
            try {
                browser.close();
            } catch (Exception E) {
                System.err.println("failed closing http client: " + E.getMessage());
                E.printStackTrace();
            }
        }

    }

    public String getGcodeForButton(PendantDataPacket p) {
        if (p.getButtonNumber() < 6) {

            String buf = this.getProperty("jog.gcode.pattern");
            buf = buf.replaceAll("\\[JOG_UNIT\\]", p.getJogUnit());
            buf = buf.replaceAll("\\[JOG_AXIS\\]", this.getProperty("button." + p.getButtonNumber() + ".axis"));
            buf = buf.replaceAll("\\[JOG_DIR\\]", this.getProperty("button." + p.getButtonNumber() + ".dir"));
            buf = buf.replaceAll("\\[JOG_SIZE\\]", p.getJogSize());

            return buf;
        } else {
            return this.getProperty("button." + p.getButtonNumber() + ".gcode");
        }

    }

    public static void listCommPorts() {
        System.out.println("listing comm ports:");
        for (SerialPort p : SerialPort.getCommPorts()) {
            System.out.println("\tcomm port [" + p.getSystemPortName() + "] [" + p.getDescriptivePortName() + "]");
        }
        System.out.println("end comm port listing");
    }

    public String getPortName() {
        return portName;
    }

    public void setPortName(String portName) {
        this.portName = portName;
    }

    public SerialPort getSerialPort() {
        return serialPort;
    }

    public void setSerialPort(SerialPort serialPort) {
        this.serialPort = serialPort;
    }

    public PendantCtrl getPendantCtrl() {
        return pendantCtrl;
    }

    public void setPendantCtrl(PendantCtrl pendantCtrl) {
        this.pendantCtrl = pendantCtrl;
    }

    public Properties getProperties() {
        return this.getPendantCtrl().getProperties();
    }

    public String getProperty(String key) {
        return this.getProperties().getProperty(key);
    }

    public long getLastIndexVisitMillis() {
        return lastIndexVisitMillis;
    }

    public void setLastIndexVisitMillis(long lastIndexVisitMillis) {
        this.lastIndexVisitMillis = lastIndexVisitMillis;
    }

    /**
     * closes any open comm ports before shutting down
     * 
     * @author bumblebee
     *
     */
    private class UgsPendantShutdownThread extends Thread {
        public UgsPendantShutdownThread() {
            super();
        }

        @Override
        public void run() {
            System.out.println("\nUgsPendant - begin shutdown...");

            if (!getPendantCtrl().isShuttingDown()) {
                // in case the rest of the system doesnt know we're shutting down
                getPendantCtrl().setShuttingDown(true);
            }

            if (getSerialPort() != null && getSerialPort().isOpen()) {
                System.out.println("UgsPendant - closing serial port [" + getSerialPort().getSystemPortName() + "] [" + getSerialPort().getDescriptivePortName() + "]");
                getSerialPort().closePort();
            }

            System.out.println("UgsPendant - end shutdown. goodbye.");
        }

    }

}
