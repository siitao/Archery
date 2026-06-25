/**
 * MySQL 权限元数据（4 级 × 数据/结构/管理 分组）。
 * 从旧版 sql/templates/instanceaccount.html:270-912 提取，配置驱动渲染授权矩阵。
 * grant 接口 priv_type：0=global / 1=db / 2=tb / 3=col。
 */

export interface PrivGroup {
  group: "数据" | "结构" | "管理";
  privs: string[];
}

export interface PrivLevelMeta {
  level: "global" | "db" | "tb" | "col";
  groups: PrivGroup[];
}

/** global 级（最全） */
const GLOBAL: PrivGroup[] = [
  {
    group: "数据",
    privs: ["SELECT", "INSERT", "UPDATE", "DELETE", "FILE"],
  },
  {
    group: "结构",
    privs: [
      "CREATE",
      "ALTER",
      "INDEX",
      "DROP",
      "CREATE TEMPORARY TABLES",
      "SHOW VIEW",
      "CREATE ROUTINE",
      "ALTER ROUTINE",
      "EXECUTE",
      "CREATE VIEW",
      "EVENT",
      "TRIGGER",
    ],
  },
  {
    group: "管理",
    privs: [
      "GRANT",
      "SUPER",
      "PROCESS",
      "RELOAD",
      "SHUTDOWN",
      "SHOW DATABASES",
      "LOCK TABLES",
      "REFERENCES",
      "REPLICATION CLIENT",
      "REPLICATION SLAVE",
      "CREATE USER",
    ],
  },
];

/** db 级（库级，19 项） */
const DB: PrivGroup[] = [
  {
    group: "数据",
    privs: ["SELECT", "INSERT", "UPDATE", "DELETE"],
  },
  {
    group: "结构",
    privs: [
      "CREATE",
      "ALTER",
      "INDEX",
      "DROP",
      "CREATE TEMPORARY TABLES",
      "SHOW VIEW",
      "CREATE ROUTINE",
      "ALTER ROUTINE",
      "EXECUTE",
      "CREATE VIEW",
      "EVENT",
      "TRIGGER",
      "REFERENCES",
      "LOCK TABLES",
    ],
  },
  {
    group: "管理",
    privs: ["GRANT"],
  },
];

/** tb 级（表级，13 项） */
const TB: PrivGroup[] = [
  {
    group: "数据",
    privs: ["SELECT", "INSERT", "UPDATE", "DELETE"],
  },
  {
    group: "结构",
    privs: [
      "CREATE",
      "ALTER",
      "INDEX",
      "DROP",
      "CREATE VIEW",
      "SHOW VIEW",
      "TRIGGER",
      "REFERENCES",
    ],
  },
  {
    group: "管理",
    privs: ["GRANT"],
  },
];

/** col 级（列级，4 项，仅数据类） */
const COL: PrivGroup[] = [
  {
    group: "数据",
    privs: ["SELECT", "INSERT", "UPDATE", "REFERENCES"],
  },
];

export const MYSQL_PRIVILEGES: PrivLevelMeta[] = [
  { level: "global", groups: GLOBAL },
  { level: "db", groups: DB },
  { level: "tb", groups: TB },
  { level: "col", groups: COL },
];

export const PRIV_LEVEL_LABEL: Record<PrivLevelMeta["level"], string> = {
  global: "全局",
  db: "库",
  tb: "表",
  col: "列",
};
