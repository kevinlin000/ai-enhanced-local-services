package com.bytebites.controller;


import com.bytebites.annotation.Idempotent;
import com.bytebites.annotation.RateLimit;
import com.bytebites.dto.Result;
import com.bytebites.domain.jpa.VoucherOrderJpa;
import com.bytebites.repository.VoucherOrderJpaRepository;
import com.bytebites.service.IVoucherOrderService;
import com.bytebites.utils.UserHolder;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;

import jakarta.annotation.Resource;

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

    @PostMapping("seckill/{id}")
    @Idempotent(key = "seckill:#voucherId", ttlSeconds = 5)
    @RateLimit(key = "secKill:#voucherId", capacity = 100, refillPerSecond = 10)
    public Result seckillVoucher(@PathVariable("id") Long voucherId) {
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
        return Result.ok(result.getContent());
    }
}
