package com.bytebites.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * TapPay 串接設定，從 application.yaml 的 tappay.* 讀取。
 * 環境變數優先：TAPPAY_PARTNER_KEY、TAPPAY_API_BASE、TAPPAY_MERCHANT_CREDITCARD
 */
@ConfigurationProperties(prefix = "tappay")
@Data
@Component
public class TapPayProperties {
    private String partnerKey;
    private String apiBase;
    private String merchantCreditCard;
}
