

import pandas as pd
from pyecharts import options as opts
from pyecharts.charts import Bar, HeatMap, Page
from pyecharts.commons.utils import JsCode

# ============================================================
# 1. 读取数据
# ============================================================
df = pd.read_csv(
    "./新媒体运营数据.csv",
    encoding="utf-8-sig",
)

print("=" * 60)
print("[读入数据] 新媒体运营数据.csv")
print("=" * 60)
print(f"总记录数: {len(df)}")
print(f"列名: {list(df.columns)}")
print()

# ============================================================
# 2. 整体统计概览
# ============================================================
print("=" * 60)
print("[整体统计]")
print("=" * 60)
print(df["月薪"].describe().apply(lambda x: f"元{x:,.0f}"))
print()
print("按学历分组统计:")
print(df.groupby("学历")["月薪"].describe().map(lambda x: f"元{x:,.0f}").to_string())
print()
print("按是否AI岗位分组统计:")
print(df.groupby("是否AI岗位")["月薪"].describe().map(lambda x: f"元{x:,.0f}").to_string())

# ============================================================
# 3. 透视表 (Pivot Table)
# ============================================================
print()
print("=" * 60)
print("[透视表] 学历 x AI/非AI 交叉薪资表（均值，元）")
print("=" * 60)
pivot = df.pivot_table(
    values="月薪",
    index="学历",
    columns="是否AI岗位",
    aggfunc=["mean", "count"],
)
pivot_mean = df.pivot_table(values="月薪", index="学历", columns="是否AI岗位", aggfunc="mean")
pivot_mean = pivot_mean.reindex(["大专", "本科", "硕士", "博士"])
print(pivot_mean.to_string())
print()
print("透视表解读:")
print("  - 横向看(同行): 相同学历，AI岗薪资 > 普通岗 → 规律2")
print("  - 纵向看(同列): 学历越高，薪资越高 → 规律1")
print("  - 右下角(博士+AI): 数值最大，是左上角(大专+非AI)的约4-5倍 → 规律3")

# ============================================================
# 4. 绘制图表 (pyecharts 交互式图表)
# ============================================================

# ---- 调色板 ----
CAT_BLUE   = "#2a78d6"
CAT_ORANGE = "#eb6834"
SEQ_BLUE_250 = "#86b6ef"  # 大专
SEQ_BLUE_400 = "#3987e5"  # 本科
SEQ_BLUE_550 = "#1c5cab"  # 硕士
SEQ_BLUE_700 = "#0d366b"  # 博士

EDU_ORDER = ["大专", "本科", "硕士", "博士"]
EDU_COLORS = [SEQ_BLUE_250, SEQ_BLUE_400, SEQ_BLUE_550, SEQ_BLUE_700]

# ---- 准备数据 ----
# 各学历×岗位类型均值
cross_mean = df.groupby(["学历", "是否AI岗位"])["月薪"].mean().round(0).unstack()
cross_mean = cross_mean.reindex(EDU_ORDER)
cross_mean.columns = ["非AI", "AI"]

# 选取有全学历数据的代表岗位（规律1用）
pos_edu_counts = df.groupby(["岗位名称", "学历"]).size().unstack().notna().sum(axis=1)
full_coverage_pos = pos_edu_counts[pos_edu_counts == 4].index.tolist()

# 从数据中推断哪些是AI岗位（避免硬编码岗位列表）
ai_positions_in_data = df[df["是否AI岗位"] == "是"]["岗位名称"].unique().tolist()
normal_positions_in_data = [p for p in full_coverage_pos if p not in ai_positions_in_data]
rep_normal = normal_positions_in_data[:2]
rep_ai = [p for p in full_coverage_pos if p in ai_positions_in_data][:2]
rep_positions = rep_normal + rep_ai

# Chart 1 数据: 代表岗位 x 学历
chart1_data = {}
for pos in rep_positions:
    sub = df[df["岗位名称"] == pos].groupby("学历")["月薪"].mean().round(0)
    chart1_data[pos] = [int(sub.get(edu, 0)) for edu in EDU_ORDER]

# Chart 2 数据: 学历 x AI/非AI
chart2_normal = [int(cross_mean.loc[edu, "非AI"]) for edu in EDU_ORDER]
chart2_ai     = [int(cross_mean.loc[edu, "AI"])   for edu in EDU_ORDER]

# Chart 3 热力图数据
heatmap_pairs = []
for i, edu in enumerate(EDU_ORDER):
    heatmap_pairs.append(["非AI岗位", edu, int(cross_mean.loc[edu, "非AI"])])
    heatmap_pairs.append(["AI岗位",  edu, int(cross_mean.loc[edu, "AI"])])

# ===========================================================
# 图表1: 规律1 — 同一岗位不同学历薪资
# ===========================================================
bar1 = Bar(init_opts=opts.InitOpts(width="900px", height="500px", bg_color="#fcfcfb"))
bar1.add_xaxis(rep_positions)

for i, edu in enumerate(EDU_ORDER):
    bar1.add_yaxis(
        edu,
        [chart1_data[pos][i] for pos in rep_positions],
        color=EDU_COLORS[i],
        label_opts=opts.LabelOpts(
            position="top",
            formatter="{c}",
            font_size=10,
            color="#898781",
        ),
        gap="0%",
        category_gap="40%",
    )

bar1.set_global_opts(
    title_opts=opts.TitleOpts(
        title="规律1: 同一岗位不同学历 → 学历越高薪资越高",
        subtitle="选取4个代表岗位（含2个AI岗），对比各学历段平均月薪",
        title_textstyle_opts=opts.TextStyleOpts(font_size=16, color="#0b0b0b", font_weight="bold"),
        subtitle_textstyle_opts=opts.TextStyleOpts(font_size=12, color="#898781"),
        pos_left="center",
    ),
    legend_opts=opts.LegendOpts(
        textstyle_opts=opts.TextStyleOpts(font_size=12),
        pos_top="bottom",
    ),
    tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="shadow"),
    yaxis_opts=opts.AxisOpts(
        name="月薪 (元)",
        name_textstyle_opts=opts.TextStyleOpts(color="#898781"),
        axislabel_opts=opts.LabelOpts(formatter="{value}"),
    ),
    xaxis_opts=opts.AxisOpts(
        axislabel_opts=opts.LabelOpts(font_size=11, color="#0b0b0b"),
    ),
)

# ===========================================================
# 图表2: 规律2 — 相同学历 AI vs 普通
# ===========================================================
diff_pcts = [round((a - n) / n * 100, 1) for n, a in zip(chart2_normal, chart2_ai)]

bar2 = Bar(init_opts=opts.InitOpts(width="800px", height="500px", bg_color="#fcfcfb"))
bar2.add_xaxis(EDU_ORDER)

bar2.add_yaxis(
    "非AI岗位",
    chart2_normal,
    color=CAT_BLUE,
    label_opts=opts.LabelOpts(position="top", formatter="{c}", font_size=11, color="#898781"),
    gap="0%",
    category_gap="30%",
)
bar2.add_yaxis(
    "AI岗位",
    chart2_ai,
    color=CAT_ORANGE,
    label_opts=opts.LabelOpts(position="top", formatter="{c}", font_size=11, color="#898781"),
    gap="0%",
    category_gap="30%",
)

bar2.set_global_opts(
    title_opts=opts.TitleOpts(
        title="规律2: 相同学历 AI岗位 vs 普通岗位薪资",
        subtitle=f"AI岗位溢价: 大专+{diff_pcts[0]}% / 本科+{diff_pcts[1]}% / 硕士+{diff_pcts[2]}% / 博士+{diff_pcts[3]}%",
        title_textstyle_opts=opts.TextStyleOpts(font_size=16, color="#0b0b0b", font_weight="bold"),
        subtitle_textstyle_opts=opts.TextStyleOpts(font_size=12, color="#eb6834"),
        pos_left="center",
    ),
    legend_opts=opts.LegendOpts(
        textstyle_opts=opts.TextStyleOpts(font_size=12),
        pos_top="bottom",
    ),
    tooltip_opts=opts.TooltipOpts(
        trigger="axis",
        axis_pointer_type="shadow",
        formatter=JsCode(
            """function(params) {
                var s = '<b>' + params[0].axisValue + '</b><br/>';
                for (var i = 0; i < params.length; i++) {
                    s += '<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:'
                      + params[i].color + ';margin-right:6px;"></span>';
                    s += params[i].seriesName + ': <b>' + params[i].value.toLocaleString() + '</b> 元<br/>';
                }
                return s;
            }"""
        ),
    ),
    yaxis_opts=opts.AxisOpts(
        name="月薪 (元)",
        name_textstyle_opts=opts.TextStyleOpts(color="#898781"),
        axislabel_opts=opts.LabelOpts(formatter="{value}"),
    ),
    xaxis_opts=opts.AxisOpts(
        axislabel_opts=opts.LabelOpts(font_size=12, color="#0b0b0b"),
    ),
)

# ===========================================================
# 图表3: 透视表热力图 — 学历 x 岗位类型
# ===========================================================
heatmap_data_vals = cross_mean.values
vmin = float(heatmap_data_vals.min())
vmax = float(heatmap_data_vals.max())

heatmap = HeatMap(init_opts=opts.InitOpts(width="800px", height="500px", bg_color="#fcfcfb"))
heatmap.add_xaxis(["非AI岗位", "AI岗位"])
heatmap.add_yaxis(
    "月薪",
    EDU_ORDER,
    heatmap_pairs,
    label_opts=opts.LabelOpts(
        is_show=True,
        position="inside",
        font_size=18,
        font_weight="bold",
        formatter=JsCode(
            f"""function(params) {{
                return params.data[2].toLocaleString();
            }}"""
        ),
        color=JsCode(
            f"""function(params) {{
                var v = params.data[2];
                var ratio = (v - {vmin}) / ({vmax} - {vmin});
                return ratio > 0.55 ? '#ffffff' : '#0b0b0b';
            }}"""
        ),
    ),
)

heatmap.set_global_opts(
    title_opts=opts.TitleOpts(
        title="规律3: 透视表热力图 — 学历 x 岗位类型 平均月薪（元）",
        subtitle="横向: AI > 非AI (规律2)  |  纵向: 学历越高薪资越高 (规律1)  |  右下角博士+AI = 天花板 (规律3)",
        title_textstyle_opts=opts.TextStyleOpts(font_size=16, color="#0b0b0b", font_weight="bold"),
        subtitle_textstyle_opts=opts.TextStyleOpts(font_size=12, color="#898781"),
        pos_left="center",
    ),
    tooltip_opts=opts.TooltipOpts(
        formatter=JsCode(
            """function(params) {
                return '<b>' + params.data[1] + ' — ' + params.data[0] + '</b><br/>'
                     + '平均月薪: <b style="font-size:16px">' + params.data[2].toLocaleString() + '</b> 元';
            }"""
        ),
    ),
    xaxis_opts=opts.AxisOpts(
        type_="category",
        splitarea_opts=opts.SplitAreaOpts(is_show=True, areastyle_opts=opts.AreaStyleOpts(opacity=0)),
        axislabel_opts=opts.LabelOpts(font_size=13, color="#0b0b0b"),
    ),
    yaxis_opts=opts.AxisOpts(
        type_="category",
        splitarea_opts=opts.SplitAreaOpts(is_show=True, areastyle_opts=opts.AreaStyleOpts(opacity=0)),
        axislabel_opts=opts.LabelOpts(font_size=13, color="#0b0b0b"),
    ),
    visualmap_opts=opts.VisualMapOpts(
        min_=vmin,
        max_=vmax,
        orient="horizontal",
        pos_left="center",
        pos_bottom="5%",
        range_color=["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
        textstyle_opts=opts.TextStyleOpts(color="#898781"),
    ),
)

# ===========================================================
# 5. 保存图表
# ===========================================================

chart1_path = "图表1_同岗位学历薪资对比.html"
chart2_path = "图表2_学历AIvs普通薪资对比.html"
chart3_path = "图表3_透视表热力图.html"

bar1.render(chart1_path)
bar2.render(chart2_path)
heatmap.render(chart3_path)

print()
print(f"[图表] 三张 pyecharts 交互式图表已保存:")
print(f"  - {chart1_path}")
print(f"  - {chart2_path}")
print(f"  - {chart3_path}")

# 仪表板: 三图合一
page = Page(layout=Page.SimplePageLayout)
page.add(bar1, bar2, heatmap)

dashboard_path = "新媒体运营图表_仪表板.html"
page.render(dashboard_path)
print(f"[图表] 仪表板(三合一)已保存到: {dashboard_path}")

print()
print("=" * 60)
print("全部完成！生成的文件列表：")
print("  1. 图表1_同岗位学历薪资对比.html    — 规律1")
print("  2. 图表2_学历AIvs普通薪资对比.html  — 规律2")
print("  3. 图表3_透视表热力图.html         — 规律3")
print("  4. 新媒体运营图表_仪表板.html      — 三合一 (推荐!)")
print("=" * 60)
