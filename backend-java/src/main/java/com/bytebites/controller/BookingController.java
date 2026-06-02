package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.entity.jpa.BookingJpa;
import com.bytebites.repository.BookingJpaRepository;
import com.bytebites.service.DepositPolicy;
import com.bytebites.service.IShopService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.CannotAcquireLockException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.DefaultTransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.LinkedHashMap;
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
    private static final ZoneId BUSINESS_ZONE = ZoneId.of("Asia/Taipei");

    private final BookingJpaRepository bookingRepo;
    private final IShopService shopService;
    private final DepositPolicy depositPolicy;
    private final JdbcTemplate jdbcTemplate;
    private final PlatformTransactionManager transactionManager;

    /**
     * 建立訂位記錄並寫 DB。
     * needsDeposit=true  → status=1(待付款)，等 TapPay 回寫。
     * needsDeposit=false → status=3(已確認)。
     */
    @PostMapping("/reserve")
    public Result reserve(@RequestBody Map<String, Object> body) {
        for (int attempt = 1; attempt <= 2; attempt++) {
            try {
                return reserveTransactionTemplate().execute(status -> reserveInTransaction(body));
            } catch (CannotAcquireLockException ex) {
                if (attempt == 2) {
                    log.warn("[Booking] slot lock contention after retry body={}", body, ex);
                    return Result.fail("該時段目前忙碌，請稍後再試");
                }
                try {
                    Thread.sleep(30);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    return Result.fail("訂位處理中斷，請再試一次");
                }
            }
        }
        return Result.fail("訂位失敗，請再試一次");
    }

    private TransactionTemplate reserveTransactionTemplate() {
        DefaultTransactionDefinition definition = new DefaultTransactionDefinition();
        definition.setIsolationLevel(TransactionDefinition.ISOLATION_READ_COMMITTED);
        definition.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRED);
        return new TransactionTemplate(transactionManager, definition);
    }

    private LocalDate today() {
        return LocalDate.now(BUSINESS_ZONE);
    }

    private Result reserveInTransaction(Map<String, Object> body) {
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
        if (!bookingDate.isAfter(today())) return Result.fail("訂位日期需為明天或之後");

        String time = bookingTime.toString();
        String table = body.getOrDefault("tableType", "normal").toString();
        if (!table.equals("normal") && !table.equals("bar") && !table.equals("private")) {
            return Result.fail("tableType 僅支援 normal/bar/private");
        }
        String idempotencyKey = body.get("idempotencyKey") != null
                ? body.get("idempotencyKey").toString().trim()
                : null;
        if (idempotencyKey != null && idempotencyKey.isBlank()) idempotencyKey = null;
        if (idempotencyKey != null && idempotencyKey.length() > 120) {
            return Result.fail("idempotencyKey 長度不可超過 120");
        }
        if (idempotencyKey != null) {
            var existing = bookingRepo.findByIdempotencyKey(idempotencyKey).orElse(null);
            if (existing != null) {
                var existingShop = shopService.getById(existing.getShopId());
                String existingShopName = existingShop != null ? existingShop.getName() : null;
                return Result.ok(bookingResponse(existing, existingShopName, true));
            }
            lockIdempotencyKey(idempotencyKey);
            existing = bookingRepo.findByIdempotencyKey(idempotencyKey).orElse(null);
            if (existing != null) {
                var existingShop = shopService.getById(existing.getShopId());
                String existingShopName = existingShop != null ? existingShop.getName() : null;
                return Result.ok(bookingResponse(existing, existingShopName, true));
            }
        }

        // 查訂金政策
        var shop     = shopService.getById(shopId);
        if (shop == null) return Result.fail("店家不存在");
        Integer typeId   = shop != null && shop.getTypeId() != null ? shop.getTypeId().intValue() : null;
        Integer score    = shop != null ? shop.getScore() : null;
        Integer avgPrice = shop != null && shop.getAvgPrice() != null ? shop.getAvgPrice().intValue() : null;
        String  shopName = shop != null ? shop.getName() : null;
        DepositPolicy.Result pol = depositPolicy.evaluate(shopId, shopName, typeId, score, avgPrice);

        ensureSlotInventory(shopId, bookingDate, time, table);
        if (!reserveSlotCapacity(shopId, bookingDate, time, table, people)) {
            return Result.fail("該時段目前已額滿，請選擇其他時間");
        }

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
        booking.setIdempotencyKey(idempotencyKey);

        bookingRepo.saveAndFlush(booking);

        log.info("[Booking] code={} shop={} people={} date={} time={} table={} needsDeposit={} status={}",
                booking.getBookingCode(), shopId, people, bookingDate, time, table,
                pol.isNeedsDeposit(), booking.getStatus());

        return Result.ok(bookingResponse(booking, shopName, false));
    }

    private void lockIdempotencyKey(String idempotencyKey) {
        jdbcTemplate.update(
                """
                INSERT IGNORE INTO tb_booking_idempotency_lock (idempotency_key)
                VALUES (?)
                """,
                idempotencyKey
        );
        jdbcTemplate.queryForObject(
                """
                SELECT idempotency_key
                FROM tb_booking_idempotency_lock
                WHERE idempotency_key = ?
                FOR UPDATE
                """,
                String.class,
                idempotencyKey
        );
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

    private Map<String, Object> bookingResponse(BookingJpa booking, String shopName, boolean idempotentReplay) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("bookingCode", booking.getBookingCode());
        out.put("shopId", booking.getShopId());
        out.put("shopName", shopName != null ? shopName : "店家 " + booking.getShopId());
        out.put("people", booking.getPeople());
        out.put("date", booking.getBookingDate().toString());
        out.put("time", booking.getBookingTime());
        out.put("tableType", booking.getTableType());
        out.put("needsDeposit", booking.getNeedsDeposit());
        out.put("depositTotal", booking.getDepositTotal());
        out.put(
                "status",
                booking.getStatus() == 1
                        ? "PENDING_PAYMENT"
                        : booking.getStatus() == 2 ? "PAID" : "CONFIRMED"
        );
        out.put("idempotentReplay", idempotentReplay);
        return out;
    }

    private void ensureSlotInventory(Long shopId, LocalDate bookingDate, String time, String tableType) {
        jdbcTemplate.update(
                """
                INSERT IGNORE INTO tb_booking_slot_inventory
                    (shop_id, booking_date, booking_time, table_type, capacity, booked_count)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                shopId,
                bookingDate,
                time,
                tableType,
                defaultSlotCapacity(tableType)
        );
    }

    private boolean reserveSlotCapacity(Long shopId, LocalDate bookingDate, String time, String tableType, int people) {
        int updated = jdbcTemplate.update(
                """
                UPDATE tb_booking_slot_inventory
                SET booked_count = booked_count + ?
                WHERE shop_id = ? AND booking_date = ? AND booking_time = ? AND table_type = ?
                  AND booked_count + ? <= capacity
                """,
                people, shopId, bookingDate, time, tableType, people
        );
        return updated == 1;
    }

    private int defaultSlotCapacity(String tableType) {
        return switch (tableType) {
            case "private" -> 4;
            case "bar" -> 6;
            default -> 8;
        };
    }
}
