package com.bytebites.controller;


import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bytebites.dto.Result;
import com.bytebites.entity.SeckillVoucher;
import com.bytebites.entity.Shop;
import com.bytebites.entity.Voucher;
import com.bytebites.entity.jpa.ShopAiMetadataJpa;
import com.bytebites.entity.jpa.ShopAbsaJpa;
import com.bytebites.repository.ShopAiMetadataJpaRepository;
import com.bytebites.repository.ShopAbsaJpaRepository;
import com.bytebites.entity.ShopType;
import com.bytebites.service.DepositPolicy;
import com.bytebites.service.ISeckillVoucherService;
import com.bytebites.service.IShopService;
import com.bytebites.service.IShopTypeService;
import com.bytebites.service.IVoucherService;
import com.bytebites.utils.SystemConstants;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import jakarta.annotation.Resource;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * <p>
 * 前端控制器
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@RestController
@RequestMapping({"/shop", "/api/shop"})
public class ShopController {

    @Resource
    public IShopService shopService;

    @Autowired
    private ShopAiMetadataJpaRepository aiMetadataRepo;

    @Autowired
    private ShopAbsaJpaRepository absaRepo;

    @Resource
    private IVoucherService voucherService;

    @Resource
    private ISeckillVoucherService seckillVoucherService;

    @Autowired
    private DepositPolicy depositPolicy;

    @Resource
    private IShopTypeService shopTypeService;

    /**
     * 根据id查询商铺信息
     * @param id 商铺id
     * @return 商铺详情数据
     */
    @GetMapping("/{id}")
    public Result queryShopById(@PathVariable("id") Long id) {

        return shopService.queryById(id);
    }

    /**
     * 查詢店家訂金政策。
     * 優先從 price_per_person 用 regex 抽最大金額，抽不到時 fallback 到 type_id。
     * 前端 BookingButton 開啟 form 時呼叫。
     */
    @GetMapping("/{id}/booking-policy")
    public Result bookingPolicy(@PathVariable("id") Long id) {
        Shop shop = shopService.getById(id);
        if (shop == null) return Result.fail("店家不存在");

        Integer typeId   = shop.getTypeId() != null ? shop.getTypeId().intValue() : null;
        Integer score    = shop.getScore();
        Integer avgPrice = shop.getAvgPrice() != null ? shop.getAvgPrice().intValue() : null;

        DepositPolicy.Result r = depositPolicy.evaluate(id, shop.getName(), typeId, score, avgPrice);

        return Result.ok(java.util.Map.of(
                "needsDeposit", r.isNeedsDeposit(),
                "depositPerPerson", r.getDepositPerPerson(),
                "reason", r.getReason(),
                "extractedPrice", r.getExtractedPrice() == null ? "" : r.getExtractedPrice()
        ));
    }

    /**
     * 全文 + 多條件搜尋。
     * q: 店名/地址/區域模糊搜尋
     * typeIds: 分類（可複選）
     * districts: 行政區（可複選）
     * mrtStations: 捷運站（可複選）
     * minScore: 最低評分（整數 ×10，e.g. 45 = 4.5 星）
     */
    @GetMapping("/search")
    public Result search(
            @RequestParam(required = false) String q,
            @RequestParam(required = false) List<Integer> typeIds,
            @RequestParam(required = false) List<String> districts,
            @RequestParam(required = false) List<String> mrtStations,
            @RequestParam(required = false) Integer minScore,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "30") Integer size
    ) {
        LambdaQueryWrapper<Shop> w = new LambdaQueryWrapper<>();
        w.eq(Shop::getIsActive, 1);
        w.eq(Shop::getSource, "google_places");

        if (q != null && !q.isBlank()) {
            w.and(qw -> qw
                    .like(Shop::getName, q)
                    .or().like(Shop::getAddress, q)
                    .or().like(Shop::getDistrict, q)
            );
        }
        if (typeIds != null && !typeIds.isEmpty()) {
            w.in(Shop::getTypeId, typeIds);
        }
        if (districts != null && !districts.isEmpty()) {
            w.in(Shop::getDistrict, districts);
        }
        if (mrtStations != null && !mrtStations.isEmpty()) {
            w.in(Shop::getMrtStation, mrtStations);
        }
        if (minScore != null) {
            w.ge(Shop::getScore, minScore);
        }
        w.orderByDesc(Shop::getScore);

        Page<Shop> p = shopService.page(new Page<>(page, size), w);

        return Result.ok(java.util.Map.of(
                "records", p.getRecords(),
                "total", p.getTotal(),
                "current", p.getCurrent(),
                "size", p.getSize()
        ));
    }

    /**
     * Filter 左欄聚合：回傳每個 filter 選項與對應店家數量。
     * 前端 ShopSearchPage 初始化時呼叫一次。
     */
    @GetMapping("/filter-options")
    public Result filterOptions() {
        LambdaQueryWrapper<Shop> w = new LambdaQueryWrapper<>();
        w.eq(Shop::getIsActive, 1);
        w.eq(Shop::getSource, "google_places");
        List<Shop> all = shopService.list(w);

        // type_id → count
        java.util.Map<Integer, Long> typeCounts = all.stream()
                .filter(s -> s.getTypeId() != null)
                .collect(Collectors.groupingBy(s -> s.getTypeId().intValue(), Collectors.counting()));

        // district → count
        java.util.Map<String, Long> districtCounts = all.stream()
                .filter(s -> s.getDistrict() != null && !s.getDistrict().isBlank())
                .collect(Collectors.groupingBy(Shop::getDistrict, Collectors.counting()));

        // mrt_station → count
        java.util.Map<String, Long> mrtCounts = all.stream()
                .filter(s -> s.getMrtStation() != null && !s.getMrtStation().isBlank())
                .collect(Collectors.groupingBy(Shop::getMrtStation, Collectors.counting()));

        // type names
        java.util.Map<Integer, String> typeNames = shopTypeService.list().stream()
                .collect(Collectors.toMap(t -> t.getId().intValue(), ShopType::getName, (a, b) -> a));

        List<java.util.Map<String, Object>> typeOptions = typeCounts.entrySet().stream()
                .map(e -> java.util.Map.<String, Object>of(
                        "id", e.getKey(),
                        "name", typeNames.getOrDefault(e.getKey(), "未知"),
                        "count", e.getValue()
                ))
                .sorted((a, b) -> Long.compare((Long) b.get("count"), (Long) a.get("count")))
                .toList();

        List<java.util.Map<String, Object>> districtOptions = districtCounts.entrySet().stream()
                .map(e -> java.util.Map.<String, Object>of("name", e.getKey(), "count", e.getValue()))
                .sorted((a, b) -> Long.compare((Long) b.get("count"), (Long) a.get("count")))
                .toList();

        List<java.util.Map<String, Object>> mrtOptions = mrtCounts.entrySet().stream()
                .map(e -> java.util.Map.<String, Object>of("name", e.getKey(), "count", e.getValue()))
                .sorted((a, b) -> Long.compare((Long) b.get("count"), (Long) a.get("count")))
                .toList();

        return Result.ok(java.util.Map.of(
                "types", typeOptions,
                "districts", districtOptions,
                "mrtStations", mrtOptions,
                "totalShops", all.size()
        ));
    }

    /**
     * 新增商铺信息
     * @param shop 商铺数据
     * @return 商铺id
     */
    @PostMapping
    public Result saveShop(@RequestBody Shop shop) {
        // 写入数据库
        shopService.save(shop);
        // 返回店铺id
        return Result.ok(shop.getId());
    }

    /**
     * 更新商铺信息
     * @param shop 商铺数据
     * @return 无
     */
    @PutMapping
    public Result updateShop(@RequestBody Shop shop) {
        // 写入数据库
        return shopService.update(shop);
    }

    /**
     * 根据商铺类型分页查询商铺信息
     * @param typeId 商铺类型
     * @param current 页码
     * @return 商铺列表
     */
    @GetMapping("/of/type")
    public Result queryShopByType(
            @RequestParam("typeId") Integer typeId,
            @RequestParam(value = "current", defaultValue = "1") Integer current,
            @RequestParam(value = "x", required = false) Double x,
            @RequestParam(value = "y", required = false) Double y
    ) {
        return shopService.queryShopByType(typeId, current, x, y);
    }

    /**
     * 根据商铺名称关键字分页查询商铺信息
     * @param name 商铺名称关键字
     * @param current 页码
     * @return 商铺列表
     */
    @GetMapping("/of/name")
    public Result queryShopByName(
            @RequestParam(value = "name", required = false) String name,
            @RequestParam(value = "current", defaultValue = "1") Integer current
    ) {
        // 根据类型分页查询
        Page<Shop> page = shopService.query()
                .like(StrUtil.isNotBlank(name), "name", name)
                .page(new Page<>(current, SystemConstants.MAX_PAGE_SIZE));
        // 返回数据
        return Result.ok(page.getRecords());
    }

    @GetMapping("/list")
    public Result listShops(@RequestParam(value = "current", defaultValue = "1") Integer current) {
        Page<Shop> page = shopService.query()
                .page(new Page<>(current, SystemConstants.MAX_PAGE_SIZE));
        return Result.ok(page.getRecords());
    }

    @GetMapping("/count")
    public Result countActiveShops() {
        long count = shopService.count(new QueryWrapper<Shop>().eq("is_active", 1));
        return Result.ok(count);
    }

    @GetMapping("/{id}/ai-metadata")
    public Result aiMetadata(@PathVariable("id") Long id) {
        return aiMetadataRepo.findById(id)
                .map(Result::ok)
                .orElse(Result.ok(null));
    }

    @GetMapping("/{id}/absa")
    public Result absa(@PathVariable("id") Long id) {
        return absaRepo.findById(id)
                .map(Result::ok)
                .orElse(Result.ok(null));
    }

    @GetMapping({"/{id}/hot-seat-vouchers", "/{id}/flash-deals"})
    public Result hotSeatVouchers(@PathVariable("id") Long id) {
        List<Voucher> vouchers = voucherService.list(
                new LambdaQueryWrapper<Voucher>()
                        .eq(Voucher::getShopId, id)
                        .eq(Voucher::getType, 1)
                        .eq(Voucher::getStatus, 1)
        );
        if (vouchers.isEmpty()) return Result.ok(Collections.emptyList());

        List<Long> voucherIds = vouchers.stream().map(Voucher::getId).toList();
        List<SeckillVoucher> seckillList = seckillVoucherService.list(
                new LambdaQueryWrapper<SeckillVoucher>()
                        .in(SeckillVoucher::getVoucherId, voucherIds)
                        .gt(SeckillVoucher::getStock, 0)
        );

        Map<Long, Integer> stockMap = seckillList.stream()
                .collect(Collectors.toMap(SeckillVoucher::getVoucherId, SeckillVoucher::getStock));
        Map<Long, SeckillVoucher> seckillMap = seckillList.stream()
                .collect(Collectors.toMap(SeckillVoucher::getVoucherId, s -> s));

        Set<Long> activeIds = stockMap.keySet();
        List<Map<String, Object>> result = vouchers.stream()
                .filter(v -> activeIds.contains(v.getId()))
                .map(v -> {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("id", v.getId());
                    m.put("title", v.getTitle());
                    m.put("sub_title", v.getSubTitle());
                    m.put("rules", v.getRules());
                    m.put("pay_value", v.getPayValue());
                    m.put("actual_value", v.getActualValue());
                    m.put("stock", stockMap.getOrDefault(v.getId(), 0));
                    SeckillVoucher seckill = seckillMap.get(v.getId());
                    m.put("begin_time", seckill == null ? null : seckill.getBeginTime());
                    m.put("end_time", seckill == null ? null : seckill.getEndTime());
                    m.put("label", "限時餐券");
                    return m;
                })
                .toList();

        return Result.ok(result);
    }
}
