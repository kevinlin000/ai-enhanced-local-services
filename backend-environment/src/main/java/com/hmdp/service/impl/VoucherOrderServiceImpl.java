package com.hmdp.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.hmdp.dto.Result;
import com.hmdp.entity.SeckillVoucher;
import com.hmdp.entity.VoucherOrder;
import com.hmdp.mapper.VoucherOrderMapper;
import com.hmdp.service.ISeckillVoucherService;
import com.hmdp.service.IVoucherOrderService;
import com.hmdp.utils.RedisIdWorker;
import com.hmdp.utils.UserHolder;
import org.springframework.aop.framework.AopContext;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;
import java.time.LocalDateTime;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@Service
public class VoucherOrderServiceImpl extends ServiceImpl<VoucherOrderMapper, VoucherOrder> implements IVoucherOrderService {


    @Resource
    private ISeckillVoucherService seckillVoucherService;

    @Resource
    private RedisIdWorker redisIdWorker;

    @Override
    public Result seckillVoucher(Long voucherId) {
        // 1.查詢優惠券
        SeckillVoucher voucher = seckillVoucherService.getById(voucherId);
        //2.判斷秒殺是否開始
        if (voucher.getBeginTime().isAfter(LocalDateTime.now())) {
            //尚未開始
            return Result.fail("秒殺尚未開始！");
        }
        //3.判斷秒殺是否結束
        if (voucher.getEndTime().isBefore(LocalDateTime.now())) {
            //已經結束
            return Result.fail("秒殺已經結束！");
        }

        //4.判斷庫存是否充足
        if (voucher.getStock() < 1) {
            //庫存不足
            return Result.fail("庫存不足！");
        }

        Long userId = UserHolder.getUser().getId();
        synchronized (userId.toString().intern()) {
            // 獲取代理對象（事務）
            IVoucherOrderService proxy = (IVoucherOrderService) AopContext.currentProxy();
            return proxy.createVoucherOrder(voucherId);
        }
    }

    @Transactional
    public  Result createVoucherOrder(Long voucherId){
            // 5.一人一單
            Long userId = UserHolder.getUser().getId();


            // 5.1 查詢訂單
            long count = query().eq("user_id", userId).eq("voucher_id", voucherId).count();
            // 5.2 判斷訂單是否存在
            if (count > 0) {
                //用戶已經購買過了
                return Result.fail("用戶已經購買過一次了！");
            }

            //6.扣減庫存
            boolean success = seckillVoucherService.update()
                    .setSql("stock = stock - 1") //set stock = stock - 1
                    .eq("voucher_id", voucherId).gt("stock", 0) // where id = ? and stock >0
                    .update();
            if (!success) {
                //扣減失敗
                return Result.fail("庫存不足！");
            }

            //7.創建訂單
            VoucherOrder voucherOrder = new VoucherOrder();
            //7.1 訂單id
            long orderId = redisIdWorker.nextId("order");
            voucherOrder.setId(orderId);

            //7.2 用戶id

            voucherOrder.setUserId(userId);
            //7.3 優惠券id
            voucherOrder.setVoucherId(voucherId);
            save(voucherOrder);
            //8.返回訂單id
            return Result.ok(orderId);
        }
    }

