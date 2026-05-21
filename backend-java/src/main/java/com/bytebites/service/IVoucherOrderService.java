package com.bytebites.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.bytebites.dto.Result;
import com.bytebites.entity.VoucherOrder;

/**
 * <p>
 *  服务类
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
public interface IVoucherOrderService extends IService<VoucherOrder> {

    Result seckillVoucher(Long voucherId);

    void createVoucherOrder(VoucherOrder voucherOrder);
}
