package com.hedgecourt.ugspendant;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.UnknownHostException;

public class TestPipe {

    public static final int PORT = 8109;

    private boolean killServer = false;
    private Object semaphore = new Object();

    public static void main(String[] args) {

        if (args.length < 1) {
            System.out.println("usage: TestPipe [start|stop]");
            System.exit(1);
        }

        if (args[0].equalsIgnoreCase("start")) {
            TestPipe tp = new TestPipe();
            tp.runServer();

        } else if (args[0].equalsIgnoreCase("stop")) {
            TestPipe tp = new TestPipe();
            tp.runClient();

        } else {
            System.out.println("usage: TestPipe [start|stop]");
            System.exit(1);
        }

    }

    public void runClient() {
        try {
            Socket sock = new Socket("localhost", PORT);
            PrintWriter out = new PrintWriter(sock.getOutputStream(), true);
            out.println("stop");
            sock.close();
        } catch (UnknownHostException E) {
            System.err.println("Unknown host: " + E.getMessage());
        } catch (IOException E) {
            System.err.println("Error writing to socket: " + E.getMessage());
            E.printStackTrace();
        }
    }

    public void runServer() {
        new Thread() {
            @Override
            public void run() {
                try {
                    ServerSocket serverSocket = new ServerSocket(PORT);
                    Socket clientSocket = serverSocket.accept();
                    BufferedReader socketIn = new BufferedReader(new InputStreamReader(clientSocket.getInputStream()));

                    String inputLine = null;

                    while ((inputLine = socketIn.readLine()) != null) {
                        System.out.println("SERVER READS [" + inputLine + "]");
                    }

                    serverSocket.close();
                    killServer = true;

                    synchronized (semaphore) {
                        semaphore.notifyAll();
                    }

                } catch (IOException E) {
                    System.err.println("Error listening to port " + PORT + " or listening to connection: " + E.getMessage());
                    E.printStackTrace();
                }

            }
        }.start();

        while (!this.killServer) {
            System.out.println("Listener thread is listening.");
            synchronized (semaphore) {
                try {
                    semaphore.wait(1000);
                } catch (InterruptedException E) {

                }
            }
        }

        System.out.println("Server exiting.");
    }

}
