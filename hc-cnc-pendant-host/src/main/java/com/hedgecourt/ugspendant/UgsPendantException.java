package com.hedgecourt.ugspendant;

public class UgsPendantException extends Exception {

    /**
     * 
     */
    private static final long serialVersionUID = 1L;

    public UgsPendantException() {
        super();
    }

    public UgsPendantException(String message) {
        super(message);
    }

    public UgsPendantException(Throwable cause) {
        super(cause);
    }

    public UgsPendantException(String message, Throwable cause) {
        super(message, cause);
    }

    public UgsPendantException(String message, Throwable cause, boolean enableSuppression, boolean writableStackTrace) {
        super(message, cause, enableSuppression, writableStackTrace);
    }

}
