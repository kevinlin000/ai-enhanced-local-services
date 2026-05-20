package com.hmdp.config;

import com.hmdp.utils.LoginIntercepter;
import com.hmdp.utils.RefreshTokenIntercepter;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import jakarta.annotation.Resource;

@Configuration
public class MvcConfig implements WebMvcConfigurer {

    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        // NOTE: replaced by Spring Security + JwtAuthenticationFilter (B2)
        // kept here for reference; will be removed after JPA refactor
//        registry.addInterceptor(new LoginIntercepter())
//                .excludePathPatterns(
//                        "/shop/**",
//                        "/shop-type/**",
//                        "/upload/**",
//                        "/voucher/**",
//                        "/blog/hot",
//                        "/user/login",
//                        "/user/code"
//                ).order(1);
//        registry.addInterceptor(new RefreshTokenIntercepter(stringRedisTemplate)).addPathPatterns("/**").order(0);
    }
}
