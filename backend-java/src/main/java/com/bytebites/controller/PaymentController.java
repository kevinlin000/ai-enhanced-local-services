package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.enums.PayType;
import com.bytebites.repository.BookingJpaRepository;
import com.bytebites.service.BookingDepositAdjustmentService;
import com.bytebites.service.BookingHoldService;
import com.bytebites.service.BookingLineNotificationService;
import com.bytebites.service.TapPayService;
import com.bytebites.utils.UserHolder;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;

import jakarta.servlet.http.HttpServletRequest;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping({"/payment", "/api/payment"})
public class PaymentController {
    private static final Duration REFUND_WEBHOOK_SIGNATURE_TOLERANCE = Duration.ofMinutes(5);

    @Autowired
    TapPayService tapPay;

    @Autowired
    BookingJpaRepository bookingRepo;

    @Autowired
    BookingHoldService bookingHoldService;

    @Autowired
    BookingLineNotificationService bookingLineNotificationService;

    @Autowired
    BookingDepositAdjustmentService bookingDepositAdjustmentService;

    @Value("${bytebites.refund.webhook.secret:}")
    String refundWebhookSecret;

    @Value("${bytebites.refund.webhook.previous-secret:}")
    String refundWebhookPreviousSecret;

    @Value("${bytebites.refund.webhook.allowed-sources:}")
    String refundWebhookAllowedSources;

    @Value("${bytebites.refund.webhook.trusted-proxies:}")
    String refundWebhookTrustedProxies;

    @Value("${bytebites.refund.webhook.source-header:X-Forwarded-For}")
    String refundWebhookSourceHeader;

    /**
     * 真實 TapPay Sandbox Pay by Prime 串接。
     * 前端先呼叫 TapPay JS SDK 取得 prime，再 POST 到此 endpoint。
     */
    @PostMapping("/tappay/pay-by-prime")
    public Result payByPrime(@RequestBody Map<String, Object> body) {
        String prime = (String) body.get("prime");
        if (prime == null || prime.isBlank()) return Result.fail("prime 必填");

        String bookingCode = (String) body.get("bookingCode");
        if (bookingCode == null || bookingCode.isBlank()) return Result.fail("bookingCode 必填");
        Long orderId;
        try {
            orderId = Long.valueOf(body.getOrDefault("orderId", System.currentTimeMillis()).toString());
        } catch (NumberFormatException ex) {
            return Result.fail("orderId 格式錯誤");
        }

        Optional<BookingJpa> opt = bookingRepo.findByBookingCode(bookingCode);
        if (opt.isEmpty()) return Result.fail("訂位不存在");

        BookingJpa bookingForPayment = opt.get();
        if (!canAccessBooking(bookingForPayment)) return Result.fail("無權操作此訂位");
        if (bookingForPayment.getStatus() == BookingHoldService.STATUS_CANCELED) return Result.fail("訂位已取消，無法付款");
        if (bookingForPayment.getStatus() == BookingHoldService.STATUS_EXPIRED) return Result.fail("此保留已逾期，請重新建立訂位");
        if (bookingHoldService.expireIfDue(bookingForPayment)) return Result.fail("此保留已逾期，請重新建立訂位");
        if (!bookingForPayment.getNeedsDeposit()) return Result.fail("此訂位免訂金、無需付款");
        if (bookingForPayment.getStatus() == BookingHoldService.STATUS_PAID) {
            return Result.ok(Map.of(
                    "status", "PAID",
                    "rec_trade_id", bookingForPayment.getPaymentTransId() != null ? bookingForPayment.getPaymentTransId() : "",
                    "bookingCode", bookingForPayment.getBookingCode(),
                    "amount", bookingForPayment.getDepositTotal(),
                    "msg", "訂位已付款，回傳既有交易編號"
            ));
        }
        Long amount = Long.valueOf(bookingForPayment.getDepositTotal());

        Map<String, Object> r = tapPay.payByPrime(prime, amount, orderId);
        Integer status = (Integer) r.get("status");

        if (status != null && status == 0) {
            String recTradeId = (String) r.get("rec_trade_id");

            bookingForPayment.setStatus(BookingHoldService.STATUS_PAID);
            bookingForPayment.setPaymentTransId(recTradeId);
            bookingRepo.save(bookingForPayment);
            bookingLineNotificationService.pushBookingUpdated(bookingForPayment, "paid");
            log.info("[Payment] bookingCode={} → status=2, trans={}", bookingCode, recTradeId);

            return Result.ok(Map.of(
                    "status",       "PAID",
                    "rec_trade_id", recTradeId,
                    "bookingCode",  bookingCode,
                    "amount",       amount,
                    "tappay_status", status,
                    "msg",          r.getOrDefault("msg", "成功")
            ));
        }
        String msg = String.valueOf(r.getOrDefault("msg", "付款失敗"));
        if (status != null && status == 4 && msg.toLowerCase().contains("ip mismatch")) {
            return Result.fail("TapPay sandbox IP 未在商家後台白名單內，請設定 server IP 後再試。");
        }
        return Result.fail("TapPay: " + msg + " (status=" + status + ")");
    }

    @GetMapping("/deposit-adjustments/top-ups")
    public Result customerTopUps() {
        Long userId = currentUserId();
        if (userId == null) return Result.fail("請先登入");
        return Result.ok(Map.of(
                "adjustments",
                bookingDepositAdjustmentService.listOpenTopUpsForCustomer(userId)
        ));
    }

    @PostMapping("/tappay/deposit-adjustments/{adjustmentId}/top-up/pay-by-prime")
    public Result payTopUpByPrime(
            @PathVariable Long adjustmentId,
            @RequestBody Map<String, Object> body
    ) {
        Long userId = currentUserId();
        if (userId == null) return Result.fail("請先登入");

        String prime = (String) body.get("prime");
        if (prime == null || prime.isBlank()) return Result.fail("prime 必填");
        Long orderId;
        try {
            orderId = Long.valueOf(body.getOrDefault("orderId", System.currentTimeMillis()).toString());
        } catch (NumberFormatException ex) {
            return Result.fail("orderId 格式錯誤");
        }

        Map<String, Object> adjustment;
        try {
            adjustment = bookingDepositAdjustmentService.payableTopUpForCustomer(userId, adjustmentId);
        } catch (IllegalArgumentException | IllegalStateException ex) {
            return Result.fail(ex.getMessage());
        }
        long amount = Math.abs(toLong(adjustment.get("deltaAmount")));
        if (amount <= 0) return Result.fail("補款金額不可為 0");

        Map<String, Object> r = tapPay.payByPrime(prime, amount, orderId);
        Integer status = (Integer) r.get("status");
        if (status != null && status == 0) {
            String recTradeId = (String) r.get("rec_trade_id");
            Map<String, Object> completed = bookingDepositAdjustmentService.recordCustomerTopUpSettlement(
                    userId,
                    adjustmentId,
                    recTradeId,
                    "Customer TapPay top-up completed"
            );
            log.info("[Payment top-up] adjustmentId={} userId={} amount={} trans={}",
                    adjustmentId, userId, amount, recTradeId);
            return Result.ok(Map.of(
                    "status", "PAID",
                    "adjustmentId", adjustmentId,
                    "bookingCode", String.valueOf(adjustment.get("bookingCode")),
                    "amount", amount,
                    "rec_trade_id", recTradeId,
                    "tappay_status", status,
                    "adjustment", completed,
                    "msg", r.getOrDefault("msg", "成功")
            ));
        }

        String msg = String.valueOf(r.getOrDefault("msg", "付款失敗"));
        if (status != null && status == 4 && msg.toLowerCase().contains("ip mismatch")) {
            return Result.fail("TapPay sandbox IP 未在商家後台白名單內，請設定 server IP 後再試。");
        }
        return Result.fail("TapPay: " + msg + " (status=" + status + ")");
    }

    /**
     * Demo 錢包補款（LINE Pay / Apple Pay / 街口）：與首次訂金的 pay-test 同一套規則，
     * 仍回寫真實的 settlement 狀態，避免 UI 與 DB 不一致。
     */
    @PostMapping("/deposit-adjustments/{adjustmentId}/top-up/pay-demo")
    public Result payTopUpWithDemo(@PathVariable Long adjustmentId) {
        Long userId = currentUserId();
        if (userId == null) return Result.fail("請先登入");

        Map<String, Object> adjustment;
        try {
            adjustment = bookingDepositAdjustmentService.payableTopUpForCustomer(userId, adjustmentId);
        } catch (IllegalArgumentException | IllegalStateException ex) {
            return Result.fail(ex.getMessage());
        }
        long amount = Math.abs(toLong(adjustment.get("deltaAmount")));
        if (amount <= 0) return Result.fail("補款金額不可為 0");

        String demoTransId = "DEMO-" + java.util.UUID.randomUUID().toString().substring(0, 12).toUpperCase();
        Map<String, Object> completed = bookingDepositAdjustmentService.recordCustomerTopUpSettlement(
                userId,
                adjustmentId,
                demoTransId,
                "Customer demo wallet top-up completed"
        );
        log.info("[Payment top-up demo] adjustmentId={} userId={} amount={} trans={}",
                adjustmentId, userId, amount, demoTransId);
        return Result.ok(Map.of(
                "status", "PAID",
                "adjustmentId", adjustmentId,
                "bookingCode", String.valueOf(adjustment.get("bookingCode")),
                "amount", amount,
                "rec_trade_id", demoTransId,
                "adjustment", completed,
                "msg", "Demo 補款成功"
        ));
    }

    @PostMapping("/tappay/deposit-adjustments/{adjustmentId}/refund/reconcile")
    public Result reconcileRefundAdjustment(
            @PathVariable Long adjustmentId,
            @RequestBody(required = false) Map<String, Object> body,
            @RequestHeader(name = "X-ByteBites-Webhook-Signature", required = false) String signature,
            @RequestHeader(name = "X-ByteBites-Webhook-Timestamp", required = false) String timestamp,
            HttpServletRequest request
    ) {
        Map<String, Object> requestBody = body != null ? body : Map.of();
        String bookingCode = text(requestBody.get("bookingCode"));
        if (bookingCode.isBlank()) return Result.fail("bookingCode 必填");

        long rawAmount = toLong(requestBody.get("amount"));
        if (rawAmount <= 0 || rawAmount > Integer.MAX_VALUE) {
            return Result.fail("amount 格式錯誤");
        }
        String status = text(requestBody.getOrDefault("status", "COMPLETED"));
        String settlementTransId = text(requestBody.get("settlementTransId"));
        String settlementNote = text(requestBody.get("settlementNote"));
        String eventKey = text(requestBody.get("eventKey"));

        if (!refundWebhookSourceValid(request)) {
            return Result.fail("退款 webhook 來源驗證失敗");
        }
        if (!refundWebhookSignatureValid(
                adjustmentId,
                bookingCode,
                rawAmount,
                status,
                settlementTransId,
                eventKey,
                signature,
                timestamp
        )) {
            return Result.fail("退款 webhook 簽章驗證失敗");
        }

        try {
            return Result.ok(bookingDepositAdjustmentService.reconcileRefund(
                    adjustmentId,
                    bookingCode,
                    (int) rawAmount,
                    status,
                    settlementTransId,
                    settlementNote,
                    eventKey
            ));
        } catch (IllegalArgumentException | IllegalStateException ex) {
            return Result.fail(ex.getMessage());
        }
    }

    /**
     * Mock TapPay callback。
     *
     * @deprecated 使用 /tappay/pay-by-prime 替代（真實 TapPay Sandbox 串接）。
     *             此 endpoint 保留供本地 demo / 非信用卡支付方式使用。
     */
    @Deprecated
    @PostMapping("/tappay/mock-callback")
    public Result mockCallback(@RequestBody Map<String, Object> body) {
        Long orderId = Long.valueOf(body.get("orderId").toString());
        int payTypeCode = ((Number) body.getOrDefault("payType", 1)).intValue();

        PayType payType = Arrays.stream(PayType.values())
                .filter(p -> p.getCode() == payTypeCode)
                .findFirst()
                .orElse(PayType.CREDIT_CARD);

        String fakeTransId = "TPY-" + UUID.randomUUID().toString().substring(0, 12).toUpperCase();

        log.info("[Mock TapPay] order={}, payType={} ({}), trans={}",
                orderId, payTypeCode, payType.getLabel(), fakeTransId);

        return Result.ok(Map.of(
                "status", "PAID",
                "rec_trade_id", fakeTransId,
                "pay_type", payTypeCode,
                "label", payType.getLabel(),
                "amount", body.getOrDefault("amount", 0)
        ));
    }

    @GetMapping("/methods")
    public Result methods() {
        return Result.ok(Arrays.stream(PayType.values())
                .map(p -> Map.of("code", p.getCode(), "label", p.getLabel()))
                .toList());
    }

    private boolean canAccessBooking(BookingJpa booking) {
        Long ownerId = booking.getUserId();
        UserDTO user = UserHolder.getUser();
        return ownerId != null && user != null && ownerId.equals(user.getId());
    }

    private Long currentUserId() {
        UserDTO user = UserHolder.getUser();
        return user != null ? user.getId() : null;
    }

    private long toLong(Object value) {
        if (value instanceof Number number) return number.longValue();
        if (value == null) return 0L;
        try {
            return Long.parseLong(value.toString());
        } catch (NumberFormatException ex) {
            return 0L;
        }
    }

    private String text(Object value) {
        return value == null ? "" : value.toString().trim();
    }

    private boolean refundWebhookSignatureValid(
            Long adjustmentId,
            String bookingCode,
            long amount,
            String status,
            String settlementTransId,
            String eventKey,
            String signature,
            String timestamp
    ) {
        List<String> secrets = refundWebhookSecrets();
        if (secrets.isEmpty()) return true;
        String normalizedSignature = normalizeSignature(signature);
        if (normalizedSignature == null || text(timestamp).isBlank()) return false;
        if (!timestampFresh(timestamp)) return false;
        String payload = refundWebhookSignaturePayload(
                timestamp,
                adjustmentId,
                bookingCode,
                amount,
                status,
                settlementTransId,
                eventKey
        );
        boolean matched = false;
        byte[] actual = normalizedSignature.getBytes(StandardCharsets.UTF_8);
        for (String secret : secrets) {
            String expected = hmacSha256Hex(secret, payload);
            matched |= MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8), actual);
        }
        return matched;
    }

    private boolean refundWebhookSourceValid(HttpServletRequest request) {
        List<String> allowedSources = sourceRules(refundWebhookAllowedSources);
        if (allowedSources.isEmpty()) return true;
        if (request == null) return false;

        String remoteAddress = normalizeSourceAddress(request.getRemoteAddr());
        List<String> candidates = new ArrayList<>();
        if (!remoteAddress.isBlank()) {
            if (sourceMatchesAny(remoteAddress, sourceRules(refundWebhookTrustedProxies))) {
                String forwardedSource = forwardedSourceAddress(request);
                if (!forwardedSource.isBlank()) {
                    candidates.add(forwardedSource);
                }
            }
            candidates.add(remoteAddress);
        }

        return candidates.stream().anyMatch(candidate -> sourceMatchesAny(candidate, allowedSources));
    }

    private String forwardedSourceAddress(HttpServletRequest request) {
        String headerName = text(refundWebhookSourceHeader);
        if (headerName.isBlank()) return "";
        String raw = request.getHeader(headerName);
        if (raw == null || raw.isBlank()) return "";
        return normalizeSourceAddress(raw.split(",", 2)[0]);
    }

    private List<String> sourceRules(String raw) {
        String value = text(raw);
        if (value.isBlank()) return List.of();
        return Arrays.stream(value.split("[,\\s]+"))
                .map(String::trim)
                .filter(rule -> !rule.isBlank())
                .distinct()
                .toList();
    }

    private boolean sourceMatchesAny(String source, List<String> rules) {
        String normalizedSource = normalizeSourceAddress(source);
        if (normalizedSource.isBlank()) return false;
        return rules.stream().anyMatch(rule -> sourceMatchesRule(normalizedSource, rule));
    }

    private boolean sourceMatchesRule(String source, String rawRule) {
        String rule = normalizeSourceAddress(rawRule);
        if (rule.isBlank()) return false;
        if (rule.contains("/")) {
            return ipv4CidrContains(source, rule);
        }
        return source.equals(rule);
    }

    private String normalizeSourceAddress(String raw) {
        String value = text(raw);
        if (value.isBlank()) return "";
        if (value.startsWith("[") && value.contains("]")) {
            value = value.substring(1, value.indexOf(']'));
        } else if (value.matches("^\\d+\\.\\d+\\.\\d+\\.\\d+:\\d+$")) {
            value = value.substring(0, value.lastIndexOf(':'));
        }
        return value;
    }

    private boolean ipv4CidrContains(String source, String cidr) {
        String[] parts = cidr.split("/", 2);
        if (parts.length != 2) return false;
        Long sourceIp = ipv4ToLong(source);
        Long networkIp = ipv4ToLong(parts[0]);
        if (sourceIp == null || networkIp == null) return false;
        int prefixLength;
        try {
            prefixLength = Integer.parseInt(parts[1]);
        } catch (NumberFormatException ex) {
            return false;
        }
        if (prefixLength < 0 || prefixLength > 32) return false;
        long mask = prefixLength == 0 ? 0L : (0xFFFF_FFFFL << (32 - prefixLength)) & 0xFFFF_FFFFL;
        return (sourceIp & mask) == (networkIp & mask);
    }

    private Long ipv4ToLong(String raw) {
        String[] octets = text(raw).split("\\.");
        if (octets.length != 4) return null;
        long value = 0L;
        for (String octet : octets) {
            int parsed;
            try {
                parsed = Integer.parseInt(octet);
            } catch (NumberFormatException ex) {
                return null;
            }
            if (parsed < 0 || parsed > 255) return null;
            value = (value << 8) | parsed;
        }
        return value;
    }

    private List<String> refundWebhookSecrets() {
        List<String> secrets = new ArrayList<>();
        addRefundWebhookSecret(secrets, refundWebhookSecret);
        addRefundWebhookSecret(secrets, refundWebhookPreviousSecret);
        return secrets;
    }

    private void addRefundWebhookSecret(List<String> secrets, String raw) {
        String secret = text(raw);
        if (!secret.isBlank() && !secrets.contains(secret)) {
            secrets.add(secret);
        }
    }

    private String refundWebhookSignaturePayload(
            String timestamp,
            Long adjustmentId,
            String bookingCode,
            long amount,
            String status,
            String settlementTransId,
            String eventKey
    ) {
        return String.join("\n",
                text(timestamp),
                "refund-reconcile",
                String.valueOf(adjustmentId),
                text(bookingCode),
                String.valueOf(amount),
                text(status).toUpperCase(),
                text(settlementTransId),
                text(eventKey)
        );
    }

    private boolean timestampFresh(String timestamp) {
        try {
            long raw = Long.parseLong(text(timestamp));
            Instant eventTime = raw > 1_000_000_000_000L
                    ? Instant.ofEpochMilli(raw)
                    : Instant.ofEpochSecond(raw);
            Duration skew = Duration.between(eventTime, Instant.now()).abs();
            return skew.compareTo(REFUND_WEBHOOK_SIGNATURE_TOLERANCE) <= 0;
        } catch (RuntimeException ex) {
            return false;
        }
    }

    private String normalizeSignature(String signature) {
        String value = text(signature);
        if (value.startsWith("sha256=")) value = value.substring("sha256=".length());
        if (value.matches("^[0-9a-fA-F]{64}$")) {
            return value.toLowerCase();
        }
        return null;
    }

    private String hmacSha256Hex(String secret, String payload) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            return HexFormat.of().formatHex(mac.doFinal(payload.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception ex) {
            throw new IllegalStateException("refund webhook signature cannot be calculated", ex);
        }
    }
}
