package com.bytebites.enums;

public enum PayType {
    CREDIT_CARD(1, "信用卡"),
    LINE_PAY(2, "Line Pay"),
    APPLE_PAY(3, "Apple Pay"),
    JKO_PAY(4, "街口支付");

    private final int code;
    private final String label;

    PayType(int code, String label) {
        this.code = code;
        this.label = label;
    }

    public int getCode() { return code; }
    public String getLabel() { return label; }
}
