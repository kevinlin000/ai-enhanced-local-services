package com.hmdp.utils;

/**
 * 手刻分散式鎖介面（教學用，非生產代碼）。
 * <p>
 * 本介面保留作為對照範例，實際生產使用請見 {@link org.redisson.api.RLock}。
 */
@Deprecated
public interface ILock {

    /**
     * 嘗試獲取鎖
     */
    boolean tryLock(long timeoutSec);


    /**
     * 釋放鎖
     */
    void unlock();

}
