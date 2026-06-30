package com.bytebites.controller;

import com.bytebites.dto.Result;
import com.bytebites.service.IVoucherOrderService;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class FlashDealControllerTest {

    private final IVoucherOrderService voucherOrderService = mock(IVoucherOrderService.class);
    private final FlashDealController controller = new FlashDealController(voucherOrderService);

    @Test
    void claimWrapsQueuedFlashDealOrder() {
        when(voucherOrderService.seckillVoucher(30101L)).thenReturn(Result.ok(99123L));

        Result result = controller.claim(30101L);

        assertThat(result.getSuccess()).isTrue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) result.getData();
        assertThat(data)
                .containsEntry("dealId", 30101L)
                .containsEntry("orderId", 99123L)
                .containsEntry("status", "QUEUED")
                .containsEntry("message", "限時餐券已搶到，訂單建立中");
    }

    @Test
    void claimKeepsSeckillFailureMessage() {
        when(voucherOrderService.seckillVoucher(30101L)).thenReturn(Result.fail("庫存不足"));

        Result result = controller.claim(30101L);

        assertThat(result.getSuccess()).isFalse();
        assertThat(result.getErrorMsg()).isEqualTo("庫存不足");
    }
}
