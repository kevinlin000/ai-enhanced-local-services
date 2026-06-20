package com.bytebites.service;

import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.entity.Shop;
import com.bytebites.utils.UserHolder;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.startsWith;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class PrivateAiOfferServiceTest {
    private static final Long USER_ID = 1012L;
    private static final Long SHOP_ID = 10009L;

    @Mock
    private JdbcTemplate jdbcTemplate;
    @Mock
    private IShopService shopService;

    private PrivateAiOfferService service;

    @BeforeEach
    void setUp() {
        service = new PrivateAiOfferService(jdbcTemplate, shopService);
        UserDTO user = new UserDTO();
        user.setId(USER_ID);
        UserHolder.saveUser(user);
    }

    @AfterEach
    void tearDown() {
        UserHolder.removeUser();
    }

    @Test
    void matchOffersCreatesPrivateOffPeakOfferForLoggedInUser() {
        when(jdbcTemplate.queryForList(anyString(), eq(USER_ID), eq(SHOP_ID))).thenReturn(List.of());
        when(shopService.getById(SHOP_ID)).thenReturn(shop());

        Result result = service.matchOffers(Map.of(
                "shopIds", List.of(SHOP_ID),
                "trigger", "OFF_PEAK_FILL",
                "people", 2,
                "targetTime", "17:00"
        ));

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data).containsEntry("created", true).containsEntry("triggerReason", "OFF_PEAK_FILL");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> offers = (List<Map<String, Object>>) data.get("offers");
        assertThat(offers).hasSize(1);
        assertThat(offers.get(0))
                .containsEntry("shopId", SHOP_ID)
                .containsEntry("shopName", "橘色涮涮屋 信義館")
                .containsEntry("title", "AI 私密離峰 9 折")
                .containsEntry("discountPercent", 10)
                .containsEntry("minPeople", 2)
                .containsEntry("status", "ACTIVE");
        assertThat(String.valueOf(offers.get(0).get("offerCode"))).startsWith("PO-");
        verify(jdbcTemplate).update(
                anyString(),
                eq(USER_ID),
                eq(SHOP_ID),
                startsWith("PO-"),
                eq("AI 私密離峰 9 折"),
                anyString(),
                eq("OFF_PEAK_FILL"),
                eq("OFF_PEAK_FILL"),
                eq(10),
                eq(2),
                any(LocalDateTime.class)
        );
    }

    @Test
    void matchOffersReusesExistingActiveOfferInsteadOfCreatingDuplicate() {
        when(jdbcTemplate.queryForList(anyString(), eq(USER_ID), eq(SHOP_ID))).thenReturn(List.of(existingOfferRow()));

        Result result = service.matchOffers(Map.of(
                "shopIds", List.of(SHOP_ID),
                "trigger", "SAVE_MONEY_INTENT"
        ));

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data).containsEntry("created", false);
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> offers = (List<Map<String, Object>>) data.get("offers");
        assertThat(offers).hasSize(1);
        assertThat(offers.get(0))
                .containsEntry("offerCode", "PO-EXISTING")
                .containsEntry("title", "AI 私密省錢 9 折")
                .containsEntry("status", "ACTIVE");
    }

    @Test
    void matchOffersRejectsAnonymousUser() {
        UserHolder.removeUser();

        Result result = service.matchOffers(Map.of("shopIds", List.of(SHOP_ID), "trigger", "OFF_PEAK_FILL"));

        assertThat(result.getSuccess()).isFalse();
        assertThat(result.getErrorMsg()).contains("登入");
    }

    private Map<String, Object> existingOfferRow() {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", 7L);
        row.put("shopId", SHOP_ID);
        row.put("shopName", "橘色涮涮屋 信義館");
        row.put("offerCode", "PO-EXISTING");
        row.put("title", "AI 私密省錢 9 折");
        row.put("description", "只在此帳號顯示");
        row.put("triggerReason", "SAVE_MONEY_INTENT");
        row.put("offerType", "PRIVATE_MATCH");
        row.put("discountPercent", 10);
        row.put("minPeople", 1);
        row.put("validUntil", LocalDateTime.of(2026, 6, 20, 18, 0));
        row.put("status", "ACTIVE");
        return row;
    }

    private Shop shop() {
        Shop shop = new Shop();
        shop.setId(SHOP_ID);
        shop.setName("橘色涮涮屋 信義館");
        shop.setIsActive(1);
        return shop;
    }
}
