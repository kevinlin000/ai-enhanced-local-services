package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.service.ParkingService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ParkingController {

    private final ParkingService parkingService;

    public ParkingController(ParkingService parkingService) {
        this.parkingService = parkingService;
    }

    @GetMapping("/api/parking/nearby")
    public Result nearbyParking(
            @RequestParam double lng,
            @RequestParam double lat,
            @RequestParam(defaultValue = "800") int radius,
            @RequestParam(defaultValue = "5") int limit
    ) {
        int safeRadius = Math.max(100, Math.min(radius, 2000));
        int safeLimit = Math.max(1, Math.min(limit, 10));
        return Result.ok(parkingService.nearby(lng, lat, safeRadius, safeLimit));
    }
}
