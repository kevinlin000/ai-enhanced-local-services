package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.enums.PayType;
import com.bytebites.repository.BookingJpaRepository;
import com.bytebites.service.BookingHoldService;
import com.bytebites.service.BookingLineNotificationService;
import com.bytebites.service.TapPayService;
import com.bytebites.utils.UserHolder;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Arrays;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping({"/payment", "/api/payment"})
public class PaymentController {

    @Autowired
    TapPayService tapPay;

    @Autowired
    BookingJpaRepository bookingRepo;

    @Autowired
    BookingHoldService bookingHoldService;

    @Autowired
    BookingLineNotificationService bookingLineNotificationService;

    /**
     * 真實 TapPay Sandbox Pay by Prime 串接。
     * 前端先呼叫 TapPay JS SDK 取得 prime，再 POST 到此 endpoint。
     */
    @PostMapping("/tappay/pay-by-prime")
    public Result payByPrime(@RequestBody Map<String, Object> body) {
        String prime = (String) body.get("prime");
        if (prime == null || prime.isBlank()) return Result.fail("prime 必填");

        Long orderId  = Long.valueOf(body.get("orderId").toString());
        Long amount   = Long.valueOf(body.getOrDefault("amount", 1280).toString());
        String bookingCode = (String) body.get("bookingCode");   // 可為 null（舊流程相容）
        BookingJpa bookingForPayment = null;

        if (bookingCode != null && !bookingCode.isBlank()) {
            Optional<BookingJpa> opt = bookingRepo.findByBookingCode(bookingCode);
            if (opt.isEmpty()) return Result.fail("訂位不存在");

            BookingJpa booking = opt.get();
            if (!canAccessBooking(booking)) return Result.fail("無權操作此訂位");
            if (booking.getStatus() == BookingHoldService.STATUS_CANCELED) return Result.fail("訂位已取消，無法付款");
            if (booking.getStatus() == BookingHoldService.STATUS_EXPIRED) return Result.fail("此保留已逾期，請重新建立訂位");
            if (bookingHoldService.expireIfDue(booking)) return Result.fail("此保留已逾期，請重新建立訂位");
            if (!booking.getNeedsDeposit()) return Result.fail("此訂位免訂金、無需付款");
            if (booking.getStatus() == BookingHoldService.STATUS_PAID) {
                return Result.ok(Map.of(
                        "status", "PAID",
                        "rec_trade_id", booking.getPaymentTransId() != null ? booking.getPaymentTransId() : "",
                        "bookingCode", booking.getBookingCode(),
                        "amount", booking.getDepositTotal(),
                        "msg", "訂位已付款，回傳既有交易編號"
                ));
            }
            bookingForPayment = booking;
            amount = Long.valueOf(booking.getDepositTotal());
        }

        Map<String, Object> r = tapPay.payByPrime(prime, amount, orderId);
        Integer status = (Integer) r.get("status");

        if (status != null && status == 0) {
            String recTradeId = (String) r.get("rec_trade_id");

            // 回寫訂位記錄：status=2(已付款), payment_trans_id=rec_trade_id
            if (bookingCode != null && !bookingCode.isBlank()) {
                BookingJpa bk = bookingForPayment != null
                        ? bookingForPayment
                        : bookingRepo.findByBookingCode(bookingCode).orElse(null);
                if (bk == null) {
                    log.warn("[Payment] bookingCode={} 找不到訂位記錄", bookingCode);
                } else {
                    bk.setStatus(BookingHoldService.STATUS_PAID);
                    bk.setPaymentTransId(recTradeId);
                    bookingRepo.save(bk);
                    bookingLineNotificationService.pushBookingUpdated(bk, "paid");
                    log.info("[Payment] bookingCode={} → status=2, trans={}", bookingCode, recTradeId);
                }
            }

            return Result.ok(Map.of(
                    "status",       "PAID",
                    "rec_trade_id", recTradeId,
                    "bookingCode",  bookingCode != null ? bookingCode : "",
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
}
