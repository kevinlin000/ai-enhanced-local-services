package com.hmdp.aspect;

import com.hmdp.annotation.RateLimit;
import com.hmdp.exception.RateLimitException;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.core.DefaultParameterNameDiscoverer;
import org.springframework.core.ParameterNameDiscoverer;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.expression.ExpressionParser;
import org.springframework.expression.spel.standard.SpelExpressionParser;
import org.springframework.expression.spel.support.StandardEvaluationContext;
import org.springframework.stereotype.Component;

import java.lang.reflect.Method;
import java.util.Collections;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Slf4j
@Aspect
@Component
public class RateLimitAspect {

    private static final String RATE_LIMIT_KEY_PREFIX = "rate:limit:";
    private static final Pattern SPEL_PATTERN = Pattern.compile("#[a-zA-Z_][a-zA-Z0-9_]*");
    private static final DefaultRedisScript<Long> TOKEN_BUCKET_SCRIPT;

    static {
        TOKEN_BUCKET_SCRIPT = new DefaultRedisScript<>();
        TOKEN_BUCKET_SCRIPT.setLocation(new ClassPathResource("lua/token-bucket.lua"));
        TOKEN_BUCKET_SCRIPT.setResultType(Long.class);
    }

    private final StringRedisTemplate stringRedisTemplate;
    private final ExpressionParser expressionParser = new SpelExpressionParser();
    private final ParameterNameDiscoverer parameterNameDiscoverer = new DefaultParameterNameDiscoverer();

    public RateLimitAspect(StringRedisTemplate stringRedisTemplate) {
        this.stringRedisTemplate = stringRedisTemplate;
    }

    @Around("@annotation(rateLimit)")
    public Object around(ProceedingJoinPoint joinPoint, RateLimit rateLimit) throws Throwable {
        String resolvedKey = RATE_LIMIT_KEY_PREFIX + resolveKey(joinPoint, rateLimit.key());
        long nowSeconds = System.currentTimeMillis() / 1000;

        Long allowed = stringRedisTemplate.execute(
                TOKEN_BUCKET_SCRIPT,
                Collections.singletonList(resolvedKey),
                String.valueOf(rateLimit.capacity()),
                String.valueOf(rateLimit.refillPerSecond()),
                String.valueOf(nowSeconds),
                String.valueOf(rateLimit.tokensNeeded())
        );
        if (!Long.valueOf(1L).equals(allowed)) {
            log.debug("rate limit blocked, key={}", resolvedKey);
            throw new RateLimitException("請稍後再試");
        }
        return joinPoint.proceed();
    }

    private String resolveKey(ProceedingJoinPoint joinPoint, String keyExpression) {
        StandardEvaluationContext context = buildContext(joinPoint);
        Matcher matcher = SPEL_PATTERN.matcher(keyExpression);
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
