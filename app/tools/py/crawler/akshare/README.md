# AKShare SDK 文档爬虫

该脚本从 AKShare 官方 `data/index.rst.txt` 的 `toctree` 动态发现全部 SDK
文档，下载每个 Markdown/RST 源文件，并按每 10 个三级标题（`###`）拆分。

输出结构如下：

```text
docs/third_party_sdk/akshare/
├── index.md
├── stock/
│   ├── index.md
│   ├── stock-001.md
│   └── ...
├── fund/
│   ├── index.md
│   ├── fund_private-001.md
│   ├── fund_public-001.md
│   └── ...
└── ...
```

根 `index.md` 同时链接分类索引和所有分片；每个分类目录也有自己的
`index.md`。脚本只会清理上一次运行清单中记录的过期生成文件，不会删除
输出目录中未被爬虫管理的手工文件。只有全部远程文档下载成功后才会更新
输出。

## 运行

先安装 crawler 的公共依赖：

```powershell
python -m pip install -r app/tools/py/crawler/requirements.txt
```

在仓库根目录执行：

```powershell
python app/tools/py/crawler/akshare/crawl.py
```

脚本不接收命令行参数。需要修改抓取设置时，直接编辑 `crawl.py` 顶部的
“运行配置”区域：

```python
SOURCE_INDEX_URL = "https://akshare.akfamily.xyz/_sources/data/index.rst.txt"
OUTPUT_DIR = Path("docs/third_party_sdk/akshare")
SECTIONS_PER_FILE = 10
WORKERS = 4
TIMEOUT_SECONDS = 60.0
RETRIES = 3
```

## 测试

```powershell
python -m unittest discover `
  -s app/tools/py/crawler/akshare `
  -p "test_*.py"
```
