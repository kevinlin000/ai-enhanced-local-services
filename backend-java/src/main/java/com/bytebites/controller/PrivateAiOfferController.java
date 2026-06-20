package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.service.PrivateAiOfferService;
import lombok.RequiredArgsConstructor;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RequiredArgsConstructor
@RestController
@RequestMapping({"/private-offers", "/api/private-offers"})
public class PrivateAiOfferController {
    private final PrivateAiOfferService privateAiOfferService;

    @GetMapping("/me")
    public Result myOffers() {
        return privateAiOfferService.myOffers();
    }

    @PostMapping("/match")
    @Transactional
    public Result matchOffers(@RequestBody(required = false) Map<String, Object> body) {
        return privateAiOfferService.matchOffers(body != null ? body : Map.of());
    }

    @PostMapping("/{offerCode}/claim")
    @Transactional
    public Result claimOffer(@PathVariable String offerCode) {
        return privateAiOfferService.claimOffer(offerCode);
    }
}
