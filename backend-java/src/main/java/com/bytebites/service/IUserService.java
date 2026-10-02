package com.bytebites.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.bytebites.dto.LoginFormDTO;
import com.bytebites.dto.Result;
import com.bytebites.entity.User;
import com.bytebites.service.oauth.LineOAuthService;

import jakarta.servlet.http.HttpSession;

/**
 * <p>
 *  服务类
 * </p>
 */
public interface IUserService extends IService<User> {

    Result sendCode(String phone, HttpSession session);

    Result login(LoginFormDTO loginForm, HttpSession session);

    String loginWithLine(LineOAuthService.LineProfile profile);

    Result logout(String token);

    Result sign();

    Result signCount();
}
