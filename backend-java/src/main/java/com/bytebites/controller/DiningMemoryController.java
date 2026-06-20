package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.service.DiningMemoryService;
import lombok.RequiredArgsConstructor;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RequiredArgsConstructor
@RestController
@RequestMapping({"/dining-memory", "/api/dining-memory"})
public class DiningMemoryController {
    private final DiningMemoryService diningMemoryService;

    @GetMapping("/me")
    public Result myMemory() {
        return diningMemoryService.myMemory();
    }

    @PostMapping("/bookings/{bookingCode}")
    @Transactional
    public Result saveBookingMemory(
            @PathVariable String bookingCode,
            @RequestBody(required = false) Map<String, Object> body
    ) {
        return diningMemoryService.saveBookingMemory(bookingCode, body != null ? body : Map.of());
    }
}
