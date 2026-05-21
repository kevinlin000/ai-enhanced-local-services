package com.bytebites.config;

import com.bytebites.dto.Result;
import com.bytebites.exception.IdempotentException;
import com.bytebites.exception.LockAcquireException;
import com.bytebites.exception.RateLimitException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Slf4j
@RestControllerAdvice
public class WebExceptionAdvice {

    @ExceptionHandler(LockAcquireException.class)
    public ResponseEntity<Result> handleLockAcquireException(LockAcquireException e) {
        return ResponseEntity.status(HttpStatus.LOCKED).body(Result.fail("資源忙碌中"));
    }

    @ExceptionHandler(IdempotentException.class)
    public ResponseEntity<Result> handleIdempotentException(IdempotentException e) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(Result.fail("重複請求，請稍候再試"));
    }

    @ExceptionHandler(RateLimitException.class)
    public ResponseEntity<Result> handleRateLimitException(RateLimitException e) {
        return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS).body(Result.fail(e.getMessage()));
    }

    @ExceptionHandler(RuntimeException.class)
    public Result handleRuntimeException(RuntimeException e) {
        log.error(e.toString(), e);
        return Result.fail("服务器异常");
    }
}
