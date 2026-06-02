package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import com.bytebites.service.DepositPolicy;
import com.bytebites.service.IShopService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalTime;
import java.time.format.DateTimeParseException;
import java.util.Map;
import java.util.UUID;

/**
 * 訂位 Controller。
 * 免訂金：直接 reserve → status=3(已確認)。
 * 有訂金：前端先 reserve → status=1(待付款)，TapPay 付款後回寫 status=2。
 * pay-test：供 AI agent 直接以 sandbox test card 完成付款。
 */
@Slf4j
@RequiredArgsConstructor
@RestController
@RequestMapping({"/booking", "/api/booking"})
public class BookingController {

    private final BookingJpaRepository bookingRepo;
    private final IShopService shopService;
    private final DepositPolicy depositPolicy;
    /**
     * 建立訂位記錄並寫 DB。
     * needsDeposit=true  → status=1(待付款)，等 TapPay 回寫。
     * needsDeposit=false → status=3(已確認)。
     */
    @PostMapping("/reserve")
    public Result reserve(@RequestBody Map<String, Object> body) {
        if (body.get("shopId") == null) return Result.fail("shopId 必填");
        if (body.get("date") == null)   return Result.fail("date 必填");
        if (body.get("time") == null)   return Result.fail("time 必填");

        Long shopId;
        int people;
        LocalDate bookingDate;
        LocalTime bookingTime;
        try {
            shopId = Long.valueOf(body.get("shopId").toString());
            people = Integer.parseInt(body.getOrDefault("people", 2).toString());
            bookingDate = LocalDate.parse(body.get("date").toString());
            bookingTime = LocalTime.parse(body.get("time").toString());
        } catch (NumberFormatException | DateTimeParseException ex) {
            return Result.fail("訂位格式錯誤，請確認 shopId、people、date(YYYY-MM-DD)、time(HH:mm)");
        }

        if (people < 1 || people > 12) return Result.fail("訂位人數需介於 1-12 人");
        if (bookingDate.isBefore(LocalDate.now())) return Result.fail("不能建立過去日期訂位");
        if (bookingDate.isEqual(LocalDate.now()) && bookingTime.isBefore(LocalTime.now())) {
            return Result.fail("不能建立過去時間訂位");
        }

        String time = bookingTime.toString();
        String table = body.getOrDefault("tableType", "normal").toString();
        if (!table.equals("normal") && !table.equals("bar") && !table.equals("private")) {
            return Result.fail("tableType 僅支援 normal/bar/private");
        }

        // 查訂金政策
        var shop     = shopService.getById(shopId);
        if (shop == null) return Result.fail("店家不存在");
        Integer typeId   = shop != null && shop.getTypeId() != null ? shop.getTypeId().intValue() : null;
        Integer score    = shop != null ? shop.getScore() : null;
        Integer avgPrice = shop != null && shop.getAvgPrice() != null ? shop.getAvgPrice().intValue() : null;
        String  shopName = shop != null ? shop.getName() : null;
        DepositPolicy.Result pol = depositPolicy.evaluate(shopId, shopName, typeId, score, avgPrice);

        // 建 booking 記錄
        BookingJpa booking = new BookingJpa();
        booking.setBookingCode("BK-" + UUID.randomUUID().toString().substring(0, 12).toUpperCase());
        booking.setShopId(shopId);
        booking.setPeople(people);
        booking.setBookingDate(bookingDate);
        booking.setBookingTime(time);
        booking.setTableType(table);
        booking.setNeedsDeposit(pol.isNeedsDeposit());
        booking.setDepositPerPerson(pol.getDepositPerPerson());
        booking.setDepositTotal(pol.isNeedsDeposit() ? pol.getDepositPerPerson() * people : 0);
        booking.setStatus(pol.isNeedsDeposit() ? 1 : 3);  // 1=待付款, 3=已確認

        bookingRepo.save(booking);

        log.info("[Booking] code={} shop={} people={} date={} time={} table={} needsDeposit={} status={}",
                booking.getBookingCode(), shopId, people, bookingDate, time, table,
                pol.isNeedsDeposit(), booking.getStatus());

        return Result.ok(Map.of(
                "bookingCode",  booking.getBookingCode(),
                "shopId",       shopId,
                "shopName",     shopName != null ? shopName : "店家 " + shopId,
                "people",       people,
                "date",         bookingDate.toString(),
                "time",         time,
                "tableType",    table,
                "needsDeposit", pol.isNeedsDeposit(),
                "depositTotal", booking.getDepositTotal(),
                "status",       pol.isNeedsDeposit() ? "PENDING_PAYMENT" : "CONFIRMED"
        ));
    }

    /**
     * AI Agent / Demo 專用：模擬訂金付款、不打真實 TapPay。
     * TapPay prime 為 one-time token 需 JS SDK 產生，server-side 無法靜態複用。
     * 此 endpoint 直接寫入 demo trans_id，僅供 agent demo 展示全流程。
     *
     * @param body { "bookingCode": "BK-XXXXXXXXXXXX" }
     */
    @PostMapping("/pay-test")
    public Result payTest(@RequestBody Map<String, Object> body) {
        String bookingCode = (String) body.get("bookingCode");
        if (bookingCode == null || bookingCode.isBlank()) return Result.fail("bookingCode 必填");

        BookingJpa b = bookingRepo.findByBookingCode(bookingCode).orElse(null);
        if (b == null)            return Result.fail("訂位不存在");
        if (!b.getNeedsDeposit()) return Result.fail("此訂位免訂金、無需付款");
        if (b.getStatus() == 2) {
            return Result.ok(Map.of(
                    "bookingCode",  bookingCode,
                    "rec_trade_id", b.getPaymentTransId(),
                    "amount",       b.getDepositTotal(),
                    "status",       "PAID",
                    "note",         "訂位已付款，回傳既有交易編號"
            ));
        }

        // Demo transaction ID（格式仿 TapPay）
        String demoTransId = "DEMO-" + UUID.randomUUID().toString().substring(0, 12).toUpperCase();
        b.setPaymentTransId(demoTransId);
        b.setStatus(2);
        bookingRepo.save(b);

        log.info("[Booking pay-test] {} demo-paid via agent, trans={}", bookingCode, demoTransId);

        return Result.ok(Map.of(
                "bookingCode",  bookingCode,
                "rec_trade_id", demoTransId,
                "amount",       b.getDepositTotal(),
                "status",       "PAID",
                "note",         "agent demo 付款，非真實 TapPay"
        ));
    }
}
