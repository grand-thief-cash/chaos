# BaoStock 文档爬虫

该脚本通过 BaoStock 官网的公开文档接口动态获取左侧菜单，下载菜单中的
全部 Markdown 文档，并按照官网顺序每 10 份文档生成一个分片：

```text
docs/third_party_sdk/baostock/
├── index.md
├── baostock-001.md
├── baostock-002.md
└── ...
```

“访问统计”是动态统计页面，不是 Markdown 文档，因此不会写入汇总文件。
根 `index.md` 会展开所有分片及其包含的具体文档。脚本还会将相对图片和
下载链接改写为 BaoStock 官网的绝对地址，并使用生成清单清理过期分片。
旧版单文件 `docs/third_party_sdk/baostock.md` 会在新目录成功生成后删除。

## 运行

先安装 crawler 的公共依赖：

```powershell
python -m pip install -r app/tools/py/crawler/requirements.txt
```

然后在仓库根目录直接运行：

```powershell
python app/tools/py/crawler/baostock/crawl.py
```

脚本不接收命令行参数。需要修改输出位置、并发数、超时或重试次数时，直接
编辑 `crawl.py` 顶部的“运行配置”区域。

## 测试

```powershell
python -m unittest discover `
  -s app/tools/py/crawler/baostock `
  -p "test_*.py"
```
