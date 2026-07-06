package com.bytebites.service.impl;

import cn.hutool.core.bean.BeanUtil;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.bytebites.domain.jpa.VoucherOrderJpa;
import com.bytebites.dto.Result;
import com.bytebites.entity.VoucherOrder;
import com.bytebites.mapper.VoucherOrderMapper;
import com.bytebites.repository.VoucherOrderJpaRepository;
import com.bytebites.service.ISeckillVoucherService;
import com.bytebites.service.IVoucherOrderService;
import com.bytebites.utils.RedisIdWorker;
import com.bytebites.utils.UserHolder;
import lombok.extern.slf4j.Slf4j;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.springframework.context.annotation.Lazy;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.connection.stream.*;
import org.springframework.data.redis.core.RedisCallback;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import jakarta.annotation.Resource;
import java.nio.charset.StandardCharsets;
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

    private static final String ORDER_STREAM = "stream.orders";
    private static final String ORDER_GROUP = "g1";
    private static final String ORDER_CONSUMER = "c1";
    private static final long RETRY_DELAY_MILLIS = 1_000L;

    @Resource
    private ISeckillVoucherService seckillVoucherService;

    @Resource
    private RedisIdWorker redisIdWorker;

    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Resource
    private RedissonClient redissonClient;

    @Resource
    private VoucherOrderJpaRepository voucherOrderJpaRepo;

    @Lazy
    @Resource
    private IVoucherOrderService proxy;

    private static final DefaultRedisScript<Long> SECKILL_SCRIPT;
    static {
        SECKILL_SCRIPT = new DefaultRedisScript<>();
        SECKILL_SCRIPT.setLocation(new ClassPathResource("seckill.lua"));
        SECKILL_SCRIPT.setResultType(Long.class);
    }

    private static final ExecutorService SECKILL_ORDER_EXECUTOR = Executors.newSingleThreadExecutor();
    private volatile boolean running = true;

    @PostConstruct
    private void init() {
        try {
            ensureOrderStreamGroup();
        } catch (RuntimeException e) {
            log.warn("餐券訂單串流初始化失敗，consumer 將重試：{}", conciseMessage(e));
        }
        SECKILL_ORDER_EXECUTOR.submit(new VoucherOrderHandler());
    }

    void ensureOrderStreamGroup() {
        try {
            stringRedisTemplate.execute((RedisCallback<String>) connection ->
                    connection.streamCommands().xGroupCreate(
                            ORDER_STREAM.getBytes(StandardCharsets.UTF_8),
                            ORDER_GROUP,
                            ReadOffset.from("0"),
                            true
                    )
            );
        } catch (RuntimeException e) {
            if (!containsMessage(e, "BUSYGROUP")) throw e;
        }
    }

    @PreDestroy
    private void destroy() {
        running = false;
        SECKILL_ORDER_EXECUTOR.shutdownNow();
    }

        private class VoucherOrderHandler implements Runnable {
        String queueName = ORDER_STREAM;
        @Override
        public void run() {
            while (running && !Thread.currentThread().isInterrupted()) {
                try {
                    //1.從消息隊列中獲取訂單資訊
                    List<MapRecord<String, Object, Object>> list = stringRedisTemplate.opsForStream().read(
                            Consumer.from(ORDER_GROUP, ORDER_CONSUMER),
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
                    stringRedisTemplate.opsForStream().acknowledge(queueName, ORDER_GROUP, record.getId());
                } catch (Exception e) {
                    if (!running || Thread.currentThread().isInterrupted()) {
                        return;
                    }
                    log.warn("餐券訂單串流處理失敗，稍後重試：{}", conciseMessage(e));
                    try {
                        ensureOrderStreamGroup();
                    } catch (RuntimeException groupError) {
                        log.warn("餐券訂單 consumer group 尚未就緒：{}", conciseMessage(groupError));
                    }
                    pauseBeforeRetry();
                    handlePendingList();
                }
            }
        }

            private void handlePendingList() {
                while (running && !Thread.currentThread().isInterrupted()) {
                    try {
                        //1.從pending list中獲取訂單資訊
                        List<MapRecord<String, Object, Object>> list = stringRedisTemplate.opsForStream().read(
                                Consumer.from(ORDER_GROUP, ORDER_CONSUMER),
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
                        stringRedisTemplate.opsForStream().acknowledge(queueName, ORDER_GROUP, record.getId());
                    } catch (Exception e) {
                        if (!running || Thread.currentThread().isInterrupted()) {
                            return;
                        }
                        log.warn("餐券 pending 訂單處理失敗，稍後重試：{}", conciseMessage(e));
                        pauseBeforeRetry();
                        return;
                    }
                }
            }
        }

    private void pauseBeforeRetry() {
        try {
            Thread.sleep(RETRY_DELAY_MILLIS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static boolean containsMessage(Throwable error, String value) {
        for (Throwable current = error; current != null; current = current.getCause()) {
            if (current.getMessage() != null && current.getMessage().contains(value)) return true;
        }
        return false;
    }

    private static String conciseMessage(Throwable error) {
        Throwable current = error;
        while (current.getCause() != null) current = current.getCause();
        return current.getMessage() == null ? current.getClass().getSimpleName() : current.getMessage();
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
            VoucherOrderJpa jpaOrder = new VoucherOrderJpa();
            BeanUtil.copyProperties(voucherOrder, jpaOrder);
            if (jpaOrder.getPayType() == null) jpaOrder.setPayType(1);
            if (jpaOrder.getStatus() == null) jpaOrder.setStatus(1);
            voucherOrderJpaRepo.save(jpaOrder);
        }
    }
