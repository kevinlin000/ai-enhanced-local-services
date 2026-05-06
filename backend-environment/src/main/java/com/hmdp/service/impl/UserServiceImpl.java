package com.hmdp.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.hmdp.dto.Result;
import com.hmdp.entity.User;
import com.hmdp.mapper.UserMapper;
import com.hmdp.service.IUserService;
import com.hmdp.utils.RegexUtils;
import org.springframework.stereotype.Service;

import javax.servlet.http.HttpSession;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@Service
public class UserServiceImpl extends ServiceImpl<UserMapper, User> implements IUserService {

    @Override
    public Result sendCode(String phone, HttpSession session) {
        //1.檢驗手機號碼
        if (RegexUtils.isPhoneInvalid(phone)) {
            
        }
        //2. 如果不符合，返回錯誤資訊

        //3. 符合，生成驗證碼

        //4. 保存驗證碼到session

        //5. 發送驗證碼

        //6. 返回ok
        return Result.ok();
    }
}
