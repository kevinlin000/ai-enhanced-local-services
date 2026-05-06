package com.hmdp.service.impl;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.bean.copier.CopyOptions;
import cn.hutool.core.lang.UUID;
import cn.hutool.core.util.RandomUtil;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.hmdp.dto.LoginFormDTO;
import com.hmdp.dto.Result;
import com.hmdp.dto.UserDTO;
import com.hmdp.entity.User;
import com.hmdp.mapper.UserMapper;
import com.hmdp.service.IUserService;
import com.hmdp.utils.RegexUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import javax.servlet.http.HttpSession;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import static com.hmdp.utils.RedisConstants.*;
import static com.hmdp.utils.SystemConstants.USER_NICK_NAME_PREFIX;

/**
 * <p>
 * 服务实现类
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@Slf4j
@Service
public class UserServiceImpl extends ServiceImpl<UserMapper, User> implements IUserService {

    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Override
    public Result sendCode(String phone, HttpSession session) {
        //1.檢驗手機號碼
        if (RegexUtils.isPhoneInvalid(phone)) {
            //2. 如果不符合，返回錯誤資訊
            return Result.fail("手機號碼格式錯誤");
        }
        //3. 符合，生成驗證碼
        String code = RandomUtil.randomNumbers(6);
        //4. 保存驗證碼到redis set key value ex 120
        stringRedisTemplate.opsForValue().set(LOGIN_CODE_KEY + phone, code, LOGIN_CODE_TTL, java.util.concurrent.TimeUnit.MINUTES);

        //5. 發送驗證碼
        log.debug("發送簡訊驗證碼成功：{}", code);
        //6. 返回ok
        return Result.ok();
    }

    @Override
    public Result login(LoginFormDTO loginForm, HttpSession session) {
        //1.檢驗手機號碼
        String phone = loginForm.getPhone();
        if (RegexUtils.isPhoneInvalid(phone)) {
            //2. 如果不符合，返回錯誤資訊
            return Result.fail("手機號碼格式錯誤");
        }
        //3. 從redis獲取驗證碼並檢驗
        String cacheCode = stringRedisTemplate.opsForValue().get(LOGIN_CODE_KEY + phone);
        String code = loginForm.getCode();
        if(cacheCode == null || !cacheCode.equals(code)){
            //3. 不一致就報錯
            return Result.fail("驗證碼錯誤");

        }

        //4. 一致，根據手機號碼查詢用戶 select * from tb_user where phone = ?
        User user = query().eq("phone", phone).one();
        //5. 判斷用戶是否存在
        if (user == null) {
        //6. 不存在，創建新用戶並保存
                user = createUserWithPhone(phone);
        }

        //7. 保存用戶資訊到redis
        //7.1 隨機生成token作為登錄令牌
        String token = UUID.randomUUID().toString(true);

        //7.2 將User對象轉換為HashMap存儲
        UserDTO userDTO = BeanUtil.copyProperties(user, UserDTO.class);
        Map<String, Object> userMap = BeanUtil.beanToMap(userDTO, new HashMap<>(),
                CopyOptions.create()
                        .setIgnoreNullValue(true)
                        .setFieldValueEditor((fieldName, fieldValue) -> fieldValue.toString()));

        //7.3 存儲數據到redis
        stringRedisTemplate.opsForHash().putAll(LOGIN_USER_KEY + token, userMap);
        String Tokenkey =  LOGIN_USER_KEY + token;
        stringRedisTemplate.opsForHash().putAll(Tokenkey, userMap);
        //7.4 設置token有效期
        stringRedisTemplate.expire(Tokenkey,LOGIN_USER_TTL, TimeUnit.MINUTES);
        //8. 返回token
        return Result.ok(token);
    }

    private User createUserWithPhone(String phone) {
        //1.創建用戶
        User user = new User();
        user.setPhone(phone);
        user.setNickName( USER_NICK_NAME_PREFIX + RandomUtil.randomString(10));
        //2.保存用戶
        save(user);
        return user;
    }


}
