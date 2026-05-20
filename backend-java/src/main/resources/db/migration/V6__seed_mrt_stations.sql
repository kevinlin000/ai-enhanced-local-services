-- V6: seed taipei mrt stations for geo search

CREATE TABLE IF NOT EXISTS tb_mrt_station (
    id BIGINT PRIMARY KEY,
    name VARCHAR(50) NOT NULL COMMENT 'station name',
    line VARCHAR(50) NOT NULL COMMENT 'mrt line name',
    x DOUBLE NOT NULL COMMENT 'longitude',
    y DOUBLE NOT NULL COMMENT 'latitude',
    district VARCHAR(20) NOT NULL COMMENT 'district name',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name)
) COMMENT='taipei mrt stations';

INSERT INTO tb_mrt_station (id, name, line, x, y, district) VALUES
    (1, '信義安和', '淡水信義線', 121.5527, 25.0331, '信義區'),
    (2, '象山', '淡水信義線', 121.5704, 25.0327, '信義區'),
    (3, '市政府', '板南線', 121.5670, 25.0408, '信義區'),
    (4, '台北101/世貿', '淡水信義線', 121.5615, 25.0335, '信義區'),
    (5, '中山', '淡水信義線', 121.5234, 25.0526, '中山區'),
    (6, '雙連', '淡水信義線', 121.5210, 25.0578, '大同區'),
    (7, '行天宮', '中和新蘆線', 121.5333, 25.0625, '中山區'),
    (8, '中山國小', '中和新蘆線', 121.5283, 25.0612, '中山區');
