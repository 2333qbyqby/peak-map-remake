# 本地解包与 90% 校准

这个流程只处理你合法持有的本地副本。导出内容放在
`references/private/`，该目录已经由 `.gitignore` 排除。

## 1. 本地查看 Unity 资源

可使用 [AssetRipper 官方仓库](https://github.com/AssetRipper/AssetRipper)
分析 Unity 序列化文件。只在本机查看场景、TerrainData、Mesh 和物件
Transform；不要把导出的官方资源提交到本仓库，也不要复制反编译实现。

推荐记录聚合数据：

- TerrainData 的分辨率、尺寸和高度数组；
- 场景中岩体的包围盒、位置、旋转、缩放和地貌标签；
- 每类物件在高度、坡度、曲率区间内的数量分布；
- 地貌边界和每个高度槽位的范围；
- 可见表面采样点或自行渲染的深度图。

## 2. 制作私有参考 bundle

最低要求：

```text
references/private/map-001/
└── height.png
```

`height.png` 可以是 16-bit 灰度高度图。若原场景主要由 Mesh 组成，先在
Unity/Blender 中从正上方向表面投射，生成统一坐标系下的高度图。洞穴和
悬垂需要额外的点云/深度图指标；首版评分只覆盖可见上表面。

## 3. 评分

```bash
island-baker score \
  --generated build/island \
  --reference references/private/map-001
```

完整 bundle 的总分为几何 75% + 物件 25%。几何分内部由以下部分组成：

| 指标 | 权重 |
|---|---:|
| 对齐后的高度 RMSE | 30% |
| 梯度/坡向一致性 | 20% |
| 岛屿轮廓 IoU | 8% |
| 多尺度形状相关性 | 14% |
| 高度分布一致性 | 8% |
| 局部高频细节 | 20% |

物件分内部为总量 20%、类别分布 25%、径向-高度分布 40%、尺度分布
15%。如果私有参考没有 `spawn_manifest.json`，报告只给几何分，并不会
假装评估了岩体/植被分布。

方向会在 4 次旋转和镜像组合中自动选择，单位缩放和高度偏移由最小二乘
对齐。只有 `passes_90_percent=true` 才能声称该参考样本达到 90%。

## 4. 自动校准

```bash
island-baker calibrate \
  --reference references/private/map-001 \
  --trials 32 \
  --output build/calibrated
```

首版会搜索种子和两组可替换地貌。下一阶段应把你记录的 spawner 统计
加入损失函数，并用 Bayesian optimization 调整 profile 参数。
