package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.service.AvailabilityNotificationService;
import lombok.RequiredArgsConstructor;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.Map;

@RequiredArgsConstructor
@RestController
@RequestMapping({"/availability", "/api/availability"})
public class AvailabilityController {
    private final AvailabilityNotificationService availability;

    @PostMapping("/watches")
    @Transactional
    public Result createWatch(@RequestBody Map<String, Object> body) {
        try {
            Long shopId = Long.valueOf(body.get("shopId").toString());
            LocalDate date = LocalDate.parse(body.get("date").toString());
            String time = body.get("time").toString();
            String tableType = String.valueOf(body.getOrDefault("tableType", "normal"));
            int people = Integer.parseInt(body.getOrDefault("people", 2).toString());
            String lineUserId = body.get("lineUserId") == null ? null : body.get("lineUserId").toString();
            return availability.createWatch(shopId, date, time, tableType, people, lineUserId);
        } catch (NullPointerException | NumberFormatException | DateTimeParseException ex) {
            return Result.fail("watch 格式錯誤，請確認 shopId/date/time/people");
        }
    }

    @GetMapping("/watches")
    @Transactional
    public Result myWatches() {
        return availability.myWatches();
    }

    @PostMapping("/watches/{id}/cancel")
    @Transactional
    public Result cancelWatch(@PathVariable Long id) {
        return availability.cancelWatch(id);
    }

    @GetMapping("/notifications")
    public Result myNotifications() {
        return availability.myNotifications();
    }

    @PostMapping("/notifications/{id}/read")
    public Result markRead(@PathVariable Long id) {
        return availability.markRead(id);
    }

    @PostMapping("/notifications/read-all")
    public Result markAllRead() {
        return availability.markAllRead();
    }
}
