package com.hmdp.service.impl;

import cn.hutool.core.bean.BeanUtil;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.hmdp.dto.Result;
import com.hmdp.entity.VoucherOrder;
import com.hmdp.mapper.VoucherOrderMapper;
import com.hmdp.service.ISeckillVoucherService;
import com.hmdp.service.IVoucherOrderService;
import com.hmdp.utils.RedisIdWorker;
import com.hmdp.utils.UserHolder;
import lombok.extern.slf4j.Slf4j;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.springframework.aop.framework.AopContext;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.connection.stream.*;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.Resource;
import java.time.Duration;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 */
@Slf4j
@Service
public class VoucherOrderServiceImpl extends ServiceImpl<VoucherOrderMapper, VoucherOrder> implements IVoucherOrderService {


    @Resource
    private ISeckillVoucherService seckillVoucherService;

    @Resource
    private RedisIdWorker redisIdWorker;

    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Resource
    private RedissonClient redissonClient;

    private static final DefaultRedisScript<Long> SECKILL_SCRIPT;
    static {
        SECKILL_SCRIPT = new DefaultRedisScript<>();
        SECKILL_SCRIPT.setLocation(new ClassPathResource("seckill.lua"));
        SECKILL_SCRIPT.setResultType(Long.class);
    }

    private static final ExecutorService SECKILL_ORDER_EXECUTOR = Executors.newSingleThreadExecutor();

    @PostConstruct
    private void init() {
        SECKILL_ORDER_EXECUTOR.submit(new VoucherOrderHandler());
    }

        private class VoucherOrderHandler implements Runnable {
        String queueName = "stream.orders";
        @Override
        public void run() {
            while (true) {
                try {
                    //1.從消息隊列中獲取訂單資訊
                    List<MapRecord<String, Object, Object>> list = stringRedisTemplate.opsForStream().read(
                            Consumer.from("g1", "c1"),
                            StreamReadOptions.empty().count(1).block(Duration.ofSeconds(2)),
                            StreamOffset.create(queueName, ReadOffset.lastConsumed())
                    );//2.判斷消息獲取是否成功
                     if (list == null || list.isEmpty()) {
                         //2.1如果獲取失敗，代表沒有消息，繼續下一次循環
                        continue;
                    }
                     MapRecord<String, Object, Object> record = list.get(0);
                     Map<Object, Object> value = record.getValue();
                     VoucherOrder voucherOrder = BeanUtil.fillBeanWithMap(value, new VoucherOrder(), true);
                    //3.如果獲取成功，創建訂單
                    handleVoucherOrder(voucherOrder);
                    //4.ACK確認
                    stringRedisTemplate.opsForStream().acknowledge(queueName, "g1", record.getId());
                } catch (Exception e) {
                    log.error("處理訂單異常", e);
                    handlePendingList();
                }
            }
        }

            private void handlePendingList() {
                while (true) {
                    try {
                        //1.從pending list中獲取訂單資訊
                        List<MapRecord<String, Object, Object>> list = stringRedisTemplate.opsForStream().read(
                                Consumer.from("g1", "c1"),
                                StreamReadOptions.empty().count(1),
                                StreamOffset.create(queueName, ReadOffset.from("0"))
                        );//2.判斷消息獲取是否成功
                        if (list == null || list.isEmpty()) {
                            //2.1如果獲取失敗，代表pending list沒有異常消息，結束循環
                            break;
                        }
                        MapRecord<String, Object, Object> record = list.get(0);
                        Map<Object, Object> value = record.getValue();
                        VoucherOrder voucherOrder = BeanUtil.fillBeanWithMap(value, new VoucherOrder(), true);
                        //3.如果獲取成功，創建訂單
                        handleVoucherOrder(voucherOrder);
                        //4.ACK確認
                        stringRedisTemplate.opsForStream().acknowledge(queueName, "g1", record.getId());
                    } catch (Exception e) {
                        log.error("處理訂單異常", e);
                        try {
                            Thread.sleep(20);
                        } catch (InterruptedException ex) {
                            throw new RuntimeException(ex);
                        }
                    }
                }
            }
        }

    private void handleVoucherOrder(VoucherOrder voucherOrder) {
        //獲取用戶
        Long userId = voucherOrder.getUserId();
        //創建鎖對象
        RLock lock = redissonClient.getLock("lock:order:" + userId);
        // 獲取鎖
        boolean isLock = lock.tryLock();
        if (!isLock) {
            // 獲取鎖失敗，返回錯誤或是重試
            log.error("不允許重複下單");
            return ;
        }
        try {
            proxy.createVoucherOrder(voucherOrder);
        } finally {
            // 釋放鎖
            lock.unlock();
        }
    }
    private IVoucherOrderService proxy;
    @Override
    public Result seckillVoucher(Long voucherId) {
        //獲取用戶
        Long userId = UserHolder.getUser().getId();
        //獲取訂單id
        long orderId = redisIdWorker.nextId("order");
        //1.執行lua腳本
        Long result = stringRedisTemplate.execute(
                SECKILL_SCRIPT,
                Collections.emptyList(),
                voucherId.toString(), userId.toString(), String.valueOf(orderId)
        );
        int r = result == null ? -1 : result.intValue();
        if (r == 1) {
            return Result.fail("庫存不足");
        }
        if (r == 2) {
            return Result.fail("不能重複下單");
        }
        if (r != 0) {
            return Result.fail("下單失敗");
        }

        //3. 獲取代理對象
        proxy = (IVoucherOrderService) AopContext.currentProxy();
        //3.返回訂單id
        return Result.ok(orderId);
    }

    @Transactional
    public void createVoucherOrder(VoucherOrder voucherOrder){
            // 5.一人一單
            Long userId = voucherOrder.getUserId();


            // 5.1 查詢訂單
            long count = query().eq("user_id", userId).eq("voucher_id", voucherOrder.getVoucherId()).count();
            // 5.2 判斷訂單是否存在
            if (count > 0) {
                //用戶已經購買過了
                log.error("用戶已經購買過一次了！");
                return;
            }

            //6.扣減庫存
            boolean success = seckillVoucherService.update()
                    .setSql("stock = stock - 1") //set stock = stock - 1
                    .eq("voucher_id", voucherOrder.getVoucherId()).gt("stock", 0) // where id = ? and stock >0
                    .update();
            if (!success) {
                //扣減失敗
                log.error("庫存不足！");
                return;
            }

            //7.創建訂單
            save(voucherOrder);
        }
    }
