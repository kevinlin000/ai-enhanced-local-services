package com.bytebites.utils;

import org.springframework.web.servlet.HandlerInterceptor;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

public class LoginIntercepter implements HandlerInterceptor {

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        //1.判斷是否需要攔截（ThreadLocal 中是否有用戶）
        if(UserHolder.getUser() == null) {
            //2.沒有，返回401狀態碼
            response.setStatus(401);
            // 攔截
            return false;
        }
        //3.有用戶，放行
        return true;
    }

}
