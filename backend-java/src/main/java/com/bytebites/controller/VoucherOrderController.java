package com.bytebites.controller;


import com.bytebites.annotation.RateLimit;
import com.bytebites.dto.Result;
import com.bytebites.domain.jpa.ShopJpa;
import com.bytebites.domain.jpa.VoucherJpa;
import com.bytebites.domain.jpa.VoucherOrderJpa;
import com.bytebites.repository.ShopJpaRepository;
import com.bytebites.repository.VoucherJpaRepository;
import com.bytebites.repository.VoucherOrderJpaRepository;
import com.bytebites.service.IVoucherOrderService;
import com.bytebites.utils.UserHolder;
import io.micrometer.core.instrument.Counter;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;

import jakarta.annotation.Resource;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;

/**
 * <p>
 *  前端控制器
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@RestController
@RequestMapping("/voucher-order")
public class VoucherOrderController {

    @Resource
    private IVoucherOrderService voucherOrderService;
    @Resource
    private VoucherOrderJpaRepository voucherOrderJpaRepo;
    @Resource
    private VoucherJpaRepository voucherJpaRepo;
    @Resource
    private ShopJpaRepository shopJpaRepo;
    @Resource
    private Counter seckillAttempts;

    @PostMapping("seckill/{id}")
    @RateLimit(key = "secKill:#voucherId", capacity = 100, refillPerSecond = 10)
    public Result seckillVoucher(@PathVariable("id") Long voucherId) {
        seckillAttempts.increment();
        return voucherOrderService.seckillVoucher(voucherId);
    }

    @GetMapping("/of/user")
    public Result listMyOrders(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size
    ) {
        Long userId = UserHolder.getUser().getId();
        Page<VoucherOrderJpa> result = voucherOrderJpaRepo
                .findByUserIdOrderByCreateTimeDesc(userId, PageRequest.of(page - 1, size));

        // 補上餐券與店家資訊，讓「我的餐券」頁不用逐張查詢
        List<Long> voucherIds = result.getContent().stream()
                .map(VoucherOrderJpa::getVoucherId)
                .distinct()
                .toList();
        Map<Long, VoucherJpa> vouchers = voucherJpaRepo.findAllById(voucherIds).stream()
                .collect(Collectors.toMap(VoucherJpa::getId, v -> v));
        List<Long> shopIds = vouchers.values().stream()
                .map(VoucherJpa::getShopId)
                .filter(Objects::nonNull)
                .distinct()
                .toList();
        Map<Long, String> shopNames = shopJpaRepo.findAllById(shopIds).stream()
                .collect(Collectors.toMap(ShopJpa::getId, ShopJpa::getName));

        List<Map<String, Object>> enriched = result.getContent().stream()
                .map(order -> {
                    VoucherJpa voucher = vouchers.get(order.getVoucherId());
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("id", String.valueOf(order.getId()));
                    row.put("voucherId", order.getVoucherId());
                    row.put("status", order.getStatus());
                    row.put("createTime", order.getCreateTime());
                    row.put("payTime", order.getPayTime());
                    row.put("useTime", order.getUseTime());
                    if (voucher != null) {
                        row.put("title", voucher.getTitle());
                        row.put("subTitle", voucher.getSubTitle());
                        row.put("rules", voucher.getRules());
                        row.put("payValue", voucher.getPayValue());
                        row.put("actualValue", voucher.getActualValue());
                        row.put("shopId", voucher.getShopId());
                        row.put("shopName", shopNames.get(voucher.getShopId()));
                    }
                    return row;
                })
                .toList();
        return Result.ok(enriched);
    }
}
