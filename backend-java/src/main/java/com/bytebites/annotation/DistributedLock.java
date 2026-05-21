package com.bytebites.annotation;

import com.bytebites.enums.LockType;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface DistributedLock {

    String key();

    LockType type();

    long waitSeconds() default 3;

    long leaseSeconds() default 10;
}
