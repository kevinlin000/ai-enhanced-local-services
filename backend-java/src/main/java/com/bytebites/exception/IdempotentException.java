package com.bytebites.exception;

public class IdempotentException extends RuntimeException {

    public IdempotentException(String message) {
        super(message);
    }
}
