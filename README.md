# Vertical Island Baker

一个面向学习与研究的垂直攀爬岛屿离线生成器。它采用 clean-room
实现，不包含官方游戏资产、场景、Logo 或反编译源码。

项目目标不是用一张 Perlin Noise 高度图“看起来差不多”，而是复现一套
可测量的生产流程：

1. 生成六层基础山体；
2. 按地貌规则依次放置大、中、小岩体和生态物件；
3. 分析自然形成的攀爬路线，可选生成补救攀爬点；
4. 烘焙 Unity 可用的高度、法线、遮蔽、网格和物件清单；
5. 用私有参考高度图计算相似度，只有实测通过才报告 90%。

> 当前状态：算法原型、八类地貌参数、烘焙器、Unity 导入器和评测器均已
> 可运行。尚未用原版私有参考集验证到 90%，因此不声称已经达到 90%。

## 地貌覆盖

一次完整岛屿包含六个高度槽位，其中第二、第三槽各有一个轮换地貌：

| 槽位 | 内置通用 profile |
|---|---|
| 1 | `coast` |
| 2 | `rainforest` / `redwood` |
| 3 | `alpine` / `mesa` |
| 4 | `caldera` |
| 5 | `kiln` |
| 6 | `summit` |

四种轮换组合覆盖八个 profile。参数定义在
`src/vertical_island_baker/config.py`。

仓库内的 `examples/sample/` 保存了可直接查看的遮罩、清单、统计与预览；
体积较大的 `terrain.obj` 未提交，可按样例目录中的命令重新生成。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

烘焙单张地图：

```bash
island-baker bake \
  --seed 20260729 \
  --second rainforest \
  --third alpine \
  --route-mode analyze \
  --output build/island
```

生成覆盖所有地貌的四张轮换地图：

```bash
island-baker gallery --resolution 129 --output build/gallery
```

## 烘焙结果

| 文件 | 用途 |
|---|---|
| `height.png` | 16-bit 灰度高度图 |
| `height.raw` | Unity 可直接读取的小端 16-bit RAW |
| `biomes.png` | 地貌颜色掩码 |
| `materials.png` | 水体、熔岩、热岩等表面材质掩码 |
| `normal.png` | 世界表面法线 |
| `occlusion.png` | 基于地形凹陷近似的环境遮蔽 |
| `terrain.obj` | 降采样三角网格 |
| `spawn_manifest.json` | 岩体、植被、危险物件和补救攀爬点 |
| `route.json` | 最低代价攀爬路线及坏段标记 |
| `statistics.json` | 高度、坡度、物件和路线统计 |
| `preview.png` | 带路线叠加的俯视预览 |
| `preview_3d.png` | 带主要 spawner 物件的三维侧视预览 |

`analyze` 模式遵循“受控随机”的思路，只评估自然生成的路线，不主动把
关卡修平。`repair` 模式会在超出配置坡度的路线段添加
`climbing_hold_cluster` 占位物，方便做保证通关的派生玩法。

## Unity 导入

1. 把 `unity/Editor/` 复制到 Unity 工程的 `Assets/Editor/`。
2. 把一个完整烘焙目录复制到 `Assets/`。
3. 打开 `Tools > Vertical Island Baker > Import Bundle`。
4. 选择 bundle 目录并导入。
5. 可创建 `TerrainPrefabLibrary`，把清单中的 `kind` 映射到你自己的
   prefab；未映射时可先生成 Sphere/Cylinder 占位物。

Unity Terrain 负责基础表面，岩壁、洞穴、悬垂和树根由
`spawn_manifest.json` 中的独立网格 prefab 表达。只用高度图无法生成
真正的悬垂结构。

## 90% 是如何定义的

```bash
island-baker score \
  --generated build/island \
  --reference references/private/map-001
```

完整 bundle 总分由几何 75% 和物件分布 25% 组成。几何分进一步包含
高度误差、梯度、轮廓、多尺度形状、高度分布和局部细节；物件分包含
总量、类别、径向-高度分布和尺度分布。若参考只提供高度图，则明确退化
为几何分。脚本自动尝试旋转和镜像，并对高度单位做线性对齐。

```bash
island-baker calibrate \
  --reference references/private/map-001 \
  --trials 32 \
  --output build/calibrated
```

只有报告中的 `passes_90_percent` 为 `true`，该样本才算达到 90%。
完整目标还需要多张地图的留出测试集，不能只拟合一张图。

本地解包、参考数据隔离与下一阶段拟合方式见
[docs/private-reference-workflow.md](docs/private-reference-workflow.md)。

## 测试

```bash
python -m unittest discover -s tests -v
```

测试覆盖确定性、种子差异、六个高度槽、路线修复、完整 bundle 导出和
自相似度基线。

## 调研

公开事实、开发者说法、地貌资料、实现映射和不确定项记录在
[docs/research.md](docs/research.md)。

## 免责声明

本项目是独立、非官方、非商业的通用地形算法研究工具，与 PEAK、
Landfall Publishing AB 或 Aggro Crab Games LLC 无关联，也未获得其
背书。请勿提交或分发从游戏中提取的模型、贴图、场景、音频或源码。
