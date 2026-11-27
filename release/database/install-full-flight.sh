#!/bin/bash
# 为旧安装补装大飞过程；首次初始化使用同一脚本。
set -eu
. /secrets/environment
export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"
mysql_root=(mysql --protocol=socket -uroot)
installed=$("${mysql_root[@]}" --batch --skip-column-names -e "
  SELECT COUNT(*) FROM information_schema.ROUTINES
  WHERE ROUTINE_SCHEMA='wendao_gm_web' AND ROUTINE_NAME='insert_flight_shape' AND ROUTINE_TYPE='PROCEDURE'
")
if [ "$installed" = 0 ]; then
  "${mysql_root[@]}" < /entry/install-full-flight.sql
fi
"${mysql_root[@]}" -e "GRANT EXECUTE ON PROCEDURE wendao_gm_web.insert_flight_shape TO 'wendao_gm'@'%';"
