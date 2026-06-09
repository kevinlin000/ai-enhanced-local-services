package com.bytebites.service;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

class TaxonomyMigrationResourceTest {

    @Test
    void v38RemovesMeatNCubesBadKoreanTagOnly() throws Exception {
        String sql = Files.readString(Path.of(
                "src/main/resources/db/migration/V38__remove_meat_n_cubes_bad_korean_tag.sql"
        ));

        assertThat(sql)
                .contains("DELETE FROM tb_shop_tag")
                .contains("tag_code = '韓式'")
                .contains("10175 -- 肉次方 燒肉放題 台北峨眉店");
        assertThat(sql).doesNotContain("UPDATE tb_shop");
    }
}
