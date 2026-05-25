package com.bytebites.config;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;
import org.springframework.validation.annotation.Validated;

/**
 * TapPay 串接設定，從 application.yaml 的 tappay.* 讀取。
 * 環境變數優先：TAPPAY_PARTNER_KEY、TAPPAY_API_BASE、TAPPAY_MERCHANT_CREDITCARD
 *
 * @Validated + @Pattern 防護：若環境變數未設定，
 * Spring 會把 ${TAPPAY_PARTNER_KEY} 當成 literal string 傳進來，
 * @NotBlank 看不出問題、但 @Pattern 會 match 到 ${ 開頭而直接炸掉啟動。
 */
@ConfigurationProperties(prefix = "tappay")
@Validated
@Data
@Component
public class TapPayProperties {

    @NotBlank(message = "tappay.partner-key 未設定（請設環境變數 TAPPAY_PARTNER_KEY）")
    @Pattern(
        regexp = "^(?!\\$\\{).+",
        message = "TAPPAY_PARTNER_KEY 未解析（仍是 placeholder），請設定環境變數"
    )
    private String partnerKey;

    @NotBlank(message = "tappay.api-base 未設定")
    @Pattern(regexp = "^(?!\\$\\{).+", message = "TAPPAY_API_BASE 未解析，請設定環境變數")
    private String apiBase;

    @NotBlank(message = "tappay.merchant-credit-card 未設定（請設環境變數 TAPPAY_MERCHANT_CREDITCARD）")
    @Pattern(
        regexp = "^(?!\\$\\{).+",
        message = "TAPPAY_MERCHANT_CREDITCARD 未解析，請設定環境變數"
    )
    private String merchantCreditCard;
}
