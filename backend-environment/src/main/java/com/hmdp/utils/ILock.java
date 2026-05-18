package com.hmdp.utils;

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
