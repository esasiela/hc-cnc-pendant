package com.hedgecourt.cncpendant;

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

public class CncPendant implements SerialPortDataListener {

    private PendantCtrl pendantCtrl = null;

    private SerialPort serialPort = null;
    private String portName = null;

    private long lastIndexVisitMillis = 0;

    public static void main(String[] args) {

        if (args.length < 1) {
            CncPendant.printUsage();
            System.exit(1);
        }

        if (args[0].equalsIgnoreCase("list")) {
            CncPendant.listCommPorts();
            System.exit(0);
        }

        PendantCtrl pendantCtrl = new PendantCtrl();
        try {
            pendantCtrl.init();
        } catch (CncPendantException E) {
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
            CncPendant.log("starting comm server");

            if (args.length < 2) {
                CncPendant.printUsage();
                System.err.println("start requires COMM_PORT");
                System.exit(1);
            }

            CncPendant cncPendant = new CncPendant(pendantCtrl, args[1]);
            cncPendant.doIt();

            System.exit(0);
        }

    }

    public static void printUsage() {
        System.out.println("usage: CncPendant [list | stop | start COMM_PORT]\n");
        System.out.println("\t-Dgcode.sender=[ugs|bcnc]");
        CncPendant.listCommPorts();
    }

    public CncPendant(PendantCtrl pendantCtrl, String commPort) {
        super();
        this.setPendantCtrl(pendantCtrl);
        this.setPortName(commPort);
    }

    public void doIt() {
        Runtime.getRuntime().addShutdownHook(new CncPendantShutdownThread());

        new Thread() {
            @Override
            public void run() {
                getPendantCtrl().runServer();
            }
        }.start();

        CncPendant.listCommPorts();

        CncPendant.logNewLine();
        CncPendant.log("looking for serial port [" + this.getPortName() + "]");

        this.setSerialPort(SerialPort.getCommPort(this.getPortName()));
        if (this.getSerialPort() == null) {
            CncPendant.log("serial port is null, exiting.");
            System.exit(1);
        }

        if (!this.getSerialPort().openPort()) {
            // failed opening
            CncPendant.log("failed opening serial port, exiting.");
            System.exit(1);
        }

        this.getSerialPort().addDataListener(this);

        CncPendant.log("successfully opened serial port.\n");

        while (!this.getPendantCtrl().isShuttingDown()) {

            if (this.getSerialPort() == null || !this.getSerialPort().isOpen()) {
                CncPendant.log("serial port is not open, exiting.");
                this.getPendantCtrl().setShuttingDown(true);
            } else {

                if (Boolean.parseBoolean(this.getProperty("verbose.heartbeat"))) {
                    CncPendant.log("thread heartbeat");
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

        CncPendant.log("shutdown received OR port closed (disconnect), exiting.");

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
        CncPendant.log("incoming serial data: numBytes=" + numRead);

        if (numRead == 1) {

            // gotta "& 0xFF" because java hates unsigned bytes
            if ((newData[0] & 0xFF) == Integer.decode(this.getProperty("serial.protocol.byte.stop"))) {
                CncPendant.log("received shutdown command via serial", true);
                this.getPendantCtrl().setShuttingDown(true);
            } else {
                PendantDataPacket p = new PendantDataPacket(this.getPendantCtrl(), newData);

                String gCode = this.getGcodeForButton(p);

                if (p.getButtonNumber() < 6) {
                    CncPendant.log("received axis jog button [" + p.toString() + "] [" + gCode + "]", true);
                } else {
                    CncPendant.log("received direct gcode button [" + p.toString() + "] [" + gCode + "]", true);
                }

                // convert gCode separator to the value required by the sender
                if (gCode != null && !this.getProperty("gcode.separator.default").equals(this.getGcodeSenderProperty("gcode.separator"))) {
                    gCode = gCode.replaceAll(this.getProperty("gcode.separator.default"), this.getGcodeSenderProperty("gcode.separator"));
                }

                // now send the gcode to the Gcode Sender Pendant webserver
                if (!Boolean.valueOf(System.getProperty("hcPendant.suppress.http", "false"))) {

                    /*
                     * after a certain amount of idle time (and first time through), we need to visit
                     * the index page of the Cnc Pendant UI webserver (important for first visit to UGS after it starts up)
                     */
                    long indexIntervalMillis = Long.parseLong(this.getGcodeSenderProperty("index.visit.seconds")) * 1000;

                    if ((indexIntervalMillis > 0) && (System.currentTimeMillis() - this.getLastIndexVisitMillis()) > indexIntervalMillis) {

                        CncPendant.log("visiting Web UI index page", true);
                        this.visitWebUI(this.getGcodeSenderProperty("index.url"), Boolean.parseBoolean(this.getGcodeSenderProperty("index.outputResponse")));
                        this.setLastIndexVisitMillis(System.currentTimeMillis());
                    }

                    // build the query parameter with the gCode
                    List<NameValuePair> queryParms = new ArrayList<>();
                    queryParms.add(new BasicNameValuePair(this.getGcodeSenderProperty("gcode.paramName"), gCode));

                    CncPendant.log("visiting Web UI gcode page", true);
                    this.visitWebUI(this.getGcodeSenderProperty("gcode.url"), Boolean.parseBoolean(this.getGcodeSenderProperty("gcode.outputResponse")), queryParms);

                    // blank line to make the console a bit easier on the eyes
                    CncPendant.logNewLine();

                }
            }
        } else {
            CncPendant.log("received more than 1 byte, skipping packet.", true);
        }
    }

    public static void log(String msg) {
        CncPendant.log(msg, false);
    }

    public static void log(String msg, boolean wantIndent) {
        if (wantIndent) {
            System.out.println("\t" + msg);
        } else {
            System.out.println("CncPendant - " + msg);
        }
    }

    public static void logNewLine() {
        System.out.println("");
    }

    public void visitWebUI(String requestUrl, boolean outputResponse) {
        this.visitWebUI(requestUrl, outputResponse, null);
    }

    public void visitWebUI(String requestUrl, boolean outputResponse, List<NameValuePair> queryParms) {
        CloseableHttpClient browser = HttpClients.createDefault();
        try {
            HttpGet getRequest = new HttpGet(requestUrl);

            if (queryParms != null) {
                URI uri = new URIBuilder(getRequest.getURI()).addParameters(queryParms).build();
                getRequest.setURI(uri);
            }

            CncPendant.log("uri [" + getRequest.getURI().toString() + "]", true);

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
            System.err.println("failed sending request to Web UI pendant webserver: " + E.getMessage());
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
        String gCode = null;
        if (p.getButtonNumber() < 6) {

            gCode = this.getProperty("jog.gcode.pattern");
            gCode = gCode.replaceAll("\\[JOG_UNIT\\]", p.getJogUnit());
            gCode = gCode.replaceAll("\\[JOG_AXIS\\]", this.getProperty("button." + p.getButtonNumber() + ".axis"));
            gCode = gCode.replaceAll("\\[JOG_DIR\\]", this.getProperty("button." + p.getButtonNumber() + ".dir"));
            gCode = gCode.replaceAll("\\[JOG_SIZE\\]", p.getJogSize());

        } else {
            gCode = this.getProperty("button." + p.getButtonNumber() + ".gcode");
        }

        return gCode;
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

    public String getGcodeSenderProperty(String key) {
        return this.getPendantCtrl().getGcodeSenderProperty(key);
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
    private class CncPendantShutdownThread extends Thread {
        public CncPendantShutdownThread() {
            super();
        }

        @Override
        public void run() {
            CncPendant.logNewLine();
            CncPendant.log("CncPendant - begin shutdown...");

            if (!getPendantCtrl().isShuttingDown()) {
                // in case the rest of the system doesnt know we're shutting down
                getPendantCtrl().setShuttingDown(true);
            }

            if (getSerialPort() != null && getSerialPort().isOpen()) {
                CncPendant.log("closing serial port [" + getSerialPort().getSystemPortName() + "] [" + getSerialPort().getDescriptivePortName() + "]");
                getSerialPort().closePort();
            }

            CncPendant.log("end shutdown. goodbye.");
        }

    }

}
