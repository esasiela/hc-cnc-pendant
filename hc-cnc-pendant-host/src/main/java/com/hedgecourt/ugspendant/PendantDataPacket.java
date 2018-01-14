package com.hedgecourt.ugspendant;

public class PendantDataPacket {

    public static final int PACK_BUTTON_NUM = 0;
    public static final int PACK_JOG_UNIT = 5;
    public static final int PACK_JOG_SIZE = 6;

    public static final int JOG_UNIT_INCH = 0;
    public static final int JOG_UNIT_MM = 1;

    public static final int JOG_SIZE_1000 = 0;
    public static final int JOG_SIZE_0100 = 1;
    public static final int JOG_SIZE_0010 = 2;
    public static final int JOG_SIZE_0001 = 3;

    private byte[] bytes = { 0x00 };

    private PendantCtrl pendantCtrl = null;

    public PendantDataPacket(PendantCtrl pendantCtrl) {
        super();
        this.setPendantCtrl(pendantCtrl);
    }

    public PendantDataPacket(PendantCtrl pendantCtrl, byte[] bytes) {
        this(pendantCtrl);
        this.setBytes(bytes);
    }

    public String getJogUnit() {
        int val = (bytes[0] & 0b00100000) >>> PACK_JOG_UNIT;
        return this.getPendantCtrl().getProperty("data.jogUnit." + val);
    }

    public String getJogSize() {
        int val = (bytes[0] & 0b11000000) >>> PACK_JOG_SIZE;
        return this.getPendantCtrl().getProperty("data.jogSize." + val);
    }

    public int getButtonNumber() {
        return (bytes[0] & 0b00011111) >>> PACK_BUTTON_NUM;
    }

    public byte[] getBytes() {
        return bytes;
    }

    public void setBytes(byte[] bytes) {
        this.bytes = bytes;
    }

    public PendantCtrl getPendantCtrl() {
        return pendantCtrl;
    }

    public void setPendantCtrl(PendantCtrl pendantCtrl) {
        this.pendantCtrl = pendantCtrl;
    }

    @Override
    public String toString() {
        return "jogSize=" + getJogSize() + " jogUnit=" + getJogUnit() + " buttonNum=" + getButtonNumber();
    }
}
