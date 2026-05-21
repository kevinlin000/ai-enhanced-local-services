package com.bytebites.exception;

public class LockAcquireException extends RuntimeException {

    public LockAcquireException(String message) {
        super(message);
    }
}
