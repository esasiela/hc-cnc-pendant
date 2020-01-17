package com.hedgecourt.cncpendant;

public class CncPendantException extends Exception {

    /**
     * 
     */
    private static final long serialVersionUID = 1L;

    public CncPendantException() {
        super();
    }

    public CncPendantException(String message) {
        super(message);
    }

    public CncPendantException(Throwable cause) {
        super(cause);
    }

    public CncPendantException(String message, Throwable cause) {
        super(message, cause);
    }

    public CncPendantException(String message, Throwable cause, boolean enableSuppression, boolean writableStackTrace) {
        super(message, cause, enableSuppression, writableStackTrace);
    }

}
