-- Backfill mrt_station and mrt_distance_meters for google_places shops
-- using haversine formula (radius 800 m, nearest station wins)
-- tb_mrt_station: x = longitude, y = latitude
-- tb_shop:        x = longitude, y = latitude

UPDATE tb_shop s
SET
    mrt_station = (
        SELECT m.name
        FROM tb_mrt_station m
        WHERE (
            6371000 * ACOS(
                COS(RADIANS(s.y)) * COS(RADIANS(m.y)) *
                COS(RADIANS(m.x) - RADIANS(s.x)) +
                SIN(RADIANS(s.y)) * SIN(RADIANS(m.y))
            )
        ) < 800
        ORDER BY (
            6371000 * ACOS(
                COS(RADIANS(s.y)) * COS(RADIANS(m.y)) *
                COS(RADIANS(m.x) - RADIANS(s.x)) +
                SIN(RADIANS(s.y)) * SIN(RADIANS(m.y))
            )
        ) ASC
        LIMIT 1
    ),
    mrt_distance_meters = (
        SELECT FLOOR(
            6371000 * ACOS(
                COS(RADIANS(s.y)) * COS(RADIANS(m.y)) *
                COS(RADIANS(m.x) - RADIANS(s.x)) +
                SIN(RADIANS(s.y)) * SIN(RADIANS(m.y))
            )
        )
        FROM tb_mrt_station m
        WHERE (
            6371000 * ACOS(
                COS(RADIANS(s.y)) * COS(RADIANS(m.y)) *
                COS(RADIANS(m.x) - RADIANS(s.x)) +
                SIN(RADIANS(s.y)) * SIN(RADIANS(m.y))
            )
        ) < 800
        ORDER BY (
            6371000 * ACOS(
                COS(RADIANS(s.y)) * COS(RADIANS(m.y)) *
                COS(RADIANS(m.x) - RADIANS(s.x)) +
                SIN(RADIANS(s.y)) * SIN(RADIANS(m.y))
            )
        ) ASC
        LIMIT 1
    )
WHERE s.source = 'google_places' AND s.is_active = 1;
