# 调研结论与算法映射

更新时间：2026-07-29。

## 能确认的事实

1. PEAK 官方页面说明岛屿布局每 24 小时轮换一次。
2. 开发者 AMA 对生成方式的描述很直接：地图不是先规划一条保证可攀的路线，而是以多个调好参数的 spawner 做“受控随机”；大范围墙体让玩家可以横向寻找更容易的区域，物品则允许越过局部不可攀区域。
3. 当前地貌结构可抽象成六个高度槽位：海岸；雨林/巨木林二选一；雪山/台地荒漠二选一；熔岩湖；火山内部；山顶。仓库因此提供八个通用 profile，但一次完整岛屿使用六个。
4. 社区技术文章称制作过程使用约 1200 Unity 单位高的基础阶梯，先生成并放置大型岩体，再放中型、小型岩体和物件，之后预烘焙并随版本分发。这个尺寸和具体顺序属于二手资料，必须用本地合法导出的数据再次验证，不能当作官方源码事实。
5. 官方 Fan Creation Policy 不允许把官方资产直接复制、分发或让作品看起来像官方产品。因此本仓库不含官方模型、贴图、场景、Logo 或反编译源码。

## 从事实到实现

| 观察 | 独立实现 |
|---|---|
| 基础阶梯 | 六段软量化的径向高度场 |
| 多个调参 spawner | 每个地貌独立密度、坡度和间距约束 |
| 大石到小石逐层覆盖 | large → medium → small → vegetation 顺序布点 |
| 不强制设计路线 | `analyze` 默认只测量路线，不修改地形 |
| 道具可跨越坏段 | `repair` 可选模式生成攀爬点占位物 |
| 离线烘焙 | 16-bit 高度图、RAW、法线、AO、OBJ、物件清单 |
| 多种每日地图 | 种子决定一切，四种地貌轮换可批量烘焙 |

## 资料来源

- [Landfall：PEAK 官方页面](https://landfall.se/peak)
- [PEAK 开发者 AMA：地图生成回答](https://www.reddit.com/r/PeakGame/comments/1m5s7ei/we_are_some_of_the_devs_behind_peak_ama/)
- [PEAK Wiki：Locations](https://peak.wiki.gg/wiki/Locations)
- [PEAK Wiki：Shore](https://peak.wiki.gg/wiki/Shore)
- [PEAK Wiki：Tropics](https://peak.wiki.gg/wiki/Tropics)
- [PEAK Wiki：Roots](https://peak.wiki.gg/wiki/Roots)
- [PEAK Wiki：Alpine](https://peak.wiki.gg/wiki/Alpine)
- [PEAK Wiki：Mesa](https://peak.wiki.gg/wiki/Mesa)
- [PEAK Wiki：Caldera](https://peak.wiki.gg/wiki/Caldera)
- [PEAK Wiki：The Kiln](https://peak.wiki.gg/wiki/The_Kiln)
- [PEAK Wiki：Peak](https://peak.wiki.gg/wiki/Peak_%28biome%29)
- [二手技术拆解：Inside PEAK's Daily Map Generation System](https://hackernoon.com/inside-peaks-daily-map-generation-system)
- [PEAK Fan Creation Policy](https://landfall.se/peak-fan-policy)

## 尚不能从公开资料证明的部分

- 原始 spawner 数量、随机分布、碰撞检测和 prefab 权重；
- 每个烘焙场景的精确尺寸、基准网格和遮蔽贴图格式；
- 每张官方地图的高度场与物件变换；
- “90%”是否已达到。

最后一项只能在用户提供合法的本地参考导出后，由仓库内的相似度脚本计算。

