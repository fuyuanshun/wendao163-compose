-- 由数据库维护账号安装。后台只获得此过程的执行权限。
DELIMITER $$
CREATE PROCEDURE wendao_gm_web.insert_flight_shape(
    IN role_gid VARBINARY(32),
    IN shape_content BLOB,
    IN saved_at CHAR(14),
    IN save_checksum INT
)
MODIFIES SQL DATA
SQL SECURITY DEFINER
BEGIN
    -- 固定原生角色和形态分支，只允许已有角色新增一次，事务由调用方控制。
    IF role_gid IS NULL OR role_gid NOT REGEXP '^[A-Za-z0-9_]{1,32}$'
       OR shape_content IS NULL
       OR LEFT(shape_content, 19) <> 0x285b22757067726164655f617474726962223a
       OR saved_at IS NULL OR saved_at NOT REGEXP '^[0-9]{14}$'
       OR save_checksum IS NULL
       OR NOT EXISTS (
            SELECT 1 FROM dl_ddb_1.data
            WHERE path = 'user' AND name = role_gid AND branch = ''
       ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid flight shape';
    END IF;
    INSERT INTO dl_ddb_1.data(path, name, branch, content, time, checksum)
    VALUES ('user', role_gid, 'upgrade', shape_content, saved_at, save_checksum);
END$$
DELIMITER ;
