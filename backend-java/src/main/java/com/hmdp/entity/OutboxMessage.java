package com.hmdp.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.experimental.Accessors;

import java.io.Serializable;
import java.time.LocalDateTime;

@Data
@EqualsAndHashCode(callSuper = false)
@Accessors(chain = true)
@TableName("outbox_message")
public class OutboxMessage implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    private String aggregateType;

    private Long aggregateId;

    private String eventType;

    private String payload;

    private String routingKey;

    private String exchange;

    private Integer status;

    private Integer retryCount;

    @TableField("created_at")
    private LocalDateTime createdAt;

    @TableField("sent_at")
    private LocalDateTime sentAt;
}
