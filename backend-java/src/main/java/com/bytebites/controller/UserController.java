package com.bytebites.controller;


import cn.hutool.core.bean.BeanUtil;
import com.bytebites.dto.LoginFormDTO;
import com.bytebites.dto.Result;
import com.bytebites.dto.UserDTO;
import com.bytebites.entity.User;
import com.bytebites.entity.UserInfo;
import com.bytebites.service.IUserInfoService;
import com.bytebites.service.IUserService;
import com.bytebites.utils.UserHolder;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;

/**
 * <p>
 * 前端控制器
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@Slf4j
@RestController
@RequestMapping({"/user", "/api/user"})
public class UserController {

    @Resource
    private IUserService userService;

    @Resource
    private IUserInfoService userInfoService;

    /**
     * @deprecated Replaced by LINE Login in B2.
     * Endpoint kept temporarily for backward compatibility during transition.
     * Will be removed in v1.1.
     * 发送手机验证码
     */
    @Deprecated
    @PostMapping("code")
    public Result sendCode(@RequestParam("phone") String phone, HttpSession session) {
        // 发送短信验证码并保存验证码
        return userService.sendCode(phone, session);
    }

    /**
     * @deprecated Replaced by LINE Login in B2.
     * Endpoint kept temporarily for backward compatibility during transition.
     * Will be removed in v1.1.
     * 登录功能
     * @param loginForm 登录参数，包含手机号、验证码；或者手机号、密码
     */
    @Deprecated
    @PostMapping("/login")
    public Result login(@RequestBody LoginFormDTO loginForm, HttpSession session){
        // 实现登录功能
        return userService.login(loginForm, session);
    }

    /**
     * 登出功能
     * @return 无
     */
    @PostMapping("/logout")
    public Result logout(HttpServletRequest request){
        String token = request.getHeader("authorization");
        return userService.logout(token);
    }

    @GetMapping("/me")
    public Result me(){
        // 获取当前登录的用户并返回
        UserDTO user = UserHolder.getUser();
        return Result.ok(user);
    }

    @GetMapping("/info/{id}")
    public Result info(@PathVariable("id") Long userId){
        // 查询详情
        UserInfo info = userInfoService.getById(userId);
        if (info == null) {
            // 没有详情，应该是第一次查看详情
            return Result.ok();
        }
        info.setCreateTime(null);
        info.setUpdateTime(null);
        // 返回
        return Result.ok(info);
    }
    @GetMapping("/{id}")
    public Result queryUserById(@PathVariable("id")Long userId){
        User user = userService.getById(userId);
        if (user==null){
            return Result.ok();
        }
        UserDTO userDTO = BeanUtil.copyProperties(user, UserDTO.class);
        return Result.ok(userDTO);
    }

    @PostMapping("/sign")
    public Result sign(){
        return userService.sign();
    }

    @PostMapping("/sign/count")
    public Result signCount(){
        return userService.signCount();
    }

}
