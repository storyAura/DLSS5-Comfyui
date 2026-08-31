# ComfyUI-DLSS5

[purkatyy/DLSS5-](https://github.com/purkatyy/DLSS5-/releases/tag/dlss) 的 ComfyUI 节点。对静图或视频拆帧做 DLSS5 Feature 18 同分辨率神经渲染。

节点：`image` → `dlss5` → **DLSS5 Neural Render**。`IMAGE` 进，`IMAGE` 出。

## 安装

Windows + NVIDIA RTX 30 / 40 / 50。需要 [VC++ 2015–2022](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)。解 30/50 的 `.rar` 需要 [7-Zip](https://www.7-zip.org/)。

1. 把本仓库放到 `ComfyUI/custom_nodes/DLSS5-Comfyui`
2. 重启 ComfyUI
3. 第一次跑图会从上游 [release](https://github.com/purkatyy/DLSS5-/releases/tag/dlss) 按当前显卡代数拉 DLL

预拉三套：

```bash
python vendor_dlls.py
```

| 文件 | 来源 |
| --- | --- |
| `vendor/dlssnr_host.dll` | `DLSS5Tool.zip` |
| `vendor/rtx40/nvngx_dlssnr.dll` | `DLSS5Tool.zip` |
| `vendor/rtx30/nvngx_dlssnr.dll` | `RTX30xx.rar` |
| `vendor/rtx50/nvngx_dlssnr.dll` | `RTX50xx.rar` |

换 30 / 40 / 50 要重启 ComfyUI。

## 工作流

```text
LoadImage → DLSS5 Neural Render → SaveImage
LoadVideo → GetVideoComponents → DLSS5 Neural Render → CreateVideo
```

[`example_workflows/dlss5_image.json`](example_workflows/dlss5_image.json)

## 例图

左 original，右 Final Effect。

![example 1](docs/examples/01.jpg)

![example 2](docs/examples/02.jpg)

![example 3](docs/examples/03.jpg)

![example 4](docs/examples/04.jpg)

![example 5](docs/examples/05.jpg)

![example 6](docs/examples/06.jpg)

![example 7](docs/examples/07.jpg)

## 参数

| 参数 | 说明 |
| --- | --- |
| `images` | `IMAGE` 张量。视频拆帧按顺序处理；RGBA 的 Alpha 原样传出 |
| `style` | 默认 / 自然 / 电影 / 风格3 |
| `intensity` | 总强度 0–1 |
| `local_tone` | 本地色调。拉低保住原图明暗 |
| `local_struct` | 本地结构。拉低守轮廓，拉高更立体 |
| `output_view` | 处理=成品；差异×10=改动对比；左右对比=左原右结果 |
| `output_mix` | 只在「处理」时生效：`原图 + (DLSS − 原图) × mix` |
| `gpu_gen` | Auto / RTX 30 / RTX 40 / RTX 50 |

## 许可

MIT。`nvngx_dlssnr.dll` 从原 release 获取。
