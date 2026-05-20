package com.hmdp.aspect;

import com.hmdp.annotation.DistributedLock;
import com.hmdp.enums.LockType;
import com.hmdp.exception.LockAcquireException;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.redisson.api.RLock;
import org.redisson.api.RReadWriteLock;
import org.redisson.api.RedissonClient;
import org.springframework.core.DefaultParameterNameDiscoverer;
import org.springframework.core.ParameterNameDiscoverer;
import org.springframework.expression.ExpressionParser;
import org.springframework.expression.spel.standard.SpelExpressionParser;
import org.springframework.expression.spel.support.StandardEvaluationContext;
import org.springframework.stereotype.Component;

import java.lang.reflect.Method;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Slf4j
@Aspect
@Component
public class DistributedLockAspect {

    private static final String LOCK_KEY_PREFIX = "rwlock:";
    private static final Pattern TEMPLATE_PATTERN = Pattern.compile("#\\{([^}]+)}");
    private static final Pattern VARIABLE_PATTERN = Pattern.compile("#[a-zA-Z_][a-zA-Z0-9_\\.]*");

    private final RedissonClient redissonClient;
    private final ExpressionParser expressionParser = new SpelExpressionParser();
    private final ParameterNameDiscoverer parameterNameDiscoverer = new DefaultParameterNameDiscoverer();

    public DistributedLockAspect(RedissonClient redissonClient) {
        this.redissonClient = redissonClient;
    }

    @Around("@annotation(distributedLock)")
    public Object around(ProceedingJoinPoint joinPoint, DistributedLock distributedLock) throws Throwable {
        String key = LOCK_KEY_PREFIX + resolveKey(joinPoint, distributedLock.key());
        RReadWriteLock readWriteLock = redissonClient.getReadWriteLock(key);
        RLock lock = distributedLock.type() == LockType.READ ? readWriteLock.readLock() : readWriteLock.writeLock();

        boolean locked = lock.tryLock(
                distributedLock.waitSeconds(),
                distributedLock.leaseSeconds(),
                TimeUnit.SECONDS
        );
        if (!locked) {
            log.debug("rw lock blocked, key={}, type={}", key, distributedLock.type());
            throw new LockAcquireException("資源忙碌中");
        }

        try {
            return joinPoint.proceed();
        } finally {
            if (lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }

    private String resolveKey(ProceedingJoinPoint joinPoint, String keyExpression) {
        StandardEvaluationContext context = buildContext(joinPoint);
        String templated = resolveTemplateExpressions(keyExpression, context);
        return resolveVariables(templated, context);
    }

    private String resolveTemplateExpressions(String keyExpression, StandardEvaluationContext context) {
        Matcher matcher = TEMPLATE_PATTERN.matcher(keyExpression);
        StringBuffer resolved = new StringBuffer();
        while (matcher.find()) {
            Object value = expressionParser.parseExpression(matcher.group(1)).getValue(context);
            matcher.appendReplacement(resolved, Matcher.quoteReplacement(String.valueOf(value)));
        }
        matcher.appendTail(resolved);
        return resolved.toString();
    }

    private String resolveVariables(String keyExpression, StandardEvaluationContext context) {
        Matcher matcher = VARIABLE_PATTERN.matcher(keyExpression);
        StringBuffer resolved = new StringBuffer();
        while (matcher.find()) {
            String expression = matcher.group();
            Object value = expressionParser.parseExpression(expression).getValue(context);
            matcher.appendReplacement(resolved, Matcher.quoteReplacement(String.valueOf(value)));
        }
        matcher.appendTail(resolved);
        return resolved.toString();
    }

    private StandardEvaluationContext buildContext(ProceedingJoinPoint joinPoint) {
        Method method = ((MethodSignature) joinPoint.getSignature()).getMethod();
        String[] parameterNames = parameterNameDiscoverer.getParameterNames(method);
        Object[] args = joinPoint.getArgs();

        StandardEvaluationContext context = new StandardEvaluationContext();
        if (parameterNames == null) {
            return context;
        }
        for (int i = 0; i < parameterNames.length; i++) {
            context.setVariable(parameterNames[i], args[i]);
        }
        return context;
    }
}
