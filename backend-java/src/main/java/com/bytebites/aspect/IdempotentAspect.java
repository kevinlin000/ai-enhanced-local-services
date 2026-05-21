package com.bytebites.aspect;

import com.bytebites.annotation.Idempotent;
import com.bytebites.exception.IdempotentException;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.core.DefaultParameterNameDiscoverer;
import org.springframework.core.ParameterNameDiscoverer;
import org.springframework.data.redis.core.StringRedisTemplate;
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
public class IdempotentAspect {

    private static final String IDEMPOTENT_KEY_PREFIX = "idem:";
    private static final Pattern TEMPLATE_PATTERN = Pattern.compile("#\\{([^}]+)}");
    private static final Pattern VARIABLE_PATTERN = Pattern.compile("#[a-zA-Z_][a-zA-Z0-9_]*");

    private final StringRedisTemplate stringRedisTemplate;
    private final ExpressionParser expressionParser = new SpelExpressionParser();
    private final ParameterNameDiscoverer parameterNameDiscoverer = new DefaultParameterNameDiscoverer();

    public IdempotentAspect(StringRedisTemplate stringRedisTemplate) {
        this.stringRedisTemplate = stringRedisTemplate;
    }

    @Around("@annotation(idempotent)")
    public Object around(ProceedingJoinPoint joinPoint, Idempotent idempotent) throws Throwable {
        String key = IDEMPOTENT_KEY_PREFIX + resolveKey(joinPoint, idempotent.key());
        Boolean locked = stringRedisTemplate.opsForValue()
                .setIfAbsent(key, "1", idempotent.ttlSeconds(), TimeUnit.SECONDS);
        if (!Boolean.TRUE.equals(locked)) {
            log.debug("idempotent blocked, key={}", key);
            throw new IdempotentException("重複請求，請稍候再試");
        }
        return joinPoint.proceed();
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
