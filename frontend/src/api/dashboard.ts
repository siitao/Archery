import request from "@/utils/request";

/** Dashboard 图表数据（GET /api/v1/dashboard/charts/）。
 * bar/line: {x: string[], series: {name,data}[]}；pie: {name,value}[]。 */

export interface ChartSeries {
  name: string;
  data: (number | string)[];
}
export interface BarLineChart {
  x: string[];
  series: ChartSeries[];
}
export interface PieDatum {
  name: string;
  value: number | string;
}

export interface DashboardCharts {
  bar1: BarLineChart; // SQL 上线数量（按日）
  bar2: BarLineChart; // SQL 上线用户
  bar3: BarLineChart; // 慢查询 db 维度
  bar5: BarLineChart; // SQL 上线工单
  pie1: PieDatum[]; // SQL 上线统计（按组）
  pie2: PieDatum[]; // SQL 语法类型
  pie3: PieDatum[]; // 慢查询 db/user 维度
  pie4: PieDatum[]; // SQL 查询用户
  pie5: PieDatum[]; // DB 检索行数
  line1: BarLineChart; // SQL 查询统计（检索行数 + 检索次数）
}

export function fetchDashboardCharts(startDate: string, endDate: string) {
  return request
    .get<DashboardCharts>("/api/v1/dashboard/charts/", {
      params: { start_date: startDate, end_date: endDate },
    })
    .then((res) => res.data);
}
